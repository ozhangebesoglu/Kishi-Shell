# Kishi Tema Sistemi — Uygulama Planı (v2.0.2.4)

> **For agentic workers:** Use superpowers:executing-plans veya subagent-driven-development.
> Her phase ayrı session'da çalıştırılabilir; bağımlılıklar phase başlığında belirtildi.

**Goal:** Kishi'nin tüm UI yüzeylerinde (REPL prompt, Dashboard, IDE Explorer + Editor, Fuzzy Search)
çoklu tema desteği — kullanıcı `theme set monokai|dracula|one-dark|solarized-dark|solarized-light`
ile seçebilsin. Editor syntax highlighting Pygments'tan terminale uygun parlak renkleri alacak.

**İki repo, tek release:** Kishi-Shell core hook + Kishi-Plugins/theme.py birlikte commit + push.

**Architecture:**
1. **Core** (`kishi/themes.py`): Tema config dosyasını okur + 5 tema için palet + `build_style()`
   ile Pygments style ile prompt_toolkit Style merge eder.
2. **Injection (4 nokta)**: `ui.py`, `tui_dashboard.py`, `tui_explorer.py`, `tui_fuzzy.py`
   içindeki `Style.from_dict({...})` çağrıları `themes.build_style(...)`'ye dönüşür.
3. **Plugin** (`Kishi-Plugins/theme.py`): `theme list|set NAME|current|get` komutu;
   `~/.config/kishi/theme` tek satırlık config dosyasına yazar.
4. **Hot-reload yok**: Restart bekleniyor. (prompt_toolkit Application.style runtime'da
   swap edilebilir ama renderer cache yenileme garantisi yok; ek mimari iş.)

**Tech Stack:** Pure Python 3.8+, mevcut bağımlılıklar (prompt_toolkit, pygments).
Pygments **zaten installed** (tui_explorer.py:13 import). Yeni dep yok.

**Out of scope (gelecek planları):**
- Hot-reload (Application.style runtime swap)
- Custom user temaları (palette JSON)
- Dashboard PTY ANSI iyileştirmeleri (Claude Code rendering — ayrı plan)
- Plugin sisteminin tema/UI parametrelerine müdahale edebilmesi

---

## File Structure

**Yeni:**
- `kishi/themes.py` — Tema modülü (config + palette + build_style)
- `tests/test_themes.py` — 5 tema validasyonu + config roundtrip + Style merge
- `~/.config/kishi/theme` — runtime'da yazılan kullanıcı seçimi (kod değil)
- `Kishi-Plugins/theme.py` — plugin (komut wrapper)
- `docs/superpowers/plans/2026-06-04-kishi-theme-system.md` — bu doküman

**Değişen (Kishi-Shell):**
- `kishi/ui.py:15-23` — `kishi_style = Style.from_dict({...})` → `themes.build_style()`
- `kishi/tui_dashboard.py:658-672` — Style.from_dict → build_style(ui_overrides=DASHBOARD_EXTRAS)
- `kishi/tui_explorer.py:324-330` — Style.from_dict → build_style(ui_overrides=EXPLORER_EXTRAS)
- `kishi/tui_fuzzy.py:99-105` — Style.from_dict → build_style(ui_overrides=FUZZY_EXTRAS)
- `pyproject.toml` — version `2.0.2.3` → `2.0.2.4`
- `kishi/main.py:250` — banner hardcoded version → `kishi_shell.__version__` veya inline güncelle
- `kishi/builtins.py:67` — help_text version
- `kishi/builtins.py:722` — neofetch version
- `README.md` + `README.tr.md` — yeni tema bölümü

**Değişen (Kishi-Plugins):**
- `Kishi-Plugins/theme.py` — YENİ plugin dosyası
- `Kishi-Plugins/README.md` — theme komutu listesi

**Dokunulmayacak:**
- `lexer/parser/executor/expander/state/job_control` — UI değişikliği, çekirdek pipeline'a etki yok
- `krep*` — tamamen ayrı subsystem
- Mevcut testler — yeni testler eklenir, regression olmamalı

---

## Phase 0 — Documentation Discovery (✅ TAMAMLANDI)

**Verified APIs** (canlı `python3 -c` ile doğrulandı, 2026-06-04):

