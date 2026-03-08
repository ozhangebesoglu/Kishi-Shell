import os
from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import Window, VSplit, HSplit
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.styles import Style
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import has_focus
from prompt_toolkit.document import Document
from prompt_toolkit.layout.margins import NumberedMargin
from prompt_toolkit.enums import EditingMode

def get_explorer_icon(path, filename):
    if os.path.isdir(path): return "📁"
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".py": return "🐍"
    if ext == ".go": return "🐹"
    if ext in (".js", ".ts", ".jsx", ".tsx"): return "📜"
    if ext in (".txt", ".md", ".json", ".yaml", ".yml", ".ini", ".cfg"): return "📝"
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".bmp"): return "🖼️"
    if ext in (".mp3", ".wav", ".ogg", ".flac"): return "🎵"
    if ext in (".mp4", ".mkv", ".avi", ".webm"): return "🎥"
    if ext in (".zip", ".tar", ".gz", ".rar", ".7z"): return "📦"
    return "📄"

class KishiExplorer:
    def __init__(self, start_dir=".", editor_buffer=None):
        self.current_dir = os.path.abspath(start_dir)
        self.files = []
        self.selected_index = 0
        self.editor_buffer = editor_buffer
        self.current_file_path = None
        self.status_msg = ""
        self.refresh_files()
        
    def refresh_files(self):
        try:
            items = [item for item in os.listdir(self.current_dir) if not item.startswith('.')]
            # Dizinler üstte, dosyalar altta olacak şekilde sırala
            self.files = [".."] + sorted(items, key=lambda x: (not os.path.isdir(os.path.join(self.current_dir, x)), x.lower()))
        except Exception:
            self.files = [".."]
            
        if self.selected_index >= len(self.files):
            self.selected_index = max(0, len(self.files) - 1)
        self.update_preview()
        
    def set_buffer_text(self, text):
        if self.editor_buffer:
            self.editor_buffer.document = Document(text=text, cursor_position=0)

    def update_preview(self):
        self.current_file_path = None
        self.status_msg = ""
        if not self.files:
            self.set_buffer_text("Directory is empty.")
            return
            
        selected_file = self.files[self.selected_index]
        if selected_file == "..":
            self.set_buffer_text("Action: Go to Parent Directory\nShortcut: [Backspace] or [Left Arrow]")
            return
            
        path = os.path.join(self.current_dir, selected_file)
        
        if os.path.isdir(path):
            try:
                items = os.listdir(path)
                preview = f"Folder Contents ({len(items)} items):\n\n"
                for item in items[:50]:
                    icon = get_explorer_icon(os.path.join(path, item), item)
                    preview += f" {icon} {item}\n"
                if len(items) > 50:
                    preview += f"\n... and {len(items)-50} more files."
                self.set_buffer_text(preview)
            except Exception as e:
                self.set_buffer_text(f"Access denied: {e}")
        else:
            try:
                size_mb = os.path.getsize(path) / (1024 * 1024)
                if size_mb > 2.0:
                    self.set_buffer_text(f"File is too large ({size_mb:.1f} MB).\n\nEditor preview disabled for performance.")
                else:
                    with open(path, 'r', encoding='utf-8') as f:
                        self.set_buffer_text(f.read())
                    self.current_file_path = path
            except UnicodeDecodeError:
                self.set_buffer_text("Binary file.\nEditor preview is not supported.")
            except Exception as e:
                self.set_buffer_text(f"Cannot read file: {e}")

    def save_current_file(self):
        if self.current_file_path and self.editor_buffer:
            try:
                with open(self.current_file_path, 'w', encoding='utf-8') as f:
                    f.write(self.editor_buffer.text)
                self.status_msg = f"[OK] {os.path.basename(self.current_file_path)} Saved!"
                return True
            except Exception as e:
                self.status_msg = f"[ERR] Save Error: {e}"
                return False
        self.status_msg = "[ERR] No text document to save."
        return False

    def get_left_text(self):
        result = [("class:title", f" 📂 {self.current_dir}\n")]
        result.append(("class:line", "=" * 45 + "\n"))
        
        # Sayfalama mantığı (Ekrana sığmayanlar için kaydırma)
        # Terminal yüksekliğini 30 satır varsayalım
        start_idx = max(0, self.selected_index - 15)
        end_idx = min(len(self.files), start_idx + 30)
        
        if start_idx > 0:
            result.append(("class:dir", "   ... (more items above)\n"))
            
        for i in range(start_idx, end_idx):
            f = self.files[i]
            prefix = " > " if i == self.selected_index else "   "
            style = "class:selected" if i == self.selected_index else ""
            
            if f == "..":
                icon = "🔙 "
            else:
                icon = get_explorer_icon(os.path.join(self.current_dir, f), f) + " "
            
            if style:
                result.append((style, prefix + icon + f + "\n"))
            else:
                if "📁" in icon or "🔙" in icon:
                    result.append(("class:dir", prefix + icon + f + "\n"))
                else:
                    result.append(("", prefix + icon + f + "\n"))
                    
        if end_idx < len(self.files):
            result.append(("class:dir", "   ... (more items below)\n"))
            
        return result

