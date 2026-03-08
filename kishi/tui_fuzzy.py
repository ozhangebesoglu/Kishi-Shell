from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import Window, HSplit, VSplit
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.styles import Style
import difflib

def run_fuzzy_history(history_lines):
    search_buffer = Buffer(multiline=False)
    
    state = {
        "filtered": history_lines[:],
        "selected_index": 0
    }
    
    def update_filter():
        q = search_buffer.text.lower()
        if not q:
            state["filtered"] = history_lines[:]
        else:
            matches = []
            for line in history_lines:
                if q in line.lower():
                    matches.append(line)
            # If standard substring yields too few, try fuzzy
            if len(matches) < 5:
                # difflib is slower but catches typos
                close_matches = difflib.get_close_matches(q, history_lines, n=15, cutoff=0.3)
                for cm in close_matches:
                    if cm not in matches:
                        matches.append(cm)
            state["filtered"] = matches
            
        state["selected_index"] = 0
            
    search_buffer.on_text_changed += lambda _: update_filter()
    
    def get_results_text():
        result = []
        limit = min(20, len(state["filtered"]))
        
        if limit == 0:
            return [("class:invalid", "  Hiçbir eşleşme bulunamadı.")]
            
        for i in range(limit):
            line = state["filtered"][i]
            prefix = " > " if i == state["selected_index"] else "   "
            style = "class:selected" if i == state["selected_index"] else ""
            
            # Truncate line visually if it's too long
            display_line = line if len(line) < 100 else line[:97] + "..."
            result.append((style, prefix + display_line + "\n"))
            
        return result
        
    results_window = Window(content=FormattedTextControl(text=get_results_text))
    
    search_bar = VSplit([
        Window(width=9, content=FormattedTextControl(text=[("class:prompt", " Arama> ")])),
        Window(content=BufferControl(buffer=search_buffer))
    ])
    
    header = Window(height=1, content=FormattedTextControl(text=[("class:header", " [SEARCH] Kishi Tarihçe (Fuzzy Search) | [Enter] Komutu Seç | [Esc] İptal ")]))
    
    layout = Layout(HSplit([
        header,
        results_window,
        Window(height=1, char='-', style='class:line'),
        search_bar
    ]))
    
    kb = KeyBindings()
    
    @kb.add("escape")
    @kb.add("c-c")
    def _(event):
        event.app.exit(result=None)
        
    @kb.add("up")
    def _(event):
        if state["selected_index"] > 0:
            state["selected_index"] -= 1
            
    @kb.add("down")
    def _(event):
        limit = min(20, len(state["filtered"]))
        if state["selected_index"] < limit - 1:
            state["selected_index"] += 1
            
    @kb.add("enter")
    def _(event):
        if state["filtered"]:
            event.app.exit(result=state["filtered"][state["selected_index"]])
        else:
            event.app.exit(result=None)
            
    style = Style.from_dict({
        "header": "bg:#ddaa00 #000000 bold",
        "prompt": "ansicyan bold",
        "selected": "bg:#0055aa #ffffff bold",
        "line": "ansidarkgray",
        "invalid": "ansired"
    })
    
    app = Application(
        layout=layout,
        key_bindings=kb,
        style=style,
        full_screen=True
    )
    
    return app.run_async()
