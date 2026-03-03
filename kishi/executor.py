import os
import sys
import shlex
import signal

from .state import COLOR_RED, COLOR_YELLOW, ALIASES, LOCAL_VARS, FUNCTIONS, BUILTINS
from .parser import SequenceNode, IfNode, WhileNode, ForNode, FunctionDefNode, LogicNode, PipelineNode
from .expander import Expander
from .job_control import JobManager

def get_close_match_suggestion(cmd_name):
    import difflib
    from .state import SYSTEM_COMMANDS, COLOR_CYAN, COLOR_RESET
    if not SYSTEM_COMMANDS:
        return ""
    matches = difflib.get_close_matches(cmd_name, SYSTEM_COMMANDS, n=1, cutoff=0.6)
    if matches:
        return f"\nŞunu mu demek istediniz: {COLOR_CYAN}'{matches[0]}'{COLOR_RESET} ?"
    return ""

def execute_pipeline(pipe_node):
    if not pipe_node.commands:
        return 0
        
    import copy
    commands = copy.deepcopy(pipe_node.commands)
    
    valid_commands = []
    for cmd in commands:
        if cmd.args and cmd.args[0] in ALIASES:
            aliased_parts = shlex.split(ALIASES[cmd.args[0]])
            cmd.args = aliased_parts + cmd.args[1:]
        cmd.args = Expander.expand(cmd.args)
        if cmd.args:
            valid_commands.append(cmd)
            
    num_cmds = len(valid_commands)
    if num_cmds == 0:
        return 0
    
    # Tek Komut ve Built-in
    if num_cmds == 1:
        cmd = valid_commands[0]
        
        env_only = True
        for a in cmd.args:
            if '=' not in a or a.startswith('-'):
                env_only = False
                break
                
        if env_only and cmd.args:
            for a in cmd.args:
                k, v = a.split('=', 1)
                LOCAL_VARS[k] = v
            return 0
            
        actual_cmd_idx = 0
        for i, a in enumerate(cmd.args):
            if '=' not in a or a.startswith('-'):
                actual_cmd_idx = i
                break
                
        if actual_cmd_idx < len(cmd.args):
            cmd_name = cmd.args[actual_cmd_idx]
            if cmd_name in BUILTINS:
                return BUILTINS[cmd_name](cmd.args[actual_cmd_idx:])
            elif cmd_name in FUNCTIONS:
                args_passed = cmd.args[actual_cmd_idx:]
                old_args = {str(i): LOCAL_VARS.get(str(i), None) for i in range(1, len(args_passed))}
                for i in range(1, len(args_passed)):
                    LOCAL_VARS[str(i)] = args_passed[i]
                    
                status = execute_ast(FUNCTIONS[cmd_name])
                
                for k, v in old_args.items():
                    if v is None:
                        if k in LOCAL_VARS: del LOCAL_VARS[k]
                    else:
                        LOCAL_VARS[k] = v
                return status

    if sys.platform == 'win32':
        import subprocess
        last_status = 0
        processes = []
        prev_stdout = None
        
        for i, cmd in enumerate(valid_commands):
            cmd_args_to_run = []
            parsing_env = True
            for a in cmd.args:
                if parsing_env and '=' in a and not a.startswith('-'): pass
                else:
                    parsing_env = False
                    cmd_args_to_run.append(a)
            if not cmd_args_to_run: continue

            cmd_name = cmd_args_to_run[0]
            if cmd_name in BUILTINS or cmd_name in FUNCTIONS:
                if cmd_name in BUILTINS: last_status = BUILTINS[cmd_name](cmd_args_to_run)
                continue
                
            kwargs = {'stdin': prev_stdout}
            if i < num_cmds - 1:
                kwargs['stdout'] = subprocess.PIPE
            else:
                if cmd.out_file:
                    mode = "a" if cmd.out_append else "w"
                    try: kwargs['stdout'] = open(cmd.out_file, mode)
                    except: pass
            
            if cmd.err_file:
                mode = "a" if cmd.err_append else "w"
                try: kwargs['stderr'] = open(cmd.err_file, mode)
                except: pass
            
            try:
                p = subprocess.Popen(cmd_args_to_run, **kwargs)
                processes.append(p)
                prev_stdout = p.stdout
            except FileNotFoundError:
                sugg = get_close_match_suggestion(cmd_name)
                print(f"{COLOR_RED}Hata:{COLOR_RESET} '{cmd_name}' bulunamadı.{sugg}", file=sys.stderr)
                return 127
            except Exception as e:
                print(f"Windows Exec Hata: {e}")
                return 1
                
        for p in processes:
            p.wait()
            last_status = p.returncode
            
        return last_status

    # Çoklu Pipe veya Tekli Harici Komutlar (Fork & Process Groups)
    pipes = [os.pipe() for _ in range(num_cmds - 1)]
    pids = []
    
    pgid = None
    shell_tty = -1
    old_pgrp = -1
    try:
        shell_tty = sys.stdin.fileno()
        old_pgrp = os.tcgetpgrp(shell_tty)
    except Exception:
        pass 

    for i in range(num_cmds):
        cmd = valid_commands[i]
        in_fd = pipes[i-1][0] if i > 0 else 0
        out_fd = pipes[i][1] if i < num_cmds - 1 else 1
        
        err_fd = 2
        user_in_fd, user_out_fd, user_err_fd = None, None, None
        from .state import COLOR_RESET
        
        if cmd.in_file:
            try: user_in_fd = os.open(cmd.in_file, os.O_RDONLY)
            except: print(f"{COLOR_RED}Hata:{COLOR_RESET} {cmd.in_file} okunamıyor."); return 1
            
        if cmd.out_file:
            flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if cmd.out_append else os.O_TRUNC)
            try: user_out_fd = os.open(cmd.out_file, flags, 0o644)
            except: print(f"{COLOR_RED}Hata:{COLOR_RESET} {cmd.out_file} yazılamıyor."); return 1
            
        if cmd.err_to_out:
            pass
        elif cmd.err_file:
            flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if cmd.err_append else os.O_TRUNC)
            try: user_err_fd = os.open(cmd.err_file, flags, 0o644)
            except: print(f"{COLOR_RED}Hata:{COLOR_RESET} {cmd.err_file} yazılamıyor."); return 1

        final_in_fd = user_in_fd if user_in_fd is not None else in_fd
        final_out_fd = user_out_fd if user_out_fd is not None else out_fd
        final_err_fd = user_err_fd if user_err_fd is not None else err_fd

        pid = os.fork()
        if pid == 0:
            # CHILD PROCESS
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            signal.signal(signal.SIGTSTP, signal.SIG_DFL)
            signal.signal(signal.SIGQUIT, signal.SIG_DFL)
            signal.signal(signal.SIGTTOU, signal.SIG_DFL)
            
            child_pid = os.getpid()
            if i == 0:
                os.setpgid(child_pid, child_pid)
            else:
                os.setpgid(child_pid, pgid)
                
            if final_in_fd != 0: os.dup2(final_in_fd, 0)
            if final_out_fd != 1: os.dup2(final_out_fd, 1)
            
            if cmd.err_to_out:
                os.dup2(1, 2)
            elif final_err_fd != 2:
                os.dup2(final_err_fd, 2)
            
            for r, w in pipes:
                os.close(r)
                os.close(w)
            if user_in_fd: os.close(user_in_fd)
            if user_out_fd: os.close(user_out_fd)
            if user_err_fd: os.close(user_err_fd)

            env_updates = {}
            cmd_args_to_run = []
            parsing_env = True
            for a in cmd.args:
                if parsing_env and '=' in a and not a.startswith('-'):
                    k, v = a.split('=', 1)
                    env_updates[k] = v
                else:
                    parsing_env = False
                    cmd_args_to_run.append(a)
            
            if not cmd_args_to_run:
                sys.exit(0)
                
            for k, v in env_updates.items():
                os.environ[k] = v

            cmd_name = cmd_args_to_run[0]
            if cmd_name in BUILTINS:
                BUILTINS[cmd_name](cmd_args_to_run)
                sys.exit(0)
            if cmd_name in FUNCTIONS:
                for idx in range(1, len(cmd_args_to_run)):
                    LOCAL_VARS[str(idx)] = cmd_args_to_run[idx]
                status = execute_ast(FUNCTIONS[cmd_name])
                sys.exit(status)
                
            try:
                os.execvp(cmd_name, cmd_args_to_run)
            except FileNotFoundError:
                sugg = get_close_match_suggestion(cmd_name)
                print(f"{COLOR_RED}Hata:{COLOR_RESET} '{cmd_name}' bulunamadı.{sugg}", file=sys.stderr)
                sys.exit(127)
        else:
            # PARENT PROCESS
            if i == 0:
                pgid = pid
            os.setpgid(pid, pgid)
            pids.append(pid)
            if user_in_fd: os.close(user_in_fd)
            if user_out_fd: os.close(user_out_fd)
            if user_err_fd: os.close(user_err_fd)

    for r, w in pipes:
        os.close(r)
        os.close(w)

    cmd_str = " ".join([" ".join(c.args) for c in valid_commands])
    job = JobManager.add_job(pids, cmd_str, pipe_node.is_background)

    last_status = 0
    if not pipe_node.is_background:
        if old_pgrp != -1:
            try: os.tcsetpgrp(shell_tty, pgid)
            except Exception: pass
            
        for p in pids:
            try:
                wpid, status = os.waitpid(p, os.WUNTRACED)
                if os.WIFSTOPPED(status):
                    job.status = "Stopped"
                    job.is_background = True
                    print(f"\n{COLOR_YELLOW}[{job.job_id}]+  Durduruldu{COLOR_RESET}      {job.cmd_str}")
                    break
                else:
                    last_status = os.waitstatus_to_exitcode(status)
            except ChildProcessError:
                pass
                
        if job.status != "Stopped":
            JobManager.remove_job(job.job_id)
            
        if old_pgrp != -1:
            try: os.tcsetpgrp(shell_tty, old_pgrp)
            except Exception: pass

    return last_status

