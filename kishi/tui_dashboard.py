import os
import io
import pty
import shutil
import signal
import psutil
import threading
import time
import subprocess
import contextlib

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
from prompt_toolkit.layout.containers import (
    Window, HSplit, VSplit, Float, FloatContainer, ConditionalContainer,
)
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.widgets import Frame
from prompt_toolkit.styles import Style
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.filters import has_focus, Condition
from prompt_toolkit.formatted_text import ANSI, to_formatted_text
from prompt_toolkit.layout.processors import BeforeInput
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.data_structures import Point
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

WIDE_THRESHOLD = 120
MEDIUM_THRESHOLD = 80


def _term_cols():
    return shutil.get_terminal_size().columns


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


# ---------------------------------------------------------------------------
# SystemMetrics — thread-safe system metrics collector
# ---------------------------------------------------------------------------

class SystemMetrics:

    def __init__(self):
        self._lock = threading.Lock()
        self._gpu_cache = [("class:invalid", "\n Loading...\n")]
        self._cpu_cache = []
        self._ram_cache = []
        self._net_cache = []
        self._last_net = None

    def fetch_all(self):
        gpu = self._fetch_gpu()
        cpu = self._fetch_cpu()
        ram = self._fetch_ram()
        net = self._fetch_net()
        with self._lock:
            self._gpu_cache = gpu
            self._cpu_cache = cpu
            self._ram_cache = ram
            self._net_cache = net

    def get_gpu(self):
        with self._lock:
            return list(self._gpu_cache)

    def get_cpu(self):
        with self._lock:
            return list(self._cpu_cache)

    def get_ram(self):
        with self._lock:
            return list(self._ram_cache)

    def get_net(self):
        with self._lock:
            return list(self._net_cache)

    def _fetch_gpu(self):
        try:
            out = subprocess.check_output(
                ["nvidia-smi",
                 "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total",
                 "--format=csv,noheader"],
                text=True, stderr=subprocess.DEVNULL
            )
            parts = out.strip().split(", ")
            if len(parts) >= 5:
                return [
                    ("class:title", f" {parts[0][:20]}\n\n"),
                    ("class:label", " Core Temp: "), ("", f"{parts[1]} °C\n"),
                    ("class:label", " GPU Util : "), ("", f"{parts[2]}\n"),
                    ("class:label", " VRAM Used: "), ("", f"{parts[3]}\n"),
                    ("class:label", " VRAM Totl: "), ("", f"{parts[4]}\n"),
                ]
            return [("class:invalid", "\n N/A\n (nvidia-smi not found)\n")]
        except (FileNotFoundError, subprocess.CalledProcessError, OSError):
            return [("class:invalid", "\n N/A\n (nvidia-smi not found)\n")]

    def _fetch_cpu(self):
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
        return c_text

    def _fetch_ram(self):
        r_text = []
        vmem = psutil.virtual_memory()
        r_text.append(("class:label", " RAM Usage:\n "))
        r_text.extend(generate_bar(vmem.percent, width=18))
        r_text.append(("", f"\n {vmem.used / (1024**3):.1f} GB / {vmem.total / (1024**3):.1f} GB\n\n"))

        swap = psutil.swap_memory()
        r_text.append(("class:label", " SWAP Usage:\n "))
        r_text.extend(generate_bar(swap.percent, width=18))
        r_text.append(("", f"\n {swap.used / (1024**3):.1f} GB / {swap.total / (1024**3):.1f} GB\n"))
        return r_text

    def _fetch_net(self):
        n_text = []
        try:
            disk = psutil.disk_usage('/')
            n_text.append(("class:label", " Root Disk (/):\n "))
            n_text.extend(generate_bar(disk.percent, width=18))
            n_text.append(("", f"\n Free: {disk.free / (1024**3):.1f}GB / {disk.total / (1024**3):.1f}GB\n\n"))
        except OSError:
            pass

        try:
            curr_net = psutil.net_io_counters()
            n_text.append(("class:label", " Network Traffic:\n"))

            down_speed = 0
            up_speed = 0
            if self._last_net:
                down_speed = (curr_net.bytes_recv - self._last_net.bytes_recv) / 1024
                up_speed = (curr_net.bytes_sent - self._last_net.bytes_sent) / 1024

            self._last_net = curr_net
            n_text.append(("", f" Down:  {down_speed:.1f} KB/s\n"))
            n_text.append(("", f" Up  :  {up_speed:.1f} KB/s\n\n"))
            n_text.append(("ansigray", f" Tot. Rx: {curr_net.bytes_recv / (1024**2):.1f} MB\n"))
            n_text.append(("ansigray", f" Tot. Tx: {curr_net.bytes_sent / (1024**2):.1f} MB\n"))
        except (OSError, AttributeError, TypeError):
            pass

        return n_text


