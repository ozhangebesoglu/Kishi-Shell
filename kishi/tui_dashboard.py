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

def kishi_dashboard(args):
    psutil.cpu_percent(interval=None)
    psutil.cpu_percent(interval=None, percpu=True)
    
    # Left panels (GPU, RAM)
    left_col = HSplit([
        Frame(Window(content=FormattedTextControl(text=get_gpu_info)), title="[ GPU ]"),
        Frame(Window(content=FormattedTextControl(text=get_ram_info)), title="[ Memory & Swap ]")
    ], width=28)
    
    # Right panels (CPU, DISK/NET)
    right_col = HSplit([
        Frame(Window(content=FormattedTextControl(text=get_cpu_info)), title="[ CPU ]"),
        Frame(Window(content=FormattedTextControl(text=get_net_info)), title="[ Storage & Net ]")
    ], width=28)
    
    from kishi.tui_explorer import ExplorerUI
    from prompt_toolkit.layout.containers import ConditionalContainer
    from prompt_toolkit.filters import Condition
    from prompt_toolkit.key_binding import merge_key_bindings

    output_buffer = Buffer(multiline=True)
    output_buffer.text = " [KISHI] Kishi Shell Dashboard Command Center\n =====================================\n - Type 'exit' or 'q' to return to normal shell.\n - You can execute fast read-only commands here.\n\n"
    
    input_buffer = Buffer(multiline=False)

    show_explorer = False
    explorer = ExplorerUI(os.getcwd(), standalone=False)
    running_process = None
    
    out_win = Window(content=BufferControl(buffer=output_buffer, focusable=True), wrap_lines=True, right_margins=[ScrollbarMargin(display_arrows=True)], always_hide_cursor=True)
    in_win = Window(content=BufferControl(buffer=input_buffer), height=1)

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
    
    header = Window(height=1, content=FormattedTextControl(text=[("class:header", " KISHI DASHBOARD 8.0 | [Enter] Execute | [Tab] Switch | [Ctrl+E] Explorer | [Ctrl+C] Quit ")]))
    layout = Layout(HSplit([header, body]), focused_element=in_win)
    
    kb = KeyBindings()
    
    @kb.add("c-c")
    def _(event):
        event.app.exit(result=0)
        
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

    @kb.add("tab")
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
            
    # Include explorer's standalone keybindings cleanly.
    combined_kb = merge_key_bindings([kb, explorer.kb])
            
    @kb.add("enter", filter=has_focus(input_buffer))
    def execute_cmd(event):
        nonlocal running_process
        cmd = input_buffer.text.strip()
        input_buffer.text = ""
        
        # If a process is already interactive, forward input to its stdin
        if running_process and running_process.poll() is None:
            try:
                # Write to unbuffered binary pipe
                running_process.stdin.write((cmd + "\n").encode('utf-8'))
                running_process.stdin.flush()
                # Echo the user's input directly into the terminal
                new_text = output_buffer.text + f"{cmd}\n"
                output_buffer.document = Document(text=new_text, cursor_position=len(new_text))
            except Exception as e:
                pass
            return

        if not cmd: return
        
        if cmd.lower() in ("exit", "quit", "q"):
            event.app.exit(result=0)
            return
            
        # Append Command
        new_text = output_buffer.text + f"\nKishi$ -> {cmd}\n"
        output_buffer.document = Document(text=new_text, cursor_position=len(new_text))
        
        try:
            cwd = explorer.state.current_dir
            if cmd.startswith("cd "):
                target = cmd.split(" ", 1)[1]
                path = os.path.expanduser(target)
                if not os.path.isabs(path):
                    path = os.path.join(cwd, path)
                os.chdir(path)
                explorer.state.current_dir = os.getcwd()
                explorer.state.refresh()
                explorer.update_preview()
                new_text = output_buffer.text + f"[DIR] Changed to: {os.getcwd()}\n"
                output_buffer.document = Document(text=new_text, cursor_position=len(new_text))
            elif cmd == "clear":
                output_buffer.text = ""
            else:
                # Launch custom background interactive process. Use bufsize=0 to force unbuffered binary streaming
                running_process = subprocess.Popen(
                    cmd, shell=True, cwd=cwd,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    bufsize=0, env={**os.environ, "PYTHONUNBUFFERED": "1"}
                )
                
                # Setup daemon thread to stream output back to the UI
                def read_stdout():
                    while True:
                        try:
                            # Read any chunk up to 1024 without waiting for \n
                            data = running_process.stdout.read(1024)
                            if not data:
                                if running_process.poll() is not None:
                                    break
                                time.sleep(0.01)
                                continue
                                
                            text = data.decode('utf-8', 'replace')
                            current_text = output_buffer.text
                            lines = (current_text + text).split('\n')
                            if len(lines) > 200:
                                current_text = "\n".join(lines[-200:])
                            else:
                                current_text = current_text + text
                                
                            output_buffer.document = Document(text=current_text, cursor_position=len(current_text))
                            try:
                                app.invalidate()
                            except: pass
                        except Exception:
                            break
                            
                threading.Thread(target=read_stdout, daemon=True).start()
                
        except Exception as e:
            new_text = output_buffer.text + f"Error: {e}\n"
            output_buffer.document = Document(text=new_text, cursor_position=len(new_text))
        
    style = Style.from_dict({
        "header": "bg:#dd4400 #ffffff bold",
        "title": "ansicyan bold",
        "label": "ansigreen bold",
        "bg": "ansidarkgray",
        "invalid": "ansired",
        "input_frame": "ansiyellow bold",
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
