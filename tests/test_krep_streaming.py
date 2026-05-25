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

    def test_regex_metacharacters_safe(self):
        """Pattern her zaman güvenli regex olmalı; meta-karakterler ya drop
        edilir (findall \\w+ ile) ya da re.escape ile escape edilir."""
        import re as _re
        from kishi.krep import _build_rg_pattern
        pattern = _build_rg_pattern("foo.bar baz+qux")
        assert pattern is not None
        # Pattern legitimate regex olmalı (compile patlamasın)
        _re.compile(pattern)
        # Token parçaları görünmeli (findall \\w+ kelimeleri ayrıştırır)
        assert "foo" in pattern
        assert "bar" in pattern
        assert "baz" in pattern
        assert "qux" in pattern
        # Bare metachar pattern'i bozmamalı: '.' veya '+' regex'i breakeder
        # findall drop ettiği için literal görünmemeli
        assert "." not in pattern  # nokta drop edildi (yoksa escape görünürdü)
        assert "+" not in pattern  # artı drop edildi

    def test_escape_safety_with_pre_escaped_chars(self):
        """\\w+ regex meta-karakterleri zaten drop ediyor ama escape() de güvende
        olduğumuzu doğrular: '_' gibi \\w'ye dahil ama re.escape'te değişmeyen
        karakterler bozulmamalı."""
        import re as _re
        from kishi.krep import _build_rg_pattern
        pattern = _build_rg_pattern("user_name auth_token")
        assert pattern is not None
        _re.compile(pattern)  # compile etmeli
        assert "user_name" in pattern
        assert "auth_token" in pattern

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