# ---------------------------------------------------------------------------
# TerminalOutput — thread-safe terminal output buffer with scroll state
# ---------------------------------------------------------------------------

class TerminalOutput:

    MAX_LINES = 300
    TRIM_TO = 200

    def __init__(self):
        self._lock = threading.Lock()
        self._lines = [
            ("class:title", " [KISHI] Dashboard Terminal\n"),
            ("", " =====================================\n"),
            ("ansigray", " Type 'exit' or 'q' to return.\n\n"),
        ]
        self._cursor = Point(0, 0)
        self._user_scrolled = False

    def get_text(self):
        with self._lock:
            return list(self._lines)

    def get_cursor_position(self):
        with self._lock:
            max_y = self._count_newlines()
            if self._cursor.y > max_y:
                self._cursor = Point(0, max_y)
            return self._cursor

    @property
    def user_scrolled(self):
        with self._lock:
            return self._user_scrolled

    @user_scrolled.setter
    def user_scrolled(self, value):
        with self._lock:
            self._user_scrolled = value

    def append_styled(self, tuples):
        with self._lock:
            self._lines.extend(tuples)
            self._trim()
            self._auto_scroll()

    def append_ansi(self, text):
        with self._lock:
            try:
                parsed = to_formatted_text(ANSI(text))
                self._lines.extend(parsed)
            except Exception:
                self._lines.append(("", str(text)))
            self._trim()
            self._auto_scroll()

    def clear(self):
        with self._lock:
            self._lines.clear()
            self._cursor = Point(0, 0)
            self._user_scrolled = False

    def scroll(self, delta):
        with self._lock:
            max_y = self._count_newlines()
            new_y = max(0, min(self._cursor.y + delta, max_y))
            self._cursor = Point(0, new_y)
            self._user_scrolled = new_y < max_y

    def scroll_to_bottom(self):
        with self._lock:
            self._user_scrolled = False
            self._cursor = Point(0, self._count_newlines())

    def scroll_to_top(self):
        with self._lock:
            self._cursor = Point(0, 0)
            self._user_scrolled = True

    def _count_newlines(self):
        return sum(t[1].count('\n') for t in self._lines)

    def _trim(self):
        line_count = self._count_newlines()
        if line_count <= self.MAX_LINES:
            return
        target = line_count - self.TRIM_TO
        removed = 0
        for i, (_, text) in enumerate(self._lines):
            removed += text.count('\n')
            if removed >= target:
                self._lines[:] = self._lines[i + 1:]
                break

    def _auto_scroll(self):
        if not self._user_scrolled:
            self._cursor = Point(0, self._count_newlines())


# ---------------------------------------------------------------------------
# CommandExecutor — command parsing, builtin dispatch, subprocess management
# ---------------------------------------------------------------------------

