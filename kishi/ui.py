import os
import subprocess
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

from .state import COLOR_AMBER, COLOR_RESET, COLOR_RED, COLOR_YELLOW, COLOR_CYAN
import kishi.state

kishi_style = Style.from_dict({
    'command.valid': 'ansigreen bold',
    'command.invalid': 'ansired bold',
    'string': 'ansiyellow',
    'variable': 'ansicyan',
    'operator': 'ansimagenta',
    'path.invalid': 'ansired underline',
    'bottom-toolbar': 'reverse'
})

class KishiLexer(Lexer):
    def lex_document(self, document):
        def get_line(lineno):
            line = document.lines[lineno]
            if not line: return []
            result = []
            words = line.split(' ')
            for i, word in enumerate(words):
                if i > 0: result.append(('', ' '))
                if not word: continue
                if word.startswith('"') or word.startswith("'") or word.endswith('"') or word.endswith("'"):
                    result.append(('class:string', word))
                elif word.startswith('$'):
                    result.append(('class:variable', word))
                elif word in ('|', '&&', '||', '>', '<', '>>', '2>', '2>>', '2>&1', '&', ';'):
                    result.append(('class:operator', word))
                elif word in ('if', 'then', 'elif', 'else', 'fi', 'for', 'while', 'in', 'do', 'done', '[', ']', '{', '}'):
                    result.append(('class:command.valid', word))
                elif i == 0 or (i > 0 and words[i-1] in ('|', '&&', '||', ';', 'then', 'do', 'else', 'elif')):
                    clean_word = word.strip()
                    if clean_word in kishi.state.BUILTINS or clean_word in kishi.state.SYSTEM_COMMANDS or clean_word in kishi.state.ALIASES:
                        result.append(('class:command.valid', word))
                    elif os.path.exists(clean_word) or clean_word.startswith("./") or clean_word.startswith("~/"):
                        result.append(('class:command.valid', word))
                    elif '/' in clean_word:
                        result.append(('class:path.invalid', word))
                    else:
                        result.append(('class:command.invalid', word))
                else:
                    if '/' in word and not os.path.exists(os.path.expanduser(word)):
                        result.append(('class:path.invalid', word))
                    else:
                        result.append(('', word))
            return result
        return get_line

class KishiCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        words = text.split()
        is_first_word = (not text) or (len(words) == 1 and not text.endswith(" ")) or (len(words) == 0)
        
        import re
        word_before_cursor = document.get_word_before_cursor(pattern=re.compile(r'[^\s]+'))
        target_dir = os.path.dirname(word_before_cursor) or "."
        base_name = os.path.basename(word_before_cursor)
        
        try:
            for f in os.listdir(target_dir):
                if f.lower().startswith(base_name.lower()):
                    full_path = os.path.join(target_dir, f) if target_dir != "." else f
                    if os.path.isdir(os.path.join(target_dir, f)):
                        yield Completion(full_path + '/', start_position=-len(base_name))
                    else:
                        yield Completion(full_path, start_position=-len(base_name))
        except: pass

        if is_first_word:
            text_lower = word_before_cursor.lower()
            if not '/' in word_before_cursor and word_before_cursor.strip() != "":
                for c in kishi.state.SYSTEM_COMMANDS:
                    if c.lower().startswith(text_lower):
                        yield Completion(c, start_position=-len(word_before_cursor))
            for b in kishi.state.BUILTINS.keys():
                if b.lower().startswith(text_lower):
                    yield Completion(b, start_position=-len(word_before_cursor))

kishi_bindings = KeyBindings()

@kishi_bindings.add('c-l')
def _(event):
    " Clears the screen cleanly and preserves the prompt. "
    from prompt_toolkit.shortcuts import clear
    clear()

@kishi_bindings.add('c-r')
async def _(event):
    " Fuzzy history search "
    history_file = os.path.join(os.environ.get("HOME", "/"), ".kishi_history")
    if not os.path.exists(history_file): return
    try:
        with open(history_file, 'r') as f:
            lines = f.readlines()
            
        parsed_commands = []
        for l in lines:
            l = l.strip()
            if not l or l.startswith('#'):
                continue
            if l.startswith('+'):
                cmd = l[1:]
                if cmd:
                    parsed_commands.append(cmd)
            else:
                parsed_commands.append(l)
                
        unique_lines = list(dict.fromkeys(reversed(parsed_commands)))
        
        from .tui_fuzzy import run_fuzzy_history
        selected = await run_fuzzy_history(unique_lines)
        
        if selected:
            event.app.current_buffer.text = selected
            event.app.current_buffer.cursor_position = len(selected)
    except: pass

@kishi_bindings.add('c-e')
async def _(event):
    " Opens File Explorer with Ctrl+E "
    from .tui_explorer import kishi_explore
    await kishi_explore(["explore"])

@kishi_bindings.add('escape', 'enter')
def _(event):
    " Forces multi-line mode with Alt+Enter "
    event.current_buffer.insert_text('\n')

def get_prompts():
    cwd = os.getcwd()
    home = os.environ.get("HOME", "")
    
    if home and cwd.startswith(home):
        display_cwd = cwd.replace(home, "~", 1)
    else:
        display_cwd = cwd

    try:
        term_width = os.get_terminal_size().columns
        if len(display_cwd) > term_width - 15:
            display_cwd = "..." + display_cwd[-(term_width - 20):]
    except: pass
        
    venv_prompt = ""
    if "VIRTUAL_ENV" in os.environ:
        venv_name = os.path.basename(os.environ["VIRTUAL_ENV"])
        venv_prompt = f"{COLOR_CYAN}({venv_name}){COLOR_RESET} "

    left_prompt = ANSI(f"{venv_prompt}{COLOR_AMBER}Kishi$ ->{COLOR_RESET} ")
    
    git_branch = ""
    try:
        git_out = subprocess.check_output(
            ["git", "branch", "--show-current"],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
        if git_out:
            git_branch = f"{COLOR_YELLOW}git:({COLOR_RED}{git_out}{COLOR_YELLOW}) {COLOR_RESET}"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
        
    right_prompt = ANSI(f"{git_branch}{COLOR_CYAN}[{display_cwd}]{COLOR_RESET}")
    return left_prompt, right_prompt

def get_bottom_toolbar():
    if kishi.state.KISHI_SESSION:
        text = kishi.state.KISHI_SESSION.default_buffer.text
        words = text.split()
        if words:
            cmd = words[0]
            if cmd == "export": return ANSI(" Usage: export VAR=value")
            if cmd == "cd": return ANSI(" Usage: cd [DIRECTORY]")
            if cmd == "grep": return ANSI(" Usage: grep [OPTIONS] PATTERN [FILE...]")
            if cmd == "pacman": return ANSI(" Arch Linux Package Manager")
            if cmd == "git": return ANSI(" Usage: git [commit/push/pull/status/...]")
    return ""

def init_prompt_toolkit():
    history_file = os.path.join(os.environ.get("HOME", "/"), ".kishi_history")
    
    return PromptSession(
        history=FileHistory(history_file),
        auto_suggest=AutoSuggestFromHistory(),
        completer=KishiCompleter(),
        lexer=KishiLexer(),
        style=kishi_style,
        key_bindings=kishi_bindings,
        bottom_toolbar=get_bottom_toolbar,
        complete_while_typing=True
    )
