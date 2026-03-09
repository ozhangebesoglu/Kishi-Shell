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

class IconProvider:
    """Provides UI icons based on file extensions (Open/Closed Principle)."""
    ICONS = {
        ".py": "🐍",
        ".go": "🐹",
        ".js": "📜", ".ts": "📜", ".jsx": "📜", ".tsx": "📜",
        ".txt": "📝", ".md": "📝", ".json": "📝", ".yaml": "📝", ".yml": "📝", ".ini": "📝", ".cfg": "📝",
        ".png": "🖼️", ".jpg": "🖼️", ".jpeg": "🖼️", ".gif": "🖼️", ".svg": "🖼️", ".bmp": "🖼️",
        ".mp3": "🎵", ".wav": "🎵", ".ogg": "🎵", ".flac": "🎵",
        ".mp4": "🎥", ".mkv": "🎥", ".avi": "🎥", ".webm": "🎥",
        ".zip": "📦", ".tar": "📦", ".gz": "📦", ".rar": "📦", ".7z": "📦"
    }

    @staticmethod
    def get_icon(path, filename):
        if os.path.isdir(path):
            return "📁"
        ext = os.path.splitext(filename)[1].lower()
        return IconProvider.ICONS.get(ext, "📄")

class FileSystemProvider:
    """Handles all OS level file operations (Single Responsibility Principle)."""
    @staticmethod
    def list_directory(directory):
        try:
            items = [item for item in os.listdir(directory) if not item.startswith('.')]
            return [".."] + sorted(items, key=lambda x: (not os.path.isdir(os.path.join(directory, x)), x.lower()))
        except Exception:
            return [".."]

    @staticmethod
    def format_directory_contents(path):
        try:
            items = os.listdir(path)
            preview = f"Folder Contents ({len(items)} items):\n\n"
            for item in items[:50]:
                icon = IconProvider.get_icon(os.path.join(path, item), item)
                preview += f" {icon} {item}\n"
            if len(items) > 50:
                preview += f"\n... and {len(items)-50} more files."
            return preview
        except Exception as e:
            return f"Access denied: {e}"

    @staticmethod
    def read_file(path):
        try:
            size_mb = os.path.getsize(path) / (1024 * 1024)
            if size_mb > 2.0:
                return f"File is too large ({size_mb:.1f} MB).\n\nEditor preview disabled for performance.", False
            with open(path, 'r', encoding='utf-8') as f:
                return f.read(), True
        except UnicodeDecodeError:
            return "Binary file.\nEditor preview is not supported.", False
        except Exception as e:
            return f"Cannot read file: {e}", False

    @staticmethod
    def write_file(path, content):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True, f"[OK] {os.path.basename(path)} Saved!"
        except Exception as e:
            return False, f"[ERR] Save Error: {e}"

class ExplorerState:
    """Maintains the purely logical state of the explorer decoupled from GUI."""
    def __init__(self, start_dir):
        self.current_dir = os.path.abspath(start_dir)
        self.files = []
        self.selected_index = 0
        self.current_file_path = None
        self.status_msg = ""
        self.refresh()

    def refresh(self):
        self.files = FileSystemProvider.list_directory(self.current_dir)
        if self.selected_index >= len(self.files):
            self.selected_index = max(0, len(self.files) - 1)

    def select_next(self):
        if self.selected_index < len(self.files) - 1:
            self.selected_index += 1
            return True
        return False

    def select_previous(self):
        if self.selected_index > 0:
            self.selected_index -= 1
            return True
        return False

    def enter_directory(self):
        if not self.files: return False
        selected = self.files[self.selected_index]
        if selected == "..":
            return self.go_back()
            
        path = os.path.join(self.current_dir, selected)
        if os.path.isdir(path):
            self.current_dir = os.path.abspath(path)
            self.selected_index = 0
            self.refresh()
            return True
        return False

    def go_back(self):
        parent = os.path.dirname(self.current_dir)
        if parent != self.current_dir:
            self.current_dir = parent
            self.selected_index = 0
            self.refresh()
            return True
        return False

    def get_selected_file(self):
        if not self.files: return None
        return self.files[self.selected_index]


