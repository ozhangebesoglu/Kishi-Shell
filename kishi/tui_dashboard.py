import os
import psutil
import threading
import time
import subprocess

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import Window, HSplit, VSplit
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.widgets import Frame
from prompt_toolkit.styles import Style
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.filters import has_focus
from prompt_toolkit.formatted_text import ANSI, to_formatted_text
from prompt_toolkit.layout.processors import BeforeInput

def generate_bar(percentage, width=15):
    filled = int(width * percentage / 100)
    empty = width - filled
    color = "ansicyan"
    if percentage > 85: color = "ansired"
    elif percentage > 60: color = "ansiyellow"
    return [
        (color, "█" * filled),
        ("class:bg", "░" * empty),
        ("", f" {percentage:5.1f}%")
    ]

gpu_text_cache = [("class:invalid", "\n Loading...\n")]
cpu_text_cache = []
ram_text_cache = []
net_text_cache = []

last_net = None

def fetch_system_background():
    global gpu_text_cache, cpu_text_cache, ram_text_cache, net_text_cache, last_net
    
    # --- GPU FETCH ---
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total", "--format=csv,noheader"],
            text=True, stderr=subprocess.DEVNULL
        )
        parts = out.strip().split(", ")
        if len(parts) >= 5:
            gpu_text_cache = [
                ("class:title", f" {parts[0][:20]}\n\n"),
                ("class:label", " Core Temp: "), ("", f"{parts[1]} °C\n"),
                ("class:label", " GPU Util : "), ("", f"{parts[2]}\n"),
                ("class:label", " VRAM Used: "), ("", f"{parts[3]}\n"),
                ("class:label", " VRAM Totl: "), ("", f"{parts[4]}\n"),
            ]
        else:
            gpu_text_cache = [("class:invalid", "\n N/A\n (nvidia-smi not found)\n")]
    except:
        gpu_text_cache = [("class:invalid", "\n N/A\n (nvidia-smi not found)\n")]

    # --- CPU FETCH ---
    c_text = []
    cpu = psutil.cpu_percent(interval=0.1)
    c_text.append(("class:label", " Total: "))
    c_text.extend(generate_bar(cpu, width=12))
    c_text.append(("", "\n\n"))
    cores = psutil.cpu_percent(interval=0.1, percpu=True)
    for i, c in enumerate(cores[:8]):
        c_text.append(("class:label", f" C{i:<2}: "))
        c_text.extend(generate_bar(c, width=13))
        c_text.append(("", "\n"))
    cpu_text_cache = c_text

    # --- RAM FETCH ---
    r_text = []
    vmem = psutil.virtual_memory()
    r_text.append(("class:label", " RAM Usage:\n "))
    r_text.extend(generate_bar(vmem.percent, width=18))
    r_text.append(("", f"\n {vmem.used / (1024**3):.1f} GB / {vmem.total / (1024**3):.1f} GB\n\n"))
    
    swap = psutil.swap_memory()
    r_text.append(("class:label", " SWAP Usage:\n "))
    r_text.extend(generate_bar(swap.percent, width=18))
    r_text.append(("", f"\n {swap.used / (1024**3):.1f} GB / {swap.total / (1024**3):.1f} GB\n"))
    ram_text_cache = r_text

    # --- NET / DISK FETCH ---
    n_text = []
    try:
        disk = psutil.disk_usage('/')
        n_text.append(("class:label", " Root Disk (/):\n "))
        n_text.extend(generate_bar(disk.percent, width=18))
        n_text.append(("", f"\n Free: {disk.free / (1024**3):.1f}GB / {disk.total / (1024**3):.1f}GB\n\n"))
    except: pass
    
    try:
        curr_net = psutil.net_io_counters()
        n_text.append(("class:label", " Network Traffic:\n"))
        
        down_speed = 0
        up_speed = 0
        if last_net:
            down_speed = (curr_net.bytes_recv - last_net.bytes_recv) / 1024
            up_speed = (curr_net.bytes_sent - last_net.bytes_sent) / 1024
            
        last_net = curr_net
        n_text.append(("", f" Down:  {down_speed:.1f} KB/s\n"))
        n_text.append(("", f" Up  :  {up_speed:.1f} KB/s\n\n"))
        n_text.append(("ansigray", f" Tot. Rx: {curr_net.bytes_recv / (1024**2):.1f} MB\n"))
        n_text.append(("ansigray", f" Tot. Tx: {curr_net.bytes_sent / (1024**2):.1f} MB\n"))
    except: pass
    net_text_cache = n_text

def get_gpu_info(): return gpu_text_cache
def get_cpu_info(): return cpu_text_cache
def get_ram_info(): return ram_text_cache
def get_net_info(): return net_text_cache


