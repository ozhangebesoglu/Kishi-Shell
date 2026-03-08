import os
import psutil
import threading
import time

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import Window, HSplit
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.styles import Style

def generate_bar(percentage, width=40):
    filled = int(width * percentage / 100)
    empty = width - filled
    
    color = "ansicyan"
    if percentage > 85:
        color = "ansired"
    elif percentage > 60:
        color = "ansiyellow"
        
    return [
        (color, "█" * filled),
        ("class:bg", "░" * empty),
        ("", f" {percentage:5.1f}%")
    ]

def get_sys_info():
    text = []
    
    # Header
    text.append(("class:title", " 📊 Kishi Shell | System Dashboard (TUI Monitor)\n"))
    text.append(("", " =================================================\n"))
    text.append(("class:help", " [Press 'q' or 'Ctrl+C' to Exit]\n\n"))
    
    # CPU
    cpu_percent = psutil.cpu_percent(interval=None)
    text.append(("class:label", " CPU Total:  "))
    text.extend(generate_bar(cpu_percent))
    text.append(("", "\n"))
    
    # Per-core
    cores = psutil.cpu_percent(interval=None, percpu=True)
    # Print max 8 cores to save vertical space if many cores exist
    for i, core_pct in enumerate(cores[:16]):
        text.append(("", f"  Core {i:<2}:  "))
        text.extend(generate_bar(core_pct, width=20))
        if i % 2 == 1:
            text.append(("", "\n"))
        else:
            text.append(("", "   |  "))
    if len(cores) % 2 != 0 or len(cores) > 16:
        text.append(("", "\n"))
        
    text.append(("", "\n"))
    
    # RAM
    vmem = psutil.virtual_memory()
    text.append(("class:label", " RAM Used:   "))
    text.extend(generate_bar(vmem.percent))
    text.append(("", f"  ({vmem.used / (1024**3):.1f}GB / {vmem.total / (1024**3):.1f}GB)\n\n"))
    
    # Swap
    swap = psutil.swap_memory()
    text.append(("class:label", " Swap Used:  "))
    text.extend(generate_bar(swap.percent))
    text.append(("", f"  ({swap.used / (1024**3):.1f}GB / {swap.total / (1024**3):.1f}GB)\n\n"))
    
    # Disk
    try:
        disk = psutil.disk_usage('/')
        text.append(("class:label", " Root Disk:  "))
        text.extend(generate_bar(disk.percent))
        text.append(("", f"  ({disk.used / (1024**3):.1f}GB / {disk.total / (1024**3):.1f}GB)\n\n"))
    except: pass
    
    # Network
    try:
        net = psutil.net_io_counters()
        text.append(("class:label", " Network IO: "))
        text.append(("", f" Sent: {net.bytes_sent / (1024**2):.1f}MB | Recv: {net.bytes_recv / (1024**2):.1f}MB\n\n"))
    except: pass
    
    return text

def kishi_dashboard(args):
    # Initialize CPU stat
    psutil.cpu_percent(interval=None)
    psutil.cpu_percent(interval=None, percpu=True)
    
    text_control = FormattedTextControl(text=get_sys_info)
    window = Window(content=text_control)
    layout = Layout(HSplit([window]))
    
    kb = KeyBindings()
    
    @kb.add("q")
    @kb.add("Q")
    @kb.add("c-c")
    def _(event):
        event.app.exit()
        
    style = Style.from_dict({
        "title": "ansicyan bold",
        "help": "ansiyellow",
        "label": "ansigreen bold",
        "bg": "ansidarkgray"
    })
    
    app = Application(
        layout=layout,
        key_bindings=kb,
        style=style,
        full_screen=True,
        refresh_interval=1.0  # Tells the event loop to redraw periodically!
    )
    
    # Fallback thread for async invalidation just in case
    def update_loop():
        while app.is_running:
            time.sleep(1)
            try:
                app.invalidate()
            except:
                pass
            
    threading.Thread(target=update_loop, daemon=True).start()
    
    try:
        app.run()
    except Exception as e:
        print(f"Dashboard Error: {e}")
        
    return 0
