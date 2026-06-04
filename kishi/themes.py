"""
Kishi theme system (v2.0.2.4+).

Kullanıcının seçtiği temayı (~/.config/kishi/theme) okur ve hem editor
(Pygments lexer) hem de UI sınıfları için tek bir prompt_toolkit Style
üretir. Plugin (Kishi-Plugins/theme.py) yalnız config dosyasını yazar;
asıl uygulama burada.

Desteklenen temalar: monokai (default), dracula, one-dark,
solarized-dark, solarized-light. Tema değişikliği için Kishi yeniden
başlatılmalıdır (renderer cache invalidate yok).
"""
import os

from prompt_toolkit.styles import Style, merge_styles
from prompt_toolkit.styles.pygments import style_from_pygments_cls


DEFAULT_THEME = "monokai"


# Tema başına UI sabitleri. Hex renkler — ANSI ad'lar kullanılmıyor ki
# terminal teması override edemesin. Yeni tema eklerken sadece bu sözlüğü
# genişlet; Pygments style adı aynı isimle yüklenir (one-dark da dahil).
_UI_PALETTES = {
    "monokai": {
        "header": "bg:#dd4400 #f8f8f2 bold",
        "compact_bar": "bg:#272822 #f8f8f2",
        "title": "#66d9ef bold",
        "label": "#a6e22e bold",
        "bg": "#3e3d32",
        "invalid": "#f92672",
        "input_frame": "#fd971f bold",
        "command.valid": "#a6e22e bold",
        "command.invalid": "#f92672 bold",
        "string": "#e6db74",
        "variable": "#66d9ef",
        "operator": "#f92672",
        "path.invalid": "#f92672 underline",
        "selected": "bg:#49483e #f8f8f2 bold",
        "dir": "#ae81ff bold",
        "line": "#75715e",
        "prompt": "#66d9ef bold",
    },
    "dracula": {
        "header": "bg:#bd93f9 #282a36 bold",
        "compact_bar": "bg:#282a36 #f8f8f2",
        "title": "#8be9fd bold",
        "label": "#50fa7b bold",
        "bg": "#44475a",
        "invalid": "#ff5555",
        "input_frame": "#ffb86c bold",
        "command.valid": "#50fa7b bold",
        "command.invalid": "#ff5555 bold",
        "string": "#f1fa8c",
        "variable": "#8be9fd",
        "operator": "#ff79c6",
        "path.invalid": "#ff5555 underline",
        "selected": "bg:#44475a #f8f8f2 bold",
        "dir": "#bd93f9 bold",
        "line": "#6272a4",
        "prompt": "#8be9fd bold",
    },
    "one-dark": {
        "header": "bg:#61afef #282c34 bold",
        "compact_bar": "bg:#282c34 #abb2bf",
        "title": "#61afef bold",
        "label": "#98c379 bold",
        "bg": "#3e4451",
        "invalid": "#e06c75",
        "input_frame": "#e5c07b bold",
        "command.valid": "#98c379 bold",
        "command.invalid": "#e06c75 bold",
        "string": "#98c379",
        "variable": "#61afef",
        "operator": "#c678dd",
        "path.invalid": "#e06c75 underline",
        "selected": "bg:#3e4451 #abb2bf bold",
        "dir": "#c678dd bold",
        "line": "#5c6370",
        "prompt": "#61afef bold",
    },
    "solarized-dark": {
        "header": "bg:#268bd2 #002b36 bold",
        "compact_bar": "bg:#073642 #93a1a1",
        "title": "#268bd2 bold",
        "label": "#859900 bold",
        "bg": "#073642",
        "invalid": "#dc322f",
        "input_frame": "#b58900 bold",
        "command.valid": "#859900 bold",
        "command.invalid": "#dc322f bold",
        "string": "#2aa198",
        "variable": "#268bd2",
        "operator": "#d33682",
        "path.invalid": "#dc322f underline",
        "selected": "bg:#073642 #eee8d5 bold",
        "dir": "#6c71c4 bold",
        "line": "#586e75",
        "prompt": "#268bd2 bold",
    },
    "solarized-light": {
        "header": "bg:#268bd2 #fdf6e3 bold",
        "compact_bar": "bg:#eee8d5 #586e75",
        "title": "#268bd2 bold",
        "label": "#859900 bold",
        "bg": "#eee8d5",
        "invalid": "#dc322f",
        "input_frame": "#b58900 bold",
        "command.valid": "#859900 bold",
        "command.invalid": "#dc322f bold",
        "string": "#2aa198",
        "variable": "#268bd2",
        "operator": "#d33682",
        "path.invalid": "#dc322f underline",
        "selected": "bg:#eee8d5 #002b36 bold",
        "dir": "#6c71c4 bold",
        "line": "#93a1a1",
        "prompt": "#268bd2 bold",
    },
}


def _config_path():
    """Aktif tema config dosyası: $XDG_CONFIG_HOME/kishi/theme veya ~/.config/kishi/theme."""
    xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.environ.get("HOME", "/"), ".config"
    )
    return os.path.join(xdg, "kishi", "theme")


def list_themes():
    """Desteklenen tema adlarını sıralı liste olarak döndürür."""
    return sorted(_UI_PALETTES.keys())


def get_current_theme():
    """Aktif tema adı. Config yoksa veya geçersiz tema yazıyorsa DEFAULT_THEME."""
    path = _config_path()
    if not os.path.isfile(path):
        return DEFAULT_THEME
    try:
        with open(path, "r", encoding="utf-8") as f:
            name = f.read().strip()
        if name in _UI_PALETTES:
            return name
    except (OSError, IOError):
        pass
    return DEFAULT_THEME


def set_current_theme(name):
    """Tema adını config'e yaz. Geçersiz isim → ValueError."""
    if name not in _UI_PALETTES:
        raise ValueError(
            f"Unknown theme: {name!r}. Available: {', '.join(list_themes())}"
        )
    path = _config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(name + "\n")


def build_style(theme_name=None, ui_overrides=None):
    """Pygments style + UI palette merge edilmiş prompt_toolkit Style.

    Args:
        theme_name: tema adı (None → config'ten oku).
        ui_overrides: site-özel ek/override UI sınıfları (örn. fuzzy'ye
                      özel header rengi).

    Returns:
        Style — Application(style=...) içinde doğrudan kullanılır.
    """
    name = theme_name or get_current_theme()
    palette = dict(_UI_PALETTES.get(name, _UI_PALETTES[DEFAULT_THEME]))
    if ui_overrides:
        palette.update(ui_overrides)
    ui_style = Style.from_dict(palette)

    try:
        from pygments.styles import get_style_by_name
        pyg_style = style_from_pygments_cls(get_style_by_name(name))
        return merge_styles([pyg_style, ui_style])
    except Exception:
        return ui_style