def kishi_explore(args):
    start_dir = os.getcwd() if len(args) < 2 else args[1]
    
    editor_buffer = Buffer(multiline=True)
    explorer = KishiExplorer(start_dir, editor_buffer)
    
    left_control = FormattedTextControl(text=explorer.get_left_text, focusable=True)
    left_window = Window(content=left_control, wrap_lines=False, width=45)
    
    right_window = Window(
        content=BufferControl(buffer=editor_buffer, focusable=True), 
        wrap_lines=True,
        left_margins=[NumberedMargin(display_tildes=True)]
    )
    
    body = VSplit([
        left_window,
        Window(width=1, char='│', style='class:line'),
        right_window
    ])
    
    def get_header():
        text = " Kishi IDE Explorer | [Up/Down] Navigate | [Tab/Esc] Switch Panel | [Ctrl+S] Save | [Space] Load Directory | [Q] Quit "
        if explorer.status_msg:
            return [("class:header", text + f" | [*] {explorer.status_msg} ")]
        return [("class:header", text)]
        
    header = Window(height=1, content=FormattedTextControl(text=get_header))
    
    layout = Layout(HSplit([header, body]), focused_element=left_window)
    
    kb = KeyBindings()
    left_focused = has_focus(left_window)
    
    @kb.add("q", filter=left_focused)
    @kb.add("Q", filter=left_focused)
    @kb.add("c-c")
    def exit_app(event):
        event.app.exit()
        
    @kb.add("tab")
    @kb.add("escape")
    def toggle_focus(event):
        if layout.has_focus(left_window):
            layout.focus(right_window)
        else:
            layout.focus(left_window)
            
    @kb.add("c-s")
    def save_file(event):
        explorer.save_current_file()
        
    @kb.add("up", filter=left_focused)
    def move_up(event):
        if explorer.selected_index > 0:
            explorer.selected_index -= 1
            explorer.update_preview()
            
    @kb.add("down", filter=left_focused)
    def move_down(event):
        if explorer.selected_index < len(explorer.files) - 1:
            explorer.selected_index += 1
            explorer.update_preview()
            
    @kb.add("enter", filter=left_focused)
    @kb.add("right", filter=left_focused)
    def enter_dir(event):
        if explorer.files:
            selected = explorer.files[explorer.selected_index]
            if selected == "..":
                go_back(event)
                return
                
            path = os.path.join(explorer.current_dir, selected)
            if os.path.isdir(path):
                explorer.current_dir = os.path.abspath(path)
                explorer.selected_index = 0
                explorer.refresh_files()
            else:
                # Dosya seçildi, editöre geç
                layout.focus(right_window)
                
    @kb.add("backspace", filter=left_focused)
    @kb.add("left", filter=left_focused)
    def go_back(event):
        parent = os.path.dirname(explorer.current_dir)
        if parent != explorer.current_dir:
            explorer.current_dir = parent
            explorer.selected_index = 0
            explorer.refresh_files()
            
    @kb.add("space", filter=left_focused)
    def select_and_exit(event):
        os.chdir(explorer.current_dir)
        event.app.exit()
            
    style = Style.from_dict({
        "header": "bg:#00aa00 #ffffff bold",
        "title": "ansicyan bold",
        "selected": "bg:#0055aa #ffffff bold",
        "dir": "ansiblue bold",
        "line": "ansidarkgray"
    })
    
    app = Application(
        layout=layout,
        key_bindings=kb,
        style=style,
        full_screen=True,
        editing_mode=EditingMode.EMACS
    )
    
    try:
        import asyncio
        try:
            asyncio.get_running_loop()
            return app.run_async()
        except RuntimeError:
            app.run()
    except Exception as e:
        print(f"Explorer Error: {e}")
        
    return 0
