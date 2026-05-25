"""
Krep streaming yardımcılarının unit testleri.

Test sırası: pure helper → streaming search → dispatch.
"""
import os
import sys
import pytest
from unittest.mock import patch


class TestRgDetection:
    def test_has_rg_is_bool(self):
        from kishi.krep import _HAS_RG
        assert isinstance(_HAS_RG, bool)

    def test_has_rg_matches_shutil(self):
        """_HAS_RG, shutil.which('rg')'in truthy değeriyle eşleşmeli."""
        import shutil
        from kishi.krep import _HAS_RG
        assert _HAS_RG == (shutil.which("rg") is not None)


class TestBuildRgPattern:
    def test_simple_query(self):
        from kishi.krep import _build_rg_pattern
        # "auth login" → "auth|login" (alfabetik veya orijinal sıra)
        pattern = _build_rg_pattern("auth login")
        assert "auth" in pattern
        assert "login" in pattern
        assert "|" in pattern

    def test_short_words_filtered(self):
        """3 karakterden kısa kelimeler pattern'a girmemeli ("a", "to" gibi)."""
        from kishi.krep import _build_rg_pattern
        pattern = _build_rg_pattern("a to be database")
        # Sadece "database" kalmalı
        assert "database" in pattern
        assert "|to|" not in pattern
        assert pattern.count("|") == 0 or pattern == "database"

    def test_regex_metacharacters_escaped(self):
        """Sorgudaki regex meta-karakterleri escape edilmeli."""
        from kishi.krep import _build_rg_pattern
        pattern = _build_rg_pattern("foo.bar baz+qux")
        # Nokta ve artı escape edilmiş olmalı
        assert "foo\\." in pattern or "foo\\.bar" in pattern
        assert "baz\\+" in pattern or "baz\\+qux" in pattern

    def test_empty_query(self):
        from kishi.krep import _build_rg_pattern
        assert _build_rg_pattern("") is None
        assert _build_rg_pattern("a to") is None  # tümü <3 char

    def test_unicode_query(self):
        from kishi.krep import _build_rg_pattern
        # Türkçe karakterler korunmalı (re.findall \w default'u Unicode'u kapsar)
        pattern = _build_rg_pattern("güvenlik şifre")
        assert pattern is not None
        # En az bir kelime girmeli
        assert "vens" in pattern or "ifre" in pattern or "güvenlik" in pattern \
               or "şifre" in pattern
