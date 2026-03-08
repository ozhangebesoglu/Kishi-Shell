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

def get_gpu_info():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total", "--format=csv,noheader"],
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
    except:
        pass
    return [("class:invalid", "\n N/A\n (nvidia-smi bulunamadı)\n")]

def get_cpu_info():
    text = []
    cpu = psutil.cpu_percent(interval=None)
    text.append(("class:label", " Total: "))
    text.extend(generate_bar(cpu, width=12))
    text.append(("", "\n\n"))
    cores = psutil.cpu_percent(interval=None, percpu=True)
    for i, c in enumerate(cores[:8]):
        text.append(("class:label", f" C{i:<2}: "))
        text.extend(generate_bar(c, width=13))
        text.append(("", "\n"))
    return text

def get_ram_info():
    text = []
    vmem = psutil.virtual_memory()
    text.append(("class:label", " RAM Kullanım:\n "))
    text.extend(generate_bar(vmem.percent, width=18))
    text.append(("", f"\n {vmem.used / (1024**3):.1f} GB / {vmem.total / (1024**3):.1f} GB\n\n"))
    
    swap = psutil.swap_memory()
    text.append(("class:label", " SWAP Kullanım:\n "))
    text.extend(generate_bar(swap.percent, width=18))
    text.append(("", f"\n {swap.used / (1024**3):.1f} GB / {swap.total / (1024**3):.1f} GB\n"))
    
    # "CAVA" placeholder as requested
    text.append(("class:label", "\n 🎵 CAVA (Mock Audio):\n"))
    import random
    text.append(("ansimagenta", " ▂▃▄▅" + "".join(random.choice(" ▂▃▄▅▆▇█") for _ in range(15)) + "\n"))
    return text

last_net = None
def get_net_info():
    global last_net
    text = []
    try:
        disk = psutil.disk_usage('/')
        text.append(("class:label", " Root Disk (/):\n "))
        text.extend(generate_bar(disk.percent, width=18))
        text.append(("", f"\n Free: {disk.free / (1024**3):.1f}GB / {disk.total / (1024**3):.1f}GB\n\n"))
    except: pass
    
    try:
        curr_net = psutil.net_io_counters()
        text.append(("class:label", " Ağ Trafiği (Network):\n"))
        
        down_speed = 0
        up_speed = 0
        if last_net:
            down_speed = (curr_net.bytes_recv - last_net.bytes_recv) / 1024
            up_speed = (curr_net.bytes_sent - last_net.bytes_sent) / 1024
            
        last_net = curr_net
        text.append(("", f" Down:  {down_speed:.1f} KB/s\n"))
        text.append(("", f" Up  :  {up_speed:.1f} KB/s\n\n"))
        text.append(("ansigray", f" Tot. Rx: {curr_net.bytes_recv / (1024**2):.1f} MB\n"))
        text.append(("ansigray", f" Tot. Tx: {curr_net.bytes_sent / (1024**2):.1f} MB\n"))
    except: pass
    return text

def kishi_dashboard(args):
    psutil.cpu_percent(interval=None)
    psutil.cpu_percent(interval=None, percpu=True)
    
    # Sol Paneller (GPU, RAM/CAVA)
    left_col = HSplit([
        Frame(Window(content=FormattedTextControl(text=get_gpu_info)), title="[ GPU ]"),
        Frame(Window(content=FormattedTextControl(text=get_ram_info)), title="[ Memory & CAVA ]")
    ], width=28)
    
    # Sağ Paneller (CPU, DISK/NET)
    right_col = HSplit([
        Frame(Window(content=FormattedTextControl(text=get_cpu_info)), title="[ CPU ]"),
        Frame(Window(content=FormattedTextControl(text=get_net_info)), title="[ Storage & Net ]")
    ], width=28)
    
    # Merkez (Terminal & Input)
    output_buffer = Buffer(multiline=True)
    output_buffer.text = " 🚀 Kishi Shell Dashboard Command Center\n =====================================\n - Normal shell'e dönmek için 'exit' veya 'q' yazın.\n - Komut çalıştırabilirsiniz (Basit read-only komutlar pty gerektirmez).\n\n"
    
    input_buffer = Buffer(multiline=False)
    
    center_col = HSplit([
        Frame(Window(content=BufferControl(buffer=output_buffer, focusable=False), wrap_lines=True), title="[ Kishi Terminal Ekranı ]"),
        Frame(Window(content=BufferControl(buffer=input_buffer), height=1), title="[ Komut Satırı ]", style="class:input_frame")
    ])
    
    body = VSplit([
        left_col,
        center_col,
        right_col
    ])
    
    header = Window(height=1, content=FormattedTextControl(text=[("class:header", " KISHI DASHBOARD 8.0 | [Enter] Komut Çalıştır | [Ctrl+C] Çıkış ")]))
    layout = Layout(HSplit([header, body]), focused_element=input_buffer)
    
    kb = KeyBindings()
    
    @kb.add("c-c")
    def _(event):
        event.app.exit(result=0)
        
    @kb.add("enter")
    def execute_cmd(event):
        cmd = input_buffer.text.strip()
        input_buffer.text = ""
        if not cmd: return
        
        if cmd.lower() in ("exit", "quit", "q"):
            event.app.exit(result=0)
            return
            
        # Append Command
        new_text = output_buffer.text + f"\nKishi$ -> {cmd}\n"
        
        try:
            if cmd.startswith("cd "):
                target = cmd.split(" ", 1)[1]
                path = os.path.expanduser(target)
                os.chdir(path)
                new_text += f"🏠 Dizin değiştirildi: {os.getcwd()}\n"
            elif cmd == "clear":
                new_text = ""
            else:
                out = subprocess.getoutput(cmd)
                new_text += out + "\n"
        except Exception as e:
            new_text += f"Hata: {e}\n"
            
        output_buffer.document = Document(
            text=new_text,
            cursor_position=len(new_text)
        )
        
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
        key_bindings=kb,
        style=style,
        full_screen=True,
        refresh_interval=1.0,
        mouse_support=True
    )
    
    def update_loop():
        while app.is_running:
            time.sleep(1)
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