class ExplorerUI:
    """Handles prompt_toolkit layouts and interactions (View & Controller)."""
    def __init__(self, start_dir, standalone=True):
        self.state = ExplorerState(start_dir)
        self.editor_buffer = Buffer(multiline=True)
        self.standalone = standalone
        self.kb = KeyBindings()
        self.setup_ui()
        self.update_preview()

    def set_buffer_text(self, text):
        self.editor_buffer.document = Document(text=text, cursor_position=0)

    def update_preview(self):
        self.state.current_file_path = None
        self.state.status_msg = ""
        
        selected_file = self.state.get_selected_file()
        if not selected_file:
            self.set_buffer_text("Directory is empty.")
            return

        if selected_file == "..":
            self.set_buffer_text("Action: Go to Parent Directory\nShortcut: [Backspace] or [Left Arrow]")
            return

        path = os.path.join(self.state.current_dir, selected_file)
        
        if os.path.isdir(path):
            self.set_buffer_text(FileSystemProvider.format_directory_contents(path))
        else:
            content, is_valid = FileSystemProvider.read_file(path)
            self.set_buffer_text(content)
            if is_valid:
                self.state.current_file_path = path

    def save_current_file(self):
        if self.state.current_file_path:
            success, msg = FileSystemProvider.write_file(self.state.current_file_path, self.editor_buffer.text)
            self.state.status_msg = msg
        else:
            self.state.status_msg = "[ERR] No text document to save."

    def get_left_text(self):
        result = [("class:title", f" 📂 {self.state.current_dir}\n")]
        result.append(("class:line", "=" * 45 + "\n"))
        
        start_idx = max(0, self.state.selected_index - 15)
        end_idx = min(len(self.state.files), start_idx + 30)
        
        if start_idx > 0:
            result.append(("class:dir", "   ... (more items above)\n"))
            
        for i in range(start_idx, end_idx):
            f = self.state.files[i]
            prefix = " > " if i == self.state.selected_index else "   "
            style = "class:selected" if i == self.state.selected_index else ""
            
            if f == "..":
                icon = "🔙 "
            else:
                icon = IconProvider.get_icon(os.path.join(self.state.current_dir, f), f) + " "
            
            if style:
                result.append((style, prefix + icon + f + "\n"))
            else:
                if "📁" in icon or "🔙" in icon:
                    result.append(("class:dir", prefix + icon + f + "\n"))
                else:
                    result.append(("", prefix + icon + f + "\n"))
                    
        if end_idx < len(self.state.files):
            result.append(("class:dir", "   ... (more items below)\n"))
            
        return result

    def setup_ui(self):
        self.left_window = Window(content=FormattedTextControl(text=self.get_left_text, focusable=True), wrap_lines=False, width=35)
        self.right_window = Window(
            content=BufferControl(buffer=self.editor_buffer, focusable=True), 
            wrap_lines=True,
            left_margins=[NumberedMargin(display_tildes=True)]
        )
        
        self.container = VSplit([
            self.left_window,
            Window(width=1, char='│', style='class:line'),
            self.right_window
        ])

        def get_header():
            text = " Kishi IDE Explorer | [Up/Down] Navigate | [Tab/Esc] Switch Panel | [Ctrl+S] Save | [Space] Load Directory | [Q] Quit "
            if self.state.status_msg:
                return [("class:header", text + f" | [*] {self.state.status_msg} ")]
            return [("class:header", text)]
            
        header = Window(height=1, content=FormattedTextControl(text=get_header))
        self.layout = Layout(HSplit([header, self.container]), focused_element=self.left_window)
        
        kb = self.kb
        left_focused = has_focus(self.left_window)
        right_focused = has_focus(self.right_window)
        explorer_focused = left_focused | right_focused
        
        @kb.add("q", filter=left_focused)
        @kb.add("Q", filter=left_focused)
        @kb.add("c-c", filter=left_focused)
        def exit_app(event):
            if self.standalone:
                event.app.exit()
            
        @kb.add("tab", filter=explorer_focused)
        @kb.add("escape", filter=explorer_focused)
        def toggle_focus(event):
            if event.app.layout.has_focus(self.left_window):
                event.app.layout.focus(self.right_window)
            else:
                event.app.layout.focus(self.left_window)
                
        @kb.add("c-s", filter=explorer_focused)
        def save_file(event):
            self.save_current_file()
            
        @kb.add("up", filter=left_focused)
        def move_up(event):
            if self.state.select_previous():
                self.update_preview()
                
        @kb.add("down", filter=left_focused)
        def move_down(event):
            if self.state.select_next():
                self.update_preview()
                
        @kb.add("enter", filter=left_focused)
        @kb.add("right", filter=left_focused)
        def enter_dir(event):
            path = os.path.join(self.state.current_dir, self.state.get_selected_file())
            if os.path.isdir(path) or self.state.get_selected_file() == "..":
                if self.state.enter_directory():
                    self.update_preview()
            else:
                event.app.layout.focus(self.right_window)
                
        @kb.add("backspace", filter=left_focused)
        @kb.add("left", filter=left_focused)
        def go_back(event):
            if self.state.go_back():
                self.update_preview()
                
        @kb.add("space", filter=left_focused)
        def select_and_exit(event):
            os.chdir(self.state.current_dir)
            if self.standalone:
                event.app.exit()

        style = Style.from_dict({
            "header": "bg:#00aa00 #ffffff bold",
            "title": "ansicyan bold",
            "selected": "bg:#0055aa #ffffff bold",
            "dir": "ansiblue bold",
            "line": "ansidarkgray"
        })

        if self.standalone:
            self.app = Application(
                layout=self.layout,
                key_bindings=kb,
                style=style,
                full_screen=True,
                editing_mode=EditingMode.EMACS
            )

    def run(self):
        if not self.standalone: return 0
        try:
            import asyncio
            try:
                asyncio.get_running_loop()
                return self.app.run_async()
            except RuntimeError:
                self.app.run()
        except Exception as e:
            print(f"Explorer Error: {e}")
        return 0

def kishi_explore(args):
    start_dir = os.getcwd() if len(args) < 2 else args[1]
    ui = ExplorerUI(start_dir)
    return ui.run()