def execute_ast(node):
    if node is None:
        return 0
        
    if isinstance(node, SequenceNode):
        last_status = 0
        for stmt in node.statements:
            last_status = execute_ast(stmt)
        return last_status
        
    elif isinstance(node, IfNode):
        if execute_ast(node.condition_ast) == 0:
            return execute_ast(node.then_ast)
        else:
            for c_ast, t_ast in node.elifs:
                if execute_ast(c_ast) == 0:
                    return execute_ast(t_ast)
            if node.else_ast:
                return execute_ast(node.else_ast)
        return 0
        
    elif isinstance(node, WhileNode):
        last_status = 0
        while execute_ast(node.condition_ast) == 0:
            last_status = execute_ast(node.body_ast)
        return last_status
        
    elif isinstance(node, ForNode):
        items = Expander.expand(node.iter_items)
        last_status = 0
        for item in items:
            LOCAL_VARS[node.var_name] = item
            last_status = execute_ast(node.body_ast)
        return last_status
        
    elif isinstance(node, FunctionDefNode):
        FUNCTIONS[node.func_name] = node.body_ast
        return 0
        
    elif isinstance(node, LogicNode):
        if node.operator == '&':
            execute_ast(node.left)
            return execute_ast(node.right)
            
        left_status = execute_ast(node.left)
        if node.operator == '&&':
            if left_status == 0:
                return execute_ast(node.right)
            return left_status
        elif node.operator == '||':
            if left_status != 0:
                return execute_ast(node.right)
            return left_status
    elif isinstance(node, PipelineNode):
        return execute_pipeline(node)
    return 0

