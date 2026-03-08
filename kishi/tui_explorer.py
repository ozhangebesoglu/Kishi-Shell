import os
from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import Window, VSplit, HSplit
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.styles import Style

class KishiExplorer:
    def __init__(self, start_dir="."):
        self.current_dir = os.path.abspath(start_dir)
        self.files = []
        self.selected_index = 0
        self.preview_text = ""
        self.refresh_files()
        
    def refresh_files(self):
        try:
            items = os.listdir(self.current_dir)
            # Dizinler üstte, dosyalar altta olacak şekilde sırala
            self.files = [".."] + sorted(items, key=lambda x: (not os.path.isdir(os.path.join(self.current_dir, x)), x.lower()))
        except Exception:
            self.files = [".."]
            
        if self.selected_index >= len(self.files):
            self.selected_index = max(0, len(self.files) - 1)
        self.update_preview()
        
    def update_preview(self):
        if not self.files:
            self.preview_text = "Dizin boş."
            return
            
        selected_file = self.files[self.selected_index]
        if selected_file == "..":
            self.preview_text = "Üst Dizine Çık (Backspace / Sol Ok)"
            return
            
        path = os.path.join(self.current_dir, selected_file)
        
        if os.path.isdir(path):
            try:
                items = os.listdir(path)
                preview = f"Klasör İçeriği ({len(items)} öğe):\n\n"
                for item in items[:50]:
                    icon = "📁" if os.path.isdir(os.path.join(path, item)) else "📄"
                    preview += f" {icon} {item}\n"
                if len(items) > 50:
                    preview += f"\n... ve {len(items)-50} dosya daha."
                self.preview_text = preview
            except Exception as e:
                self.preview_text = f"Erişim engellendi: {e}"
        else:
            try:
                size_mb = os.path.getsize(path) / (1024 * 1024)
                if size_mb > 2.0:
                    self.preview_text = f"Dosya çok büyük ({size_mb:.1f} MB).\n\nPerformans için önizleme kapalı."
                else:
                    with open(path, 'r', encoding='utf-8') as f:
                        self.preview_text = f.read(3000)
            except UnicodeDecodeError:
                self.preview_text = "İkilik (Binary) dosya.\nÖnizleme desteklenmiyor."
            except Exception as e:
                self.preview_text = f"Okunamıyor: {e}"

    def get_left_text(self):
        result = [("class:title", f" 📂 {self.current_dir}\n")]
        result.append(("class:line", "=" * 45 + "\n"))
        
        # Sayfalama mantığı (Ekrana sığmayanlar için kaydırma)
        # Terminal yüksekliğini 30 satır varsayalım
        start_idx = max(0, self.selected_index - 15)
        end_idx = min(len(self.files), start_idx + 30)
        
        if start_idx > 0:
            result.append(("class:dir", "   ... (yukarıda daha fazla var)\n"))
            
        for i in range(start_idx, end_idx):
            f = self.files[i]
            prefix = " ▶ " if i == self.selected_index else "   "
            style = "class:selected" if i == self.selected_index else ""
            
            if f == "..":
                icon = "🔙 "
            else:
                icon = "📁 " if os.path.isdir(os.path.join(self.current_dir, f)) else "📄 "
            
            if style:
                result.append((style, prefix + icon + f + "\n"))
            else:
                if "📁" in icon or "🔙" in icon:
                    result.append(("class:dir", prefix + icon + f + "\n"))
                else:
                    result.append(("", prefix + icon + f + "\n"))
                    
        if end_idx < len(self.files):
            result.append(("class:dir", "   ... (aşağıda daha fazla var)\n"))
            
        return result
        
    def get_right_text(self):
        return [("class:preview", self.preview_text)]

def kishi_explore(args):
    start_dir = os.getcwd() if len(args) < 2 else args[1]
    explorer = KishiExplorer(start_dir)
    app = None
    
    left_window = Window(content=FormattedTextControl(text=explorer.get_left_text), wrap_lines=False, width=50)
    right_window = Window(content=FormattedTextControl(text=explorer.get_right_text), wrap_lines=True)
    
    body = VSplit([
        left_window,
        Window(width=1, char='│', style='class:line'),
        right_window
    ])
    
    header_text = [("class:header", " Kishi Explorer | [↑/↓] Gezin | [Enter/Right] Gir | [Backspace/Left] Geri | [Space] Kabuk Dizini Yap | [Q] Çıkış ")]
    header = Window(height=1, content=FormattedTextControl(text=header_text))
    
    layout = Layout(HSplit([header, body]))
    
    kb = KeyBindings()
    
    @kb.add("q")
    @kb.add("Q")
    @kb.add("c-c")
    def exit_app(event):
        event.app.exit()
        
    @kb.add("up")
    def move_up(event):
        if explorer.selected_index > 0:
            explorer.selected_index -= 1
            explorer.update_preview()
            
    @kb.add("down")
    def move_down(event):
        if explorer.selected_index < len(explorer.files) - 1:
            explorer.selected_index += 1
            explorer.update_preview()
            
    @kb.add("enter")
    @kb.add("right")
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
                
    @kb.add("backspace")
    @kb.add("left")
    def go_back(event):
        parent = os.path.dirname(explorer.current_dir)
        if parent != explorer.current_dir:
            explorer.current_dir = parent
            explorer.selected_index = 0
            explorer.refresh_files()
            
    @kb.add("space")
    def select_and_exit(event):
        # Kishi shell'in o anki dizinini değiştirerek çık
        os.chdir(explorer.current_dir)
        event.app.exit()
            
    style = Style.from_dict({
        "header": "bg:#00aa00 #ffffff bold",
        "title": "ansicyan bold",
        "selected": "bg:#0055aa #ffffff bold",
        "dir": "ansiblue bold",
        "preview": "ansigray",
        "line": "ansidarkgray"
    })
    
    app = Application(
        layout=layout,
        key_bindings=kb,
        style=style,
        full_screen=True
    )
    
    try:
        app.run()
    except Exception as e:
        print(f"Explorer Error: {e}")
        
    return 0
