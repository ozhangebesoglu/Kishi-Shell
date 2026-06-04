"""
kishi/themes.py için kapsamlı testler.

- Tema registry (5 tema, default = monokai)
- Config roundtrip (~/.config/kishi/theme) — HOME monkeypatch ile izole
- build_style API (her 5 tema, ui_overrides önceliği)
- Integration: ui.py kishi_style hâlâ Style instance
- ANSI ad guard: palette'lerde hiç ansicyan/ansired/vs. yok
"""
import os
import pytest


# ---------------------------------------------------------------------------
# Theme registry
# ---------------------------------------------------------------------------

class TestThemeRegistry:
    def test_list_themes_returns_expected_set(self):
        from kishi.themes import list_themes
        names = list_themes()
        assert set(names) == {
            "monokai", "dracula", "one-dark",
            "solarized-dark", "solarized-light",
        }

    def test_list_themes_is_sorted(self):
        from kishi.themes import list_themes
        names = list_themes()
        assert names == sorted(names)

    def test_default_theme_is_monokai(self):
        from kishi.themes import DEFAULT_THEME
        assert DEFAULT_THEME == "monokai"


# ---------------------------------------------------------------------------
# Config roundtrip — ~/.config/kishi/theme
# ---------------------------------------------------------------------------

class TestConfigRoundtrip:
    def test_get_current_default_when_no_config(self, monkeypatch, tmp_path):
        # XDG_CONFIG_HOME ve HOME ikisini de override
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        from kishi.themes import get_current_theme, DEFAULT_THEME
        assert get_current_theme() == DEFAULT_THEME

    def test_set_and_read_back(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        from kishi.themes import set_current_theme, get_current_theme
        set_current_theme("dracula")
        assert get_current_theme() == "dracula"
        # Dosya gerçekten yazıldı mı?
        cfg = tmp_path / ".config" / "kishi" / "theme"
        assert cfg.is_file()
        assert cfg.read_text().strip() == "dracula"

    def test_invalid_theme_raises(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        from kishi.themes import set_current_theme
        with pytest.raises(ValueError, match="Unknown theme"):
            set_current_theme("nonexistent_xyz")

    def test_corrupted_config_falls_back_to_default(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        cfg = tmp_path / ".config" / "kishi" / "theme"
        cfg.parent.mkdir(parents=True)
        cfg.write_text("garbage_theme_name\n")
        from kishi.themes import get_current_theme, DEFAULT_THEME
        assert get_current_theme() == DEFAULT_THEME

    def test_xdg_config_home_honored(self, monkeypatch, tmp_path):
        xdg = tmp_path / "custom_xdg"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        from kishi.themes import set_current_theme
        set_current_theme("one-dark")
        assert (xdg / "kishi" / "theme").is_file()


# ---------------------------------------------------------------------------
# build_style — API contract
# ---------------------------------------------------------------------------

class TestBuildStyle:
    @pytest.mark.parametrize("name", [
        "monokai", "dracula", "one-dark",
        "solarized-dark", "solarized-light",
    ])
    def test_each_theme_builds(self, name):
        from kishi.themes import build_style
        style = build_style(name)
        assert style is not None
        # prompt_toolkit Style ortak arayüzü: get_attrs_for_style_str
        assert hasattr(style, "get_attrs_for_style_str")

    def test_default_param_uses_config(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        from kishi.themes import build_style, set_current_theme
        set_current_theme("dracula")
        s = build_style()  # theme_name=None → config'ten dracula
        assert s is not None

    def test_ui_overrides_take_precedence(self):
        from kishi.themes import build_style
        style = build_style("monokai", ui_overrides={"header": "bg:#ff00ff bold"})
        attrs = style.get_attrs_for_style_str("class:header")
        # bgcolor magenta olmalı (override aktif)
        assert "ff00ff" in (attrs.bgcolor or "").lower()

    def test_unknown_theme_falls_back_to_default_palette(self):
        # Geçersiz tema build_style'a verilirse default palette + Pygments fail
        # → en azından bir UI Style döner (saf Style ya da MergedStyle).
        from kishi.themes import build_style
        style = build_style("invalid_xyz_zzz")
        assert style is not None


# ---------------------------------------------------------------------------
# Integration — UI modüllerinin entegrasyonu
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_ui_module_kishi_style_is_built(self):
        """ui.py'nin kishi_style'ı build_style sonucu (Style instance) olmalı."""
        from kishi.ui import kishi_style
        assert kishi_style is not None
        assert hasattr(kishi_style, "get_attrs_for_style_str")


# ---------------------------------------------------------------------------
# Anti-pattern guards
# ---------------------------------------------------------------------------

class TestNoAnsiNames:
    """Tema paletlerinde ANSI ad'lar bulunmamalı (terminal teması override edemesin)."""

    BANNED = (
        "ansicyan", "ansired", "ansigreen", "ansiyellow",
        "ansimagenta", "ansiblue", "ansidarkgray", "ansigray",
    )

    def test_palettes_have_no_ansi_names(self):
        from kishi.themes import _UI_PALETTES
        for theme_name, palette in _UI_PALETTES.items():
            for cls, spec in palette.items():
                for banned in self.BANNED:
                    assert banned not in spec, (
                        f"{theme_name}.{cls} hâlâ '{banned}' içeriyor: {spec!r}"
                    )