def process_command_line(cmd_line):
    """Ana komut işleyici"""
    import kishi.state
    KISHI_SESSION = kishi.state.KISHI_SESSION
    try:
        if ('!!' in cmd_line or '!$' in cmd_line) and KISHI_SESSION:
            strings = KISHI_SESSION.history.get_strings()
            if strings:
                last_idx = len(strings) - 1
                last_cmd = strings[last_idx]
                
                while last_cmd == cmd_line and last_idx > 0:
                    last_idx -= 1
                    last_cmd = strings[last_idx]
                
                expanded = False
                
                if '!!' in cmd_line and last_cmd:
                    cmd_line = cmd_line.replace('!!', last_cmd)
                    expanded = True
                if '!$' in cmd_line and last_cmd:
                    try:
                        from .lexer import Tokenizer
                        last_arg = Tokenizer.tokenize(last_cmd)[-1]
                        cmd_line = cmd_line.replace('!$', last_arg)
                        expanded = True
                    except: pass
                
                if expanded:
                    print(cmd_line)
    except Exception:
        pass
        
    from .lexer import Tokenizer
    from .parser import Parser
    tokens = Tokenizer.wrap_tokenize(cmd_line)
    if not tokens:
        return
    ast = Parser.parse(tokens)
    if ast:
        execute_ast(ast)
