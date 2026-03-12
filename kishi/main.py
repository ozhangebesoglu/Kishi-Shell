import os
import sys
import signal

import kishi.state as state
from kishi.builtins import BUILTINS_DICT
from kishi.ui import init_prompt_toolkit, get_prompts
from kishi.executor import process_command_line
from kishi.job_control import JobManager

def load_rc_file():
    startup_cmds = []
    rc_path = os.path.join(os.environ.get("HOME", "/"), ".kishirc")
    if not os.path.exists(rc_path):
        try:
            with open(rc_path, "w") as f:
                f.write("# Kishi Shell Initialization File\n")
                f.write("alias ll='ls -la'\n")
                f.write("alias h='history'\n")
        except: pass
        return startup_cmds

    try:
        with open(rc_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"): continue
                if line.startswith("alias "):
                    parts = line[6:].split("=", 1)
                    if len(parts) == 2:
                        name = parts[0].strip()
                        val = parts[1].strip().strip("'").strip('"')
                        state.ALIASES[name] = val
                elif line.startswith("export "):
                    parts = line[7:].split("=", 1)
                    if len(parts) == 2:
                        name = parts[0].strip()
                        val = parts[1].strip().strip("'").strip('"')
                        import re
                        def replacer(m):
                            return os.environ.get(m.group(1), "")
                        val = re.sub(r'\$([A-Za-z0-9_]+)', replacer, val)
                        os.environ[name] = val
                else:
                    startup_cmds.append(line)
    except Exception as e:
        print(f"Warning: Could not read .kishirc - {e}")
        
    return startup_cmds

def load_plugins():
    import importlib.util
    
    plugin_dir = os.path.join(os.environ.get("HOME", "/"), ".kishi", "plugins")
    if not os.path.exists(plugin_dir):
        return
        
    for filename in os.listdir(plugin_dir):
        if filename.endswith(".py"):
            filepath = os.path.join(plugin_dir, filename)
            module_name = "kishi.plugins." + filename[:-3]
            try:
                spec = importlib.util.spec_from_file_location(module_name, filepath)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    if hasattr(mod, "PLUGIN_COMMANDS") and isinstance(mod.PLUGIN_COMMANDS, dict):
                        expected_cmd = filename[:-3]
                        if expected_cmd in mod.PLUGIN_COMMANDS:
                            state.BUILTINS[expected_cmd] = mod.PLUGIN_COMMANDS[expected_cmd]
                        else:
                            print(f"{state.COLOR_YELLOW}Plugin Warning:{state.COLOR_RESET} '{filename}' ignored. It must export exactly '{expected_cmd}' in PLUGIN_COMMANDS.")
            except Exception as e:
                print(f"{state.COLOR_RED}Plugin Error:{state.COLOR_RESET} Failed to load {filename} - {e}")

def main():
    state.BUILTINS.update(BUILTINS_DICT)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--setup":
        from kishi.builtins import kishi_setup
        sys.exit(kishi_setup(["setup"] + sys.argv[2:]))

    if len(sys.argv) > 2 and sys.argv[1] == "-c":
        state.load_system_commands()
        load_rc_file()
        load_plugins()
        process_command_line(sys.argv[2])
        sys.exit(0)
        
    def sigint_handler(sig, frame):
        pass
    signal.signal(signal.SIGINT, sigint_handler)
    try:
        signal.signal(signal.SIGTSTP, signal.SIG_IGN)
        signal.signal(signal.SIGTTOU, signal.SIG_IGN)
        signal.signal(signal.SIGTTIN, signal.SIG_IGN)
    except AttributeError:
        pass

    state.load_system_commands()
    try:
        state.KISHI_SESSION = init_prompt_toolkit()
    except Exception as e:
        print("Failed to load prompt_toolkit:", e)
        
    startup_cmds = load_rc_file()
    load_plugins()
    
    # Execute startup commands from .kishirc
    for cmd in startup_cmds:
        process_command_line(cmd)
    
    print(f"{state.COLOR_AMBER}Kishi Shell Advanced (v2.0.0.1){state.COLOR_RESET}")
    print("Type 'help' for the command guide.")

    while True:
        try:
            JobManager.clean_jobs()
            
            l_prompt, r_prompt = get_prompts()
            if state.KISHI_SESSION:
                cmd_line = state.KISHI_SESSION.prompt(l_prompt, rprompt=r_prompt)
            else:
                cmd_line = input("Kishi$ -> ")
            
            if not cmd_line.strip(): continue
            
            process_command_line(cmd_line)
            
        except EOFError:
            print(f"\n{state.COLOR_AMBER}Kishi:{state.COLOR_RESET} Exit signal received. Goodbye!")
            break
        except KeyboardInterrupt:
            print()
        except Exception as e:
            print(f"{state.COLOR_RED}Kishi Panic:{state.COLOR_RESET} {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
