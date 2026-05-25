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


class TestStreamingSearch:
    @pytest.fixture
    def tmp_corpus(self, tmp_path):
        # 3 dosya: auth keyword'lerini içeren, bot/db, boring
        (tmp_path / "auth.py").write_text(
            "def login(user):\n"
            "    auth_token = generate_token()\n"
            "    return validate(user)\n"
        )
        (tmp_path / "config.py").write_text(
            "DB_HOST = 'localhost'\n"
            "DB_PORT = 5432\n"
        )
        (tmp_path / "boring.txt").write_text(
            "apple banana cherry\n" * 10
        )
        return str(tmp_path)

    def test_streaming_finds_matches(self, tmp_corpus):
        """Streaming search auth dosyasından eşleşme döndürmeli."""
        from kishi.krep import _krep_rg_streaming, vectorize_text
        q_vec = vectorize_text("login auth")
        matches, stats = _krep_rg_streaming(
            query_str="login auth",
            q_vec=q_vec,
            paths=[tmp_corpus],
            limit=5,
        )
        assert isinstance(matches, list)
        assert len(matches) > 0
        # auth.py içinde eşleşme olmalı (output_str içinde geçmeli)
        assert any("auth.py" in m[2] for m in matches)
        assert stats["lines_vectorized"] > 0

    def test_streaming_no_matches_returns_empty(self, tmp_corpus):
        """Hiç eşleşmeyen sorgu boş liste dönmeli."""
        from kishi.krep import _krep_rg_streaming, vectorize_text
        q_vec = vectorize_text("error")
        matches, stats = _krep_rg_streaming(
            query_str="qwertyzxcvbn",  # corpus'ta yok
            q_vec=q_vec,
            paths=[tmp_corpus],
            limit=5,
        )
        assert matches == []

    def test_streaming_respects_limit_via_early_stop(self, tmp_path):
        """Limit × 10 match bulunca rg terminate edilmeli (early stop)."""
        # 100 dosya, her birinde 20 auth-içeren satır → 2000 potansiyel
        for i in range(100):
            (tmp_path / f"f{i:03d}.txt").write_text("auth login\n" * 20)

        from kishi.krep import _krep_rg_streaming, vectorize_text
        q_vec = vectorize_text("auth")
        matches, stats = _krep_rg_streaming(
            query_str="auth",
            q_vec=q_vec,
            paths=[str(tmp_path)],
            limit=5,
        )
        # Early-stop tetiklenmeli (target = 5 × 10 = 50 match)
        assert stats["early_stopped"] is True
        assert stats["matches_found"] >= 50
        # Vektörize edilen satır sayısı target'a yakın olmalı; tüm 2000 değil
        assert stats["lines_vectorized"] < 200

    def test_streaming_empty_pattern_returns_empty(self, tmp_corpus):
        """Pattern üretilmezse (örn. tüm kelimeler <3 char) boş dönmeli."""
        from kishi.krep import _krep_rg_streaming, vectorize_text
        q_vec = vectorize_text("data")  # geçerli q_vec
        matches, stats = _krep_rg_streaming(
            query_str="a to",  # build_rg_pattern None döner
            q_vec=q_vec,
            paths=[tmp_corpus],
            limit=5,
        )
        assert matches == []
        assert stats.get("reason") == "no_pattern"

    def test_streaming_non_utf8_files_handled(self, tmp_path):
        """Non-UTF8 byte içeren dosya hata vermemeli."""
        bad = tmp_path / "bad.bin"
        bad.write_bytes(b"auth\xf1login\xff\nokay text here\n")

        from kishi.krep import _krep_rg_streaming, vectorize_text
        q_vec = vectorize_text("auth")
        matches, stats = _krep_rg_streaming(
            query_str="auth login",
            q_vec=q_vec,
            paths=[str(tmp_path)],
            limit=5,
        )
        # Crash etmemeli; en azından stats döner
        assert isinstance(stats, dict)
        assert "elapsed_ms" in stats

    def test_streaming_returns_correct_tuple_format(self, tmp_corpus):
        """Match formatı (l_vec, similarity, output_str) olmalı."""
        from kishi.krep import _krep_rg_streaming, vectorize_text
        q_vec = vectorize_text("auth")
        matches, _ = _krep_rg_streaming(
            query_str="auth",
            q_vec=q_vec,
            paths=[tmp_corpus],
            limit=5,
        )
        assert len(matches) > 0
        for m in matches:
            assert len(m) == 3
            l_vec, sim, output_str = m
            assert isinstance(l_vec, list)
            assert len(l_vec) == 3
            assert isinstance(sim, float)
            assert 0.0 <= sim <= 1.0
            assert isinstance(output_str, str)
            # Renkli output beklenir
            assert "\033[" in output_str