def _build_prompt_tuples():
    tuples = []
    if "VIRTUAL_ENV" in os.environ:
        venv_name = os.path.basename(os.environ["VIRTUAL_ENV"])
        tuples.append(("ansicyan", f"({venv_name}) "))
    tuples.append(("fg:#ffbf00 bold", "Kishi$ -> "))
    return tuples


def _build_info_tuples():
    tuples = []
    try:
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"],
            stderr=subprocess.DEVNULL, text=True, cwd=os.getcwd()
        ).strip()
        if branch:
            tuples.extend([
                ("ansiyellow", " git:("),
                ("ansired", branch),
                ("ansiyellow", ") "),
            ])
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    cwd = os.getcwd()
    home = os.environ.get("HOME", "")
    display_cwd = cwd.replace(home, "~", 1) if home and cwd.startswith(home) else cwd
    tuples.append(("ansicyan", f"[{display_cwd}]"))
    return tuples


def kishi_dashboard(args):
    psutil.cpu_percent(interval=None)
    psutil.cpu_percent(interval=None, percpu=True)
    
    left_col = HSplit([
        Frame(Window(content=FormattedTextControl(text=get_gpu_info)), title="[ GPU ]"),
        Frame(Window(content=FormattedTextControl(text=get_ram_info)), title="[ Memory & Swap ]")
    ], width=28)
    
    right_col = HSplit([
        Frame(Window(content=FormattedTextControl(text=get_cpu_info)), title="[ CPU ]"),
        Frame(Window(content=FormattedTextControl(text=get_net_info)), title="[ Storage & Net ]")
    ], width=28)
    
    from kishi.tui_explorer import ExplorerUI
    from prompt_toolkit.layout.containers import ConditionalContainer
    from prompt_toolkit.filters import Condition
    from prompt_toolkit.key_binding import merge_key_bindings

    terminal_lines = []
    terminal_lines.extend([
        ("class:title", " [KISHI] Dashboard Terminal\n"),
        ("", " =====================================\n"),
        ("ansigray", " Type 'exit' or 'q' to return.\n\n"),
    ])

    from kishi.ui import KishiCompleter, KishiLexer
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

    history_file = os.path.join(os.environ.get("HOME", "/"), ".kishi_history")
    input_buffer = Buffer(
        multiline=False,
        completer=KishiCompleter(),
        complete_while_typing=True,
        history=FileHistory(history_file),
        auto_suggest=AutoSuggestFromHistory(),
        enable_history_search=True,
    )

    show_explorer = False
    explorer = ExplorerUI(os.getcwd(), standalone=False)
    running_process = None

    def get_terminal_text():
        return terminal_lines

    out_control = FormattedTextControl(
        text=get_terminal_text,
        focusable=True,
        show_cursor=True,
    )

    out_win = Window(
        content=out_control,
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
        cursorline=False,
    )

    from prompt_toolkit.layout.menus import CompletionsMenu
    from prompt_toolkit.layout.containers import Float, FloatContainer

    in_control = BufferControl(
        buffer=input_buffer,
        input_processors=[BeforeInput(_build_prompt_tuples)],
        lexer=KishiLexer(),
    )
    in_win = Window(content=in_control, height=1)

    explorer_col = ConditionalContainer(
        content=Frame(explorer.container, title="[ IDE Explorer ]"),
        filter=Condition(lambda: show_explorer)
    )

    center_col = HSplit([
        explorer_col,
        Frame(out_win, title="[ Kishi Terminal ]"),
        Frame(in_win, title="[ Command Line ]", style="class:input_frame")
    ])
    
    body = VSplit([
        left_col,
        center_col,
        right_col
    ])
    
    header = Window(height=1, content=FormattedTextControl(text=[("class:header", " KISHI DASHBOARD 8.0 | [Enter] Run | [Tab] Complete | [PgUp/PgDn] Scroll | [Shift+Tab] Switch | [Ctrl+E] Explorer | [Ctrl+R] Search | [Ctrl+Q] Quit ")]))

    root = FloatContainer(
        content=HSplit([header, body]),
        floats=[Float(
            xcursor=True, ycursor=True,
            allow_cover_cursor=True,
            content=CompletionsMenu(max_height=10, scroll_offset=1),
        )]
    )
    layout = Layout(root, focused_element=in_win)

    kb = KeyBindings()

    _user_scrolled = [False]

    def _scroll_to_bottom(force=False):
        if _user_scrolled[0] and not force:
            return
        full_text = "".join(t[1] for t in terminal_lines)
        line_count = full_text.count('\n')
        try:
            from prompt_toolkit.data_structures import Point
            out_control._cursor_position = Point(x=0, y=line_count)
        except Exception:
            pass

    def _trim_lines():
        full_text = "".join(t[1] for t in terminal_lines)
        line_count = full_text.count('\n')
        if line_count > 300:
            target = line_count - 200
            removed = 0
            for i, (_, text) in enumerate(terminal_lines):
                removed += text.count('\n')
                if removed >= target:
                    terminal_lines[:] = terminal_lines[i + 1:]
                    break

    def _append_styled(tuples):
        terminal_lines.extend(tuples)
        _trim_lines()
        _scroll_to_bottom()

    def _append_ansi(text):
        try:
            parsed = to_formatted_text(ANSI(text))
            terminal_lines.extend(parsed)
        except Exception:
            terminal_lines.append(("", str(text)))
        _trim_lines()
        _scroll_to_bottom()

    def _run_builtin(builtin_func, builtin_args):
        import io, contextlib
        f = io.StringIO()
        with contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
            try:
                builtin_func(builtin_args)
            except SystemExit:
                pass
        output = f.getvalue()
        if output:
            _append_ansi(output)

    @kb.add("c-q")
    def _(event):
        if running_process and running_process.poll() is None:
            running_process.kill()
        event.app.exit(result=0)

    @kb.add("c-c")
    def _(event):
        nonlocal running_process
        if running_process and running_process.poll() is None:
            import signal
            try:
                running_process.send_signal(signal.SIGINT)
            except:
                running_process.kill()
            _append_styled([("ansired bold", "\n^C\n")])
            running_process = None
        
    @kb.add("c-e")
    def toggle_explorer(event):
        nonlocal show_explorer
        if not show_explorer:
            show_explorer = True
            layout.focus(explorer.left_window)
        else:
            if layout.has_focus(explorer.left_window):
                show_explorer = False
                layout.focus(in_win)
            else:
                layout.focus(explorer.left_window)

    @kb.add("s-tab")
    def toggle_focus(event):
        if layout.has_focus(in_win):
            layout.focus(out_win)
        elif layout.has_focus(out_win):
            if show_explorer:
                layout.focus(explorer.left_window)
            else:
                layout.focus(in_win)
        elif layout.has_focus(explorer.left_window):
            layout.focus(explorer.right_window)
        elif layout.has_focus(explorer.right_window):
            layout.focus(in_win)
        else:
            layout.focus(in_win)

    _rsearch = {"matches": [], "idx": 0, "updating": False}

    def _reset_rsearch(buff):
        if not _rsearch["updating"]:
            _rsearch["matches"] = []
            _rsearch["idx"] = 0

    input_buffer.on_text_changed += _reset_rsearch

    def _load_history_commands():
        if not os.path.exists(history_file):
            return []
        try:
            with open(history_file, "r") as f:
                lines = f.readlines()
        except Exception:
            return []
        cmds = []
        for l in lines:
            l = l.strip()
            if not l or l.startswith("#"):
                continue
            if l.startswith("+"):
                cmd = l[1:]
                if cmd:
                    cmds.append(cmd)
            else:
                cmds.append(l)
        return list(dict.fromkeys(reversed(cmds)))

    @kb.add("c-r", filter=has_focus(input_buffer))
    def reverse_search(event):
        st = _rsearch
        if st["matches"]:
            st["idx"] = (st["idx"] + 1) % len(st["matches"])
            st["updating"] = True
            input_buffer.text = st["matches"][st["idx"]]
            input_buffer.cursor_position = len(input_buffer.text)
            st["updating"] = False
            return

        query = input_buffer.text.strip().lower()
        unique = _load_history_commands()
        if query:
            matches = [c for c in unique if query in c.lower()]
        else:
            matches = unique

        if matches:
            st["matches"] = matches
            st["idx"] = 0
            st["updating"] = True
            input_buffer.text = matches[0]
            input_buffer.cursor_position = len(input_buffer.text)
            st["updating"] = False

    def _get_max_y():
        full_text = "".join(t[1] for t in terminal_lines)
        return full_text.count('\n')

    def _do_scroll(delta):
        from prompt_toolkit.data_structures import Point
        pos = out_control._cursor_position
        max_y = _get_max_y()
        new_y = max(0, min(pos.y + delta, max_y))
        out_control._cursor_position = Point(x=0, y=new_y)
        _user_scrolled[0] = new_y < max_y

    @kb.add("up", filter=has_focus(out_control))
    def scroll_up(event):
        _do_scroll(-3)

    @kb.add("down", filter=has_focus(out_control))
    def scroll_down(event):
        _do_scroll(3)

    @kb.add("pageup")
    def page_up(event):
        _do_scroll(-15)

    @kb.add("pagedown")
    def page_down(event):
        _do_scroll(15)

    @kb.add("end")
    def scroll_end(event):
        _user_scrolled[0] = False
        _scroll_to_bottom(force=True)

    @kb.add("home")
    def scroll_home(event):
        from prompt_toolkit.data_structures import Point
        out_control._cursor_position = Point(x=0, y=0)
        _user_scrolled[0] = True

    combined_kb = merge_key_bindings([kb, explorer.kb])

    @kb.add("enter", filter=has_focus(input_buffer))
    def execute_cmd(event):
        nonlocal running_process
        cmd = input_buffer.text.strip()
        input_buffer.text = ""

        if running_process and running_process.poll() is None:
            try:
                running_process.stdin.write((cmd + "\n").encode('utf-8'))
                running_process.stdin.flush()
                _append_styled([("", f"{cmd}\n")])
            except Exception:
                pass
            return

        if not cmd: return

        _user_scrolled[0] = False

        try:
            input_buffer.history.store_string(cmd)
        except Exception:
            pass

        if cmd.lower() in ("exit", "quit", "q"):
            event.app.exit(result=0)
            return

        prompt_line = [("", "\n")]
        prompt_line.extend(_build_prompt_tuples())
        prompt_line.append(("bold", cmd))
        prompt_line.extend(_build_info_tuples())
        prompt_line.append(("", "\n"))
        _append_styled(prompt_line)

        try:
            from kishi.lexer import Tokenizer
            from kishi.expander import Expander
            from kishi.state import ALIASES, BUILTINS, FUNCTIONS, LOCAL_VARS
            import shlex

            tokens = Tokenizer.tokenize(cmd)
            if not tokens:
                return

            cmd_name = tokens[0]

            if cmd_name in ALIASES:
                aliased = shlex.split(ALIASES[cmd_name])
                tokens = aliased + tokens[1:]
                cmd_name = tokens[0]

            expanded = Expander.expand(tokens)
            if not expanded:
                return
            cmd_name = expanded[0]

            cwd = explorer.state.current_dir

            if cmd_name == "cd":
                target = expanded[1] if len(expanded) > 1 else os.environ.get("HOME", "/")
                path = os.path.expanduser(target)
                if not os.path.isabs(path):
                    path = os.path.join(cwd, path)
                os.chdir(path)
                explorer.state.current_dir = os.getcwd()
                explorer.state.refresh()
                explorer.update_preview()
                _append_styled([("ansigreen", f" {os.getcwd()}\n")])
            elif cmd_name == "clear":
                terminal_lines.clear()
            elif cmd_name in BUILTINS:
                _run_builtin(BUILTINS[cmd_name], expanded)
            elif cmd_name in FUNCTIONS:
                from kishi.executor import execute_ast
                for i in range(1, len(expanded)):
                    LOCAL_VARS[str(i)] = expanded[i]
                import io, contextlib
                f = io.StringIO()
                with contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
                    try:
                        execute_ast(FUNCTIONS[cmd_name])
                    except SystemExit:
                        pass
                output = f.getvalue()
                if output:
                    _append_ansi(output)
            else:
                running_process = subprocess.Popen(
                    expanded, cwd=cwd,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    bufsize=0, env={**os.environ, "PYTHONUNBUFFERED": "1", "TERM": "xterm-256color"}
                )

                def read_stdout():
                    while True:
                        try:
                            data = running_process.stdout.read(1024)
                            if not data:
                                if running_process.poll() is not None:
                                    break
                                time.sleep(0.01)
                                continue
                            _append_ansi(data.decode('utf-8', 'replace'))
                            try:
                                app.invalidate()
                            except: pass
                        except Exception:
                            break

                threading.Thread(target=read_stdout, daemon=True).start()

        except Exception as e:
            _append_styled([("ansired", f"Error: {e}\n")])
        
    style = Style.from_dict({
        "header": "bg:#dd4400 #ffffff bold",
        "title": "ansicyan bold",
        "label": "ansigreen bold",
        "bg": "ansidarkgray",
        "invalid": "ansired",
        "input_frame": "ansiyellow bold",
        "command.valid": "ansigreen bold",
        "command.invalid": "ansired bold",
        "string": "ansiyellow",
        "variable": "ansicyan",
        "operator": "ansimagenta",
        "path.invalid": "ansired underline",
    })
    
    app = Application(
        layout=layout,
        key_bindings=combined_kb,
        style=style,
        full_screen=True,
        refresh_interval=2.5,
        mouse_support=True
    )
    
    def update_loop():
        fetch_system_background()
        while app.is_running:
            time.sleep(2.5)
            fetch_system_background()
            try:
                app.invalidate()
            except: pass
            
    threading.Thread(target=update_loop, daemon=True).start()
    
    try:
        import asyncio
        try:
            asyncio.get_running_loop()
            return app.run_async()
        except RuntimeError:
            app.run()
    except Exception as e:
        print(f"Dashboard Error: {e}")
        
    return 0