| API | Import yolu | Kullanım |
|---|---|---|
| `Style` | `prompt_toolkit.styles.style` | `Style.from_dict({class: spec})` |
| `merge_styles` | `prompt_toolkit.styles.style` | `merge_styles([style1, style2])` |
| `style_from_pygments_cls` | `prompt_toolkit.styles.pygments` | `style_from_pygments_cls(get_style_by_name("monokai"))` |
| `get_style_by_name` | `pygments.styles` | 5 tema (monokai/dracula/one-dark/solarized-dark/solarized-light) DOĞRULANDI |
| `Application(style=...)` | `prompt_toolkit.application` | constructor accepts style |

**Anti-patterns to avoid:**
- Pygments style adına `_` yerine `-` kullan (`one-dark` doğru, `one_dark` yanlış)
- `Style.from_dict` ile pygments class adı geçilmez (sadece UI sınıfları)
- `Application` runtime'da Style swap için `app.style = new_style` ile renderer invalidation gerek
  → bu plan **restart gerektirir**, hot-reload denenmeyecek

**Plugin sistemi davranışı** (✅ kod ile doğrulandı, `kishi/main.py:122`):
- `~/.kishi/plugins/NAME.py` otomatik yüklenir
- `PLUGIN_COMMANDS = {NAME: func}` dict export'u gerekli
- Komut adı **dosya adıyla eşleşmeli** (`theme.py` → `"theme"` key)
- Plugin **sadece** `BUILTINS` dict'e komut ekleyebilir; Style/lexer override edemez
- Plugin değişikliğinden sonra **restart gerekir** (load_plugins sadece startup'ta çalışır)

---

## Phase 1 — Core Theme Module

**Files:**
- Create: `kishi/themes.py`

**Tasks:**

- [ ] **Step 1.1: kishi/themes.py oluştur**

API spesifikasyonu (zorunlu fonksiyonlar):
- `DEFAULT_THEME = "monokai"` (modül sabiti)
- `list_themes() -> list[str]` — desteklenen tema adları (sıralı)
- `get_current_theme() -> str` — config'ten oku, yoksa DEFAULT_THEME
- `set_current_theme(name: str) -> None` — config'e yaz, geçersiz isim → `ValueError`
- `build_style(theme_name: str | None = None, ui_overrides: dict | None = None) -> Style` —
  Pygments style + UI palette merge'lenmiş prompt_toolkit Style döner. theme_name=None → config'ten.

Internal:
- `_UI_PALETTES: dict[str, dict[str, str]]` — her tema için 14 UI sınıfı:
  `header, compact_bar, title, label, bg, invalid, input_frame,
   command.valid, command.invalid, string, variable, operator,
   path.invalid, selected, dir, line, prompt`
- `_config_path()` — `~/.config/kishi/theme` (XDG_CONFIG_HOME varsa onu kullan)

**Palette örneği (Monokai, doğrulanmış canlı renkler):**
```python
"monokai": {
    "header": "bg:#dd4400 #f8f8f2 bold",
    "compact_bar": "bg:#272822 #f8f8f2",
    "title": "#66d9ef bold",         # cyan, parlak
    "label": "#a6e22e bold",         # green
    "bg": "#3e3d32",
    "invalid": "#f92672",            # magenta-red
    "input_frame": "#fd971f bold",
    "command.valid": "#a6e22e bold",
    "command.invalid": "#f92672 bold",
    "string": "#e6db74",             # yellow
    "variable": "#66d9ef",
    "operator": "#f92672",
    "path.invalid": "#f92672 underline",
    "selected": "bg:#49483e #f8f8f2 bold",
    "dir": "#ae81ff bold",           # purple
    "line": "#75715e",               # comment grey
    "prompt": "#66d9ef bold",
}
```

Aynı yapı: `dracula`, `one-dark`, `solarized-dark`, `solarized-light`.

build_style implementasyonu:
```python
def build_style(theme_name=None, ui_overrides=None):
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
```

**Verification:**
- [ ] `python3 -c "from kishi.themes import list_themes; print(list_themes())"` → 5 isim
- [ ] `python3 -c "from kishi.themes import build_style; s = build_style('dracula'); print(type(s).__name__)"` → `_MergedStyle`
- [ ] Geçersiz tema set'inde ValueError fırlat: `set_current_theme('xyz')`

**Anti-patterns:**
- ❌ `Style.from_dict` yerine sözlük döndürme (mutlaka Style instance dön)
- ❌ Pygments class adını UI palette'e mix etme

---

## Phase 2 — UI Site Injections (4 nokta)

**Bağımlılık:** Phase 1 tamamlanmalı.

**Files (sırayla):**
- Modify: `kishi/ui.py`
- Modify: `kishi/tui_dashboard.py`
- Modify: `kishi/tui_explorer.py`
- Modify: `kishi/tui_fuzzy.py`

**Tasks:**

- [ ] **Step 2.1: ui.py — REPL prompt Style**

Konum: `kishi/ui.py:15-23`

Mevcut:
```python
kishi_style = Style.from_dict({
    'command.valid': 'ansigreen bold',
    'command.invalid': 'ansired bold',
    ...
})
```

Yeni:
```python
from kishi.themes import build_style

# REPL'e özel ek sınıflar (palette default'ları üzerine yazar)
_REPL_OVERRIDES = {
    'bottom-toolbar': 'reverse',
}
kishi_style = build_style(ui_overrides=_REPL_OVERRIDES)
```

- [ ] **Step 2.2: tui_dashboard.py — Dashboard Style**

Konum: `kishi/tui_dashboard.py:658-672`

Mevcut: `Style.from_dict({"header": ..., "compact_bar": ..., ...})` (13 sınıf)

Yeni:
```python
from kishi.themes import build_style
style = build_style()
```

Tüm 13 sınıf zaten `_UI_PALETTES` içinde var; dashboard-özel override gerekmiyor.

- [ ] **Step 2.3: tui_explorer.py — Editor + Explorer Style**

Konum: `kishi/tui_explorer.py:324-330`

Mevcut: `Style.from_dict({"header": ..., "title": ..., "selected": ..., "dir": ..., "line": ...})`

Yeni:
```python
from kishi.themes import build_style

# Explorer'a özel: header rengi tema-dışı (yeşil tasarım kararı)
_EXPLORER_OVERRIDES = {
    "header": "bg:#00aa00 #ffffff bold",
}
style = build_style(ui_overrides=_EXPLORER_OVERRIDES)
```

**Kritik:** Bu noktada `PygmentsLexer` kullanılan editor (line 169 `PygmentsLexer(type(...))`)
artık merged style'ı kullanacağı için **syntax highlighting parlak/okunur olacak**.

- [ ] **Step 2.4: tui_fuzzy.py — Fuzzy Search Style**

Konum: `kishi/tui_fuzzy.py:99-105`

Mevcut: `Style.from_dict({"header": ..., "prompt": ..., "selected": ..., "line": ..., "invalid": ...})`

Yeni:
```python
from kishi.themes import build_style

_FUZZY_OVERRIDES = {
    "header": "bg:#ddaa00 #000000 bold",  # fuzzy-özel amber header
}
style = build_style(ui_overrides=_FUZZY_OVERRIDES)
```

**Verification:**
- [ ] `python3 -c "from kishi.ui import kishi_style; from prompt_toolkit.styles import Style; assert kishi_style"`
- [ ] `python3 -m kishi -c "explore"` → editor açıldığında syntax renkler **parlak**
- [ ] `python3 -m kishi -c "dashboard"` → tüm panel başlıkları okunur
- [ ] `pytest tests/test_tui.py -v` → mevcut testler hâlâ geçer

**Anti-patterns:**
- ❌ `Style.from_dict` artık ui.py/tui_*.py içinde **kalmamalı** (grep ile doğrula)
- ❌ ANSI ad'lar (`ansicyan`, `ansigreen` vs.) tema palette'inde **kalmamalı**

---

## Phase 3 — Plugin (Kishi-Plugins/theme.py)

**Bağımlılık:** Phase 1 tamamlanmalı (`kishi.themes` import edilebilir olmalı).

**Files:**
- Create: `Kishi-Plugins/theme.py`
- Modify: `Kishi-Plugins/README.md`

**Tasks:**

- [ ] **Step 3.1: theme.py plugin'i yaz**

```python
"""
theme — Kishi tema seçici.

Kullanım:
  theme              # şu anki tema + tüm liste
  theme list         # tüm temalar
  theme current      # aktif tema (kısa)
  theme set NAME     # tema değiştir → ~/.config/kishi/theme'a yaz
                     # (etkili olması için Kishi'yi restart et)
  theme get          # = current
"""
def theme(args):
    color_green = "\033[1;32m"
    color_red = "\033[1;31m"
    color_amber = "\033[38;2;255;191;0m"
    color_cyan = "\033[1;36m"
    color_reset = "\033[0m"

    try:
        from kishi import themes
    except ImportError:
        print(f"{color_red}theme plugin requires Kishi v2.0.2.4+{color_reset}")
        return 1

    if len(args) < 2 or args[1] == "list":
        current = themes.get_current_theme()
        print(f"{color_amber}Kishi Themes{color_reset}")
        for name in themes.list_themes():
            marker = f" {color_green}(active){color_reset}" if name == current else ""
            print(f"  - {name}{marker}")
        print(f"\nUse: {color_cyan}theme set NAME{color_reset} "
              f"(restart Kishi to apply)")
        return 0

    action = args[1].lower()

    if action in ("current", "get"):
        print(themes.get_current_theme())
        return 0

    if action == "set":
        if len(args) < 3:
            print(f"{color_red}Usage: theme set NAME{color_reset}")
            print(f"Available: {', '.join(themes.list_themes())}")
            return 1
        name = args[2]
        try:
            themes.set_current_theme(name)
        except ValueError as e:
            print(f"{color_red}{e}{color_reset}")
            return 1
        print(f"{color_green}[+]{color_reset} Theme set to: {color_cyan}{name}{color_reset}")
        print(f"    Restart Kishi to apply (theme is loaded at startup).")
        return 0

    print(f"{color_red}Unknown action: {action}{color_reset}")
    print(f"Usage: theme [list|current|set NAME]")
    return 1


PLUGIN_COMMANDS = {
    "theme": theme,
}
```

- [ ] **Step 3.2: Kishi-Plugins/README.md güncelle**

"Available Plugins" tablosuna ekle:
```markdown
| **theme** | `theme` | Switch Kishi color theme | `theme set dracula` |
```

**Verification:**
- [ ] `cp Kishi-Plugins/theme.py ~/.kishi/plugins/` + Kishi restart
- [ ] `Kishi$ -> theme` → 5 tema listelenir, monokai (active) işaretli
- [ ] `Kishi$ -> theme set dracula` → success mesajı + restart uyarısı
- [ ] `cat ~/.config/kishi/theme` → `dracula`
- [ ] Kishi restart → renkler dracula
- [ ] `theme set invalid_xyz` → ValueError mesajı + non-zero exit

**Anti-patterns:**
- ❌ Plugin Style/lexer override etmeye çalışma — `kishi.themes` API'sini KULLAN
- ❌ Plugin restart'siz tema değişikliği vaad etme — net "restart required" mesajı ver

---

## Phase 4 — Tests

**Bağımlılık:** Phase 1-3 tamamlanmalı.

**Files:**
- Create: `tests/test_themes.py`

**Tasks:**

- [ ] **Step 4.1: test_themes.py yaz**

Kategoriler:
```python
import pytest
from prompt_toolkit.styles import Style

class TestThemeRegistry:
    def test_list_themes_returns_5(self):
        from kishi.themes import list_themes
        names = list_themes()
        assert set(names) == {"monokai", "dracula", "one-dark",
                              "solarized-dark", "solarized-light"}

    def test_default_theme_is_monokai(self, monkeypatch, tmp_path):
        # ~/.config/kishi/ tmp_path'e yönlendir
        monkeypatch.setenv("HOME", str(tmp_path))
        from kishi.themes import get_current_theme, DEFAULT_THEME
        assert get_current_theme() == DEFAULT_THEME == "monokai"


class TestConfigRoundtrip:
    def test_set_and_read_back(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        from kishi.themes import set_current_theme, get_current_theme
        set_current_theme("dracula")
        assert get_current_theme() == "dracula"

    def test_invalid_theme_raises(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        from kishi.themes import set_current_theme
        with pytest.raises(ValueError, match="Unknown theme"):
            set_current_theme("nonexistent_xyz")

    def test_corrupted_config_falls_back_to_default(self, monkeypatch, tmp_path):
        cfg = tmp_path / ".config" / "kishi" / "theme"
        cfg.parent.mkdir(parents=True)
        cfg.write_text("garbage_theme_name\n")
        monkeypatch.setenv("HOME", str(tmp_path))
        from kishi.themes import get_current_theme, DEFAULT_THEME
        assert get_current_theme() == DEFAULT_THEME


class TestBuildStyle:
    @pytest.mark.parametrize("name", [
        "monokai", "dracula", "one-dark", "solarized-dark", "solarized-light"
    ])
    def test_each_theme_builds(self, name):
        from kishi.themes import build_style
        style = build_style(name)
        assert style is not None
        # Pygments + UI merge sonucu (MergedStyle) veya saf Style
        assert hasattr(style, "get_attrs_for_style_str")

    def test_ui_overrides_take_precedence(self):
        from kishi.themes import build_style
        style = build_style("monokai", ui_overrides={"header": "bg:#ff00ff"})
        # MergedStyle ile sınıf-bazlı resolve test:
        attrs = style.get_attrs_for_style_str("class:header")
        # bgcolor magenta olmalı (override aktif)
        # Not: prompt_toolkit Attrs API'si bgcolor str döner
        assert "ff00ff" in (attrs.bgcolor or "").lower()


class TestIntegration:
    def test_ui_module_uses_build_style(self):
        """ui.py'nin kishi_style'ı Style instance olmalı."""
        from kishi.ui import kishi_style
        assert kishi_style is not None
        assert hasattr(kishi_style, "get_attrs_for_style_str")

    def test_no_ansi_names_in_palette(self):
        """ANSI ad'lar (ansicyan vs.) palette'te kalmamalı."""
        from kishi.themes import _UI_PALETTES
        for theme_name, palette in _UI_PALETTES.items():
            for cls, spec in palette.items():
                # ANSI ad'lar yerine hex/word renkler bekleniyor
                assert "ansicyan" not in spec, f"{theme_name}.{cls} hâlâ ansicyan"
                assert "ansired" not in spec, f"{theme_name}.{cls} hâlâ ansired"
                assert "ansigreen" not in spec, f"{theme_name}.{cls} hâlâ ansigreen"
                assert "ansiyellow" not in spec, f"{theme_name}.{cls} hâlâ ansiyellow"
                assert "ansimagenta" not in spec, f"{theme_name}.{cls} hâlâ ansimagenta"
                assert "ansiblue" not in spec, f"{theme_name}.{cls} hâlâ ansiblue"
                assert "ansidarkgray" not in spec, f"{theme_name}.{cls} hâlâ ansidarkgray"
```

**Verification:**
- [ ] `pytest tests/test_themes.py -v` → 10+ test, hepsi geçer
- [ ] `pytest --no-header -q` → 416+ test (mevcut 406 + ~10 yeni)
- [ ] Tek fail hâlâ `test_arithmetic_not_expanded` (Krep dışı, dokümante edilmiş eksiklik)

**Anti-patterns:**
- ❌ Test'lerde `~/.config/kishi/` gerçek path'i yazma → mutlaka `monkeypatch.setenv("HOME", tmp)` kullan
- ❌ Style internalsına özel reach (`style._style_rules` gibi) → public API: `get_attrs_for_style_str`

---

## Phase 5 — Version Bump + Hardcoded Strings

**Bağımlılık:** Phase 1-4 tamamlanmalı + testler yeşil.

**Files:**
- Modify: `pyproject.toml` (version: 2.0.2.3 → 2.0.2.4)
- Modify: `kishi/main.py:250` (banner version string)
- Modify: `kishi/builtins.py:67` (help_text version)
- Modify: `kishi/builtins.py:722` (neofetch version)

**Tasks:**

- [ ] **Step 5.1: pyproject.toml**

```toml
version = "2.0.2.4"
```

- [ ] **Step 5.2: Hardcoded 3 string güncelle**

Aramalar:
```bash
grep -rn "v2.0.2.2\|2.0.2.3" kishi/ --include="*.py"
```

Şu 3 yerde `v2.0.2.2` → `v2.0.2.4`:
- `kishi/main.py:250` — `Kishi Shell Advanced (v2.0.2.2)` banner
- `kishi/builtins.py:67` — `help_text` başlığı
- `kishi/builtins.py:722` — neofetch `Shell:` satırı

**Not:** Şu an `v2.0.2.3`'e bile güncellenmemişler — bu drift'i bu PR ile düzeltiyoruz.
İdeal çözüm: `kishi/__version__.py` modülü + tek noktadan oku.
**Bu plan kapsamında değil** — sadece string fix.

- [ ] **Step 5.3: README.md + README.tr.md**

Başlık version: `v2.0.2.3` → `v2.0.2.4`
Yeni "Theme System" bölümü ekle (Krep AI bölümünden önce veya sonra):

```markdown
## Theme System (v2.0.2.4+)

Kishi 5 yerleşik tema ile gelir: **Monokai** (default), **Dracula**, **One Dark**,
**Solarized Dark**, **Solarized Light**. Editor syntax highlighting + dashboard +
explorer + REPL prompt — hepsi seçilen temayı kullanır.

```bash
# Temaları listele
Kishi$ -> theme

# Tema değiştir (Kishi-Plugins'ten plugin gerektirir)
Kishi$ -> plugin install theme
Kishi$ -> theme set dracula
[+] Theme set to: dracula
    Restart Kishi to apply (theme is loaded at startup).
```

Tema seçimi `~/.config/kishi/theme` dosyasına yazılır — kalıcıdır.
```

TR README'ye paralel ekleme.

**Verification:**
- [ ] `grep -rn "v2.0.2.2\|v2.0.2.3" kishi/ --include="*.py"` → 0 hit
- [ ] `python3 -c "import kishi; print('OK')"` → import temiz
- [ ] `pytest --no-header -q` → 416+ test geçer, sadece arithmetic fail

---

## Phase 6 — Commit + Push (İKİ REPO PARALEL)

**Bağımlılık:** Phase 5 + tüm testler geçer.

**Tasks:**

- [ ] **Step 6.1: Kishi-Shell repo'da staged review**

```bash
cd '/home/ozhan/Sistem/Okul/Sistem&Gorsel/VizeProjesi'
git status --short
git diff --stat
```

Beklenen dosyalar:
```
M  kishi/builtins.py            (~2 satır version + 0 başka değişiklik)
M  kishi/main.py                (~1 satır version)
M  kishi/ui.py                  (~5 satır build_style geçişi)
M  kishi/tui_dashboard.py       (~5 satır build_style)
M  kishi/tui_explorer.py        (~5 satır build_style)
M  kishi/tui_fuzzy.py           (~5 satır build_style)
A  kishi/themes.py              (YENİ, ~150 satır)
A  tests/test_themes.py         (YENİ, ~100 satır)
M  pyproject.toml               (1 satır version)
M  README.md                    (~25 satır theme bölümü)
M  README.tr.md                 (~25 satır theme bölümü)
A  docs/superpowers/plans/2026-06-04-kishi-theme-system.md   (bu doküman)
```

- [ ] **Step 6.2: Kishi-Shell commit**

Conventional commit:
```
feat(theme): 5-theme system with Pygments syntax highlighting (v2.0.2.4)

- kishi/themes.py: 5 built-in themes (monokai, dracula, one-dark,
  solarized-dark, solarized-light), Pygments style + UI palette merge.
- 4 UI sites (ui.py, tui_dashboard, tui_explorer, tui_fuzzy) switched
  from Style.from_dict ANSI names to themes.build_style() fixed hex.
- Editor syntax highlighting now uses Pygments style merged into
  prompt_toolkit Style → readable colors on dark terminal themes.
- Theme selection persisted to ~/.config/kishi/theme (Kishi restart
  required to apply, no hot-reload yet).
- Hardcoded version strings synced to 2.0.2.4 (was drifting at 2.0.2.2).
- Plugin (`theme list|set|current`) ships in Kishi-Plugins repo.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

- [ ] **Step 6.3: Kishi-Plugins repo commit**

```bash
cd /home/ozhan/Sistem/Repos/Kishi-Plugins
# (veya başka path — repo gerçek konumu doğrula)
git status --short
# A  theme.py
# M  README.md
```

Commit:
```
feat(theme): theme plugin for Kishi v2.0.2.4+

Adds `theme` command: list/current/get/set sub-actions.
Writes selection to ~/.config/kishi/theme (requires Kishi v2.0.2.4+
core themes module to apply).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

- [ ] **Step 6.4: Senkron push (kullanıcı onayıyla)**

```bash
# Önce Kishi-Plugins (smaller blast radius)
cd /path/to/Kishi-Plugins && git push origin main

# Sonra Kishi-Shell + tag
cd '/home/ozhan/Sistem/Okul/Sistem&Gorsel/VizeProjesi'
git push origin main
git tag v2.0.2.4 HEAD
git push origin v2.0.2.4   # cibuildwheel + PyPI + GitHub Release tetikler
```

**Verification:**
- [ ] `gh run list --limit 3` → v2.0.2.4 publish workflow running
- [ ] ~7 dk sonra: `gh release view v2.0.2.4` → release yayınlandı
- [ ] `pip index versions kishi-shell` → 2.0.2.4 görünür
- [ ] User: `plugin install theme` + Kishi restart + `theme set dracula` → renkler değişir

**Anti-patterns:**
- ❌ Tag'ı testler yeşil olmadan atma
- ❌ Sadece bir repo'ya push edip diğerini unutma — atomik release olmalı
- ❌ Push'tan önce gerçekten 2 repo'ya da commit atıldı mı kontrol etmeden tag'a geçme

---

## Final Verification Checklist

Hepsini sırayla doğrula:

- [ ] Mevcut tüm testler hâlâ geçer (`pytest --no-header -q` → 406+ baseline)
- [ ] Yeni testler hepsi yeşil (`pytest tests/test_themes.py -v` → 10+ test)
- [ ] Lokal smoke test:
  - [ ] `kishi -c "explore"` → editor Python dosyası açar, **parlak** renkler
  - [ ] `kishi -c "dashboard"` → tüm panel başlıkları okunur
  - [ ] `theme set dracula` + restart → mor tonlar
- [ ] 4 shell uyumu kalıyor (bash/zsh/fish/sh) — sadece tema değişikliği, shell mantığı el sürülmedi
- [ ] PyPI 2.0.2.4 yayında
- [ ] AUR auto-update workflow tamam
- [ ] README'lerde tema bölümü güncel

## Bilinen Sınırlamalar (Belgelenir)

1. **Restart gerekli**: Tema değişikliği için Kishi yeniden başlatılmalı.
   Hot-reload ek mimari iş gerektirir (Application.style runtime swap +
   renderer cache invalidate + tüm Style.from_dict çağrılarının instance
   re-create'i). Ayrı bir plan.

2. **5 sabit tema**: Custom user temaları desteklenmiyor. Eklemek için
   `~/.config/kishi/themes/NAME.json` formatında bir palette loader gerek.
   Ayrı plan.

3. **Dashboard PTY ANSI**: Claude Code gibi modern TUI'ler hâlâ `^M^M`
   gösterebilir — terminal size sync + alt-screen handling eksik.
   **Bu plan kapsamı DEĞİL.** Ayrı planda ele alınacak.

4. **Hardcoded version strings**: Bu PR 3 string'i 2.0.2.4'e senkronladı
   ama mimari sorun çözülmedi. Gelecekteki iyileştirme: `kishi/__version__.py`
   single-source-of-truth.

---

## Implementation Order (Recommended Session Plan)

Her phase ayrı session'da çalışabilir:

**Session A** (60 dk): Phase 0 (done) + Phase 1 (themes.py)
**Session B** (45 dk): Phase 2 (4 UI site injections)
**Session C** (30 dk): Phase 3 (Kishi-Plugins/theme.py + README)
**Session D** (45 dk): Phase 4 (tests)
**Session E** (30 dk): Phase 5 (version bump + README'ler) + Phase 6 (commit + push)

Total: ~3.5 saat istisnasız iş. Daha hızlı olabilir, çünkü mimari netleştirildi
(varsayım yok, tüm dosyalar/satırlar verified).