class CommandExecutor:

    def __init__(self, output, explorer):
        self._lock = threading.Lock()
        self._process = None
        self._master_fd = None
        self._output = output
        self._explorer = explorer

    @property
    def is_running(self):
        with self._lock:
            return self._process is not None and self._process.poll() is None

    @property
    def process(self):
        with self._lock:
            return self._process

    def send_input(self, text):
        with self._lock:
            proc = self._process
            master_fd = self._master_fd
        if proc and proc.poll() is None and master_fd is not None:
            try:
                os.write(master_fd, (text + "\n").encode('utf-8'))
                return True
            except (OSError, BrokenPipeError):
                return False
        return False

    def interrupt(self):
        with self._lock:
            proc = self._process
            master_fd = self._master_fd
        if proc and proc.poll() is None:
            try:
                if master_fd is not None:
                    os.write(master_fd, b'\x03')
                else:
                    proc.send_signal(signal.SIGINT)
            except (OSError, ProcessLookupError):
                proc.kill()
            self._output.append_styled([("ansired bold", "\n^C\n")])
            with self._lock:
                self._process = None

    def kill(self):
        with self._lock:
            if self._process and self._process.poll() is None:
                self._process.kill()

    def execute(self, cmd, app):
        if self.is_running:
            self.send_input(cmd)
            return None

        if not cmd:
            return None

        self._output.user_scrolled = False

        if cmd.lower() in ("exit", "quit", "q"):
            return "exit"

        prompt_line = [("", "\n")]
        prompt_line.extend(_build_prompt_tuples())
        prompt_line.append(("bold", cmd))
        prompt_line.extend(_build_info_tuples())
        prompt_line.append(("", "\n"))
        self._output.append_styled(prompt_line)

        try:
            from kishi.lexer import Tokenizer
            from kishi.expander import Expander
            from kishi.state import ALIASES, BUILTINS, FUNCTIONS, LOCAL_VARS
            import shlex

            tokens = Tokenizer.tokenize(cmd)
            if not tokens:
                return None

            cmd_name = tokens[0]

            if cmd_name in ALIASES:
                aliased = shlex.split(ALIASES[cmd_name])
                tokens = aliased + tokens[1:]
                cmd_name = tokens[0]

            expanded = Expander.expand(tokens)
            if not expanded:
                return None
            cmd_name = expanded[0]

            cwd = self._explorer.state.current_dir

            if cmd_name == "cd":
                target = expanded[1] if len(expanded) > 1 else os.environ.get("HOME", "/")
                path = os.path.expanduser(target)
                if not os.path.isabs(path):
                    path = os.path.join(cwd, path)
                os.chdir(path)
                self._explorer.state.current_dir = os.getcwd()
                self._explorer.state.refresh()
                self._explorer.update_preview()
                self._output.append_styled([("ansigreen", f" {os.getcwd()}\n")])
            elif cmd_name == "clear":
                self._output.clear()
            elif cmd_name in BUILTINS:
                self._run_builtin(BUILTINS[cmd_name], expanded)
                self._explorer.state.refresh()
                self._explorer.update_preview()
            elif cmd_name in FUNCTIONS:
                self._run_function(FUNCTIONS[cmd_name], expanded, LOCAL_VARS)
                self._explorer.state.refresh()
                self._explorer.update_preview()
            else:
                self._spawn_external(expanded, cwd, app)

        except Exception as e:
            self._output.append_styled([("ansired", f"Error: {e}\n")])

        return None

    def _run_builtin(self, builtin_func, builtin_args):
        f = io.StringIO()
        with contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
            try:
                builtin_func(builtin_args)
            except SystemExit:
                pass
        output = f.getvalue()
        if output:
            self._output.append_ansi(output)

    def _run_function(self, func_ast, expanded, local_vars):
        from kishi.executor import execute_ast
        for i in range(1, len(expanded)):
            local_vars[str(i)] = expanded[i]
        f = io.StringIO()
        with contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
            try:
                execute_ast(func_ast)
            except SystemExit:
                pass
        output = f.getvalue()
        if output:
            self._output.append_ansi(output)

    def _spawn_external(self, expanded, cwd, app):
        master_fd, slave_fd = pty.openpty()

        proc = subprocess.Popen(
            expanded, cwd=cwd,
            stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
            preexec_fn=os.setsid,
            close_fds=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1", "TERM": "xterm-256color"},
        )
        os.close(slave_fd)

        with self._lock:
            self._process = proc
            self._master_fd = master_fd

        def read_pty():
            try:
                while proc.poll() is None:
                    try:
                        data = os.read(master_fd, 4096)
                        if not data:
                            break
                        self._output.append_ansi(data.decode('utf-8', 'replace'))
                        try:
                            app.invalidate()
                        except RuntimeError:
                            pass
                    except OSError:
                        break
            finally:
                try:
                    os.close(master_fd)
                except OSError:
                    pass
                with self._lock:
                    self._process = None
                    self._master_fd = None
                self._explorer.state.refresh()
                self._explorer.update_preview()
                try:
                    app.invalidate()
                except RuntimeError:
                    pass

        threading.Thread(target=read_pty, daemon=True).start()


# ---------------------------------------------------------------------------
# DashboardState — pure state container (no prompt_toolkit imports)
# ---------------------------------------------------------------------------

class DashboardState:

    def __init__(self):
        self.metrics = SystemMetrics()
        self.output = TerminalOutput()
        self.show_explorer = False
        self.rsearch = {"matches": [], "idx": 0, "updating": False}


# ---------------------------------------------------------------------------
# DashboardUI — view + controller
# ---------------------------------------------------------------------------

class DashboardUI:

    def __init__(self, args):
        self.state = DashboardState()

        from kishi.tui_explorer import ExplorerUI
        self.explorer = ExplorerUI(os.getcwd(), standalone=False)
        self.executor = CommandExecutor(self.state.output, self.explorer)

        from kishi.ui import KishiCompleter, KishiLexer

        history_file = os.path.join(os.environ.get("HOME", "/"), ".kishi_history")
        self._history_file = history_file
        self.input_buffer = Buffer(
            multiline=False,
            completer=KishiCompleter(),
            complete_while_typing=True,
            history=FileHistory(history_file),
            auto_suggest=AutoSuggestFromHistory(),
            enable_history_search=True,
        )
        self.input_buffer.on_text_changed += self._reset_rsearch

        self.kb = KeyBindings()
        self._kishi_lexer = KishiLexer()
        self._setup_layout()
        self._setup_key_bindings()

    def run(self):
        self._start_background_threads()
        try:
            import asyncio
            try:
                asyncio.get_running_loop()
                return self.app.run_async()
            except RuntimeError:
                self.app.run()
        except (EOFError, KeyboardInterrupt):
            pass
        except Exception as e:
            print(f"Dashboard Error: {e}")
        return 0

    # -- Layout ----------------------------------------------------------------

    def _setup_layout(self):
        metrics = self.state.metrics

        left_col = HSplit([
            Frame(Window(content=FormattedTextControl(text=metrics.get_gpu)), title="[ GPU ]"),
            Frame(Window(content=FormattedTextControl(text=metrics.get_ram)), title="[ Memory & Swap ]")
        ], width=28)

        right_col = HSplit([
            Frame(Window(content=FormattedTextControl(text=metrics.get_cpu)), title="[ CPU ]"),
            Frame(Window(content=FormattedTextControl(text=metrics.get_net)), title="[ Storage & Net ]")
        ], width=28)

        is_wide = Condition(lambda: _term_cols() >= WIDE_THRESHOLD)
        is_medium = Condition(lambda: MEDIUM_THRESHOLD <= _term_cols() < WIDE_THRESHOLD)

        left_visible = ConditionalContainer(content=left_col, filter=is_wide)
        right_visible = ConditionalContainer(content=right_col, filter=is_wide)

        compact_bar = ConditionalContainer(
            content=Window(
                height=1,
                content=FormattedTextControl(text=self._get_compact_sysinfo),
                style="class:compact_bar",
            ),
            filter=is_medium,
        )

        output = self.state.output
        self.out_control = FormattedTextControl(
            text=output.get_text,
            focusable=True,
            show_cursor=False,
            get_cursor_position=output.get_cursor_position,
        )

        self.out_win = Window(
            content=self.out_control,
            wrap_lines=True,
            right_margins=[ScrollbarMargin(display_arrows=True)],
            cursorline=False,
        )

        in_control = BufferControl(
            buffer=self.input_buffer,
            input_processors=[BeforeInput(_build_prompt_tuples)],
            lexer=self._kishi_lexer,
        )
        self.in_win = Window(content=in_control, height=1)

        explorer_col = ConditionalContainer(
            content=Frame(self.explorer.container, title="[ IDE Explorer ]"),
            filter=Condition(lambda: self.state.show_explorer)
        )

        center_col = HSplit([
            explorer_col,
            Frame(self.out_win, title="[ Kishi Terminal ]"),
            Frame(self.in_win, title="[ Command Line ]", style="class:input_frame"),
            compact_bar,
        ])

        body = VSplit([left_visible, center_col, right_visible])

        header = Window(height=1, content=FormattedTextControl(text=self._get_header_text))

        root = FloatContainer(
            content=HSplit([header, body]),
            floats=[Float(
                xcursor=True, ycursor=True,
                allow_cover_cursor=True,
                content=CompletionsMenu(max_height=10, scroll_offset=1),
            )]
        )
        self.layout = Layout(root, focused_element=self.in_win)

        style = Style.from_dict({
            "header": "bg:#dd4400 #ffffff bold",
            "compact_bar": "bg:#333333 #aaaaaa",
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

        combined_kb = merge_key_bindings([self.kb, self.explorer.kb])

        self.app = Application(
            layout=self.layout,
            key_bindings=combined_kb,
            style=style,
            full_screen=True,
            refresh_interval=2.5,
            mouse_support=True,
        )

    def _get_header_text(self):
        cols = _term_cols()
        if cols >= WIDE_THRESHOLD:
            return [("class:header", " KISHI DASHBOARD 8.0 | [Enter] Run | [Tab] Complete | [PgUp/PgDn] Scroll | [Shift+Tab] Switch | [Ctrl+E] Explorer | [Ctrl+R] Search | [Ctrl+Q] Quit ")]
        if cols >= MEDIUM_THRESHOLD:
            return [("class:header", " KISHI 8.0 | [Enter] Run | [Tab] Complete | [PgUp/PgDn] Scroll | [Ctrl+E] Explorer | [Ctrl+Q] Quit ")]
        return [("class:header", " KISHI 8.0 | [Ctrl+Q] Quit ")]

    def _get_compact_sysinfo(self):
        try:
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            return [
                ("class:header",
                 f" CPU: {cpu:.0f}%"
                 f" | RAM: {mem.used/(1024**3):.1f}/{mem.total/(1024**3):.0f}G ({mem.percent:.0f}%)"
                 f" | Disk: {disk.free/(1024**3):.0f}G free"
                 f" ")
            ]
        except Exception:
            return [("class:header", " System info unavailable ")]

    # -- Key Bindings ----------------------------------------------------------

    def _setup_key_bindings(self):
        kb = self.kb

        @kb.add("c-q")
        def on_ctrl_q(event):
            self.executor.kill()
            event.app.exit(result=0)

        @kb.add("c-c")
        def on_ctrl_c(event):
            self.executor.interrupt()

        @kb.add("c-e")
        def on_ctrl_e(event):
            if not self.state.show_explorer:
                self.state.show_explorer = True
                self.layout.focus(self.explorer.left_window)
            else:
                if self.layout.has_focus(self.explorer.left_window):
                    self.state.show_explorer = False
                    self.layout.focus(self.in_win)
                else:
                    self.layout.focus(self.explorer.left_window)

        @kb.add("s-tab")
        def on_shift_tab(event):
            if self.layout.has_focus(self.in_win):
                self.layout.focus(self.out_win)
            elif self.layout.has_focus(self.out_win):
                if self.state.show_explorer:
                    self.layout.focus(self.explorer.left_window)
                else:
                    self.layout.focus(self.in_win)
            elif self.layout.has_focus(self.explorer.left_window):
                self.layout.focus(self.explorer.right_window)
            elif self.layout.has_focus(self.explorer.right_window):
                self.layout.focus(self.in_win)
            else:
                self.layout.focus(self.in_win)

        @kb.add("c-r", filter=has_focus(self.input_buffer))
        def on_ctrl_r(event):
            st = self.state.rsearch
            if st["matches"]:
                st["idx"] = (st["idx"] + 1) % len(st["matches"])
                st["updating"] = True
                self.input_buffer.text = st["matches"][st["idx"]]
                self.input_buffer.cursor_position = len(self.input_buffer.text)
                st["updating"] = False
                return

            query = self.input_buffer.text.strip().lower()
            unique = self._load_history_commands()
            if query:
                matches = [c for c in unique if query in c.lower()]
            else:
                matches = unique

            if matches:
                st["matches"] = matches
                st["idx"] = 0
                st["updating"] = True
                self.input_buffer.text = matches[0]
                self.input_buffer.cursor_position = len(self.input_buffer.text)
                st["updating"] = False

        @kb.add("up", filter=has_focus(self.out_control))
        def on_scroll_up(event):
            self.state.output.scroll(-3)

        @kb.add("down", filter=has_focus(self.out_control))
        def on_scroll_down(event):
            self.state.output.scroll(3)

        @kb.add("pageup")
        def on_page_up(event):
            self.state.output.scroll(-15)

        @kb.add("pagedown")
        def on_page_down(event):
            self.state.output.scroll(15)

        @kb.add("end")
        def on_end(event):
            self.state.output.scroll_to_bottom()

        @kb.add("home")
        def on_home(event):
            self.state.output.scroll_to_top()

        @kb.add("enter", filter=has_focus(self.input_buffer))
        def on_enter(event):
            cmd = self.input_buffer.text.strip()
            self.input_buffer.text = ""

            try:
                self.input_buffer.history.store_string(cmd)
            except Exception:
                pass

            result = self.executor.execute(cmd, event.app)
            if result == "exit":
                event.app.exit(result=0)

    # -- Background ------------------------------------------------------------

    def _start_background_threads(self):
        threading.Thread(target=self._update_loop, daemon=True).start()

    def _update_loop(self):
        self.state.metrics.fetch_all()
        while self.app.is_running:
            time.sleep(2.5)
            self.state.metrics.fetch_all()
            try:
                self.app.invalidate()
            except RuntimeError:
                pass

    # -- Helpers ---------------------------------------------------------------

    def _reset_rsearch(self, buff):
        if not self.state.rsearch["updating"]:
            self.state.rsearch["matches"] = []
            self.state.rsearch["idx"] = 0

    def _load_history_commands(self):
        if not os.path.exists(self._history_file):
            return []
        try:
            with open(self._history_file, "r") as f:
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


# ---------------------------------------------------------------------------
# Public API — preserved entry point
# ---------------------------------------------------------------------------

def kishi_dashboard(args):
    psutil.cpu_percent(interval=None)
    psutil.cpu_percent(interval=None, percpu=True)
    ui = DashboardUI(args)
    return ui.run()
