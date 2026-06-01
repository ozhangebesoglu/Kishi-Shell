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
    """_krep_rg_streaming sadece ripgrep sistemde varsa çalışır.
    Yoksa rg_spawn_failed döner; class-level skip uygula."""

    @pytest.fixture(autouse=True)
    def _require_rg(self):
        import shutil
        if shutil.which("rg") is None:
            pytest.skip("ripgrep not installed; _krep_rg_streaming requires it")

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
            # Merge sonrası tuple 4-element: (l_vec, sim, output_str, raw_text).
            # raw_text scatter 3D PCA-3 reduce için gerek (krep_learn entegrasyonu).
            assert len(m) in (3, 4)
            l_vec, sim, output_str = m[0], m[1], m[2]
            assert isinstance(l_vec, list) or hasattr(l_vec, "shape")
            # Keyword mode 3D, HD model mode 50D
            try:
                vec_len = len(l_vec)
            except TypeError:
                vec_len = l_vec.shape[0]
            assert vec_len >= 3
            assert isinstance(sim, float)
            assert 0.0 <= sim <= 1.0
            assert isinstance(output_str, str)
            assert "\033[" in output_str
            if len(m) == 4:
                assert isinstance(m[3], str)  # raw_text


class TestKrepSearchDispatch:
    @pytest.fixture
    def small_corpus(self, tmp_path):
        (tmp_path / "errors.log").write_text(
            "database connection error\n"
            "user login successful\n"
            "system timeout occurred\n"
        )
        return str(tmp_path)

    def test_dispatch_uses_rg_when_available(self, small_corpus, capsys):
        """rg varsa, krep_search rg-streaming yolundan geçmeli."""
        from kishi.krep import krep_search, _HAS_RG
        if not _HAS_RG:
            pytest.skip("rg not installed")
        rc = krep_search("database error", [small_corpus], limit=5)
        captured = capsys.readouterr()
        assert rc == 0
        assert "database connection error" in captured.out

    def test_dispatch_falls_back_when_rg_disabled(self, small_corpus,
                                                  capsys, monkeypatch):
        """_HAS_RG=False olduğunda fallback yolu çalışmalı."""
        import kishi.krep as krep_mod
        monkeypatch.setattr(krep_mod, "_HAS_RG", False)

        rc = krep_mod.krep_search("database error", [small_corpus], limit=5)
        captured = capsys.readouterr()
        assert rc == 0
        assert "database connection error" in captured.out

    def test_dispatch_stdin_skips_rg(self, monkeypatch, capsys):
        """Stdin modu rg'yi bypass etmeli (rg dosya argümanı bekler)."""
        from kishi.krep import krep_search
        monkeypatch.setattr(
            "sys.stdin.readline",
            iter([
                "database connection error\n",
                "random other line\n",
                "",
            ]).__next__,
        )
        rc = krep_search("database", [], limit=5)
        captured = capsys.readouterr()
        assert rc == 0
        assert "database connection error" in captured.out

    def test_dispatch_no_matches_returns_one(self, small_corpus, capsys):
        """Eşleşme bulunmazsa veya semantic vektör üretilemezse rc=1 dönmeli."""
        from kishi.krep import krep_search
        # Hem EN (default) hem TR mesajları kabul:
        # - "zzzqwerty" → q_vec=[0,0,0] → "could not extract" / "çıkarılamadı"
        # - veya q_vec dolu + 0 match → "no results" / "bulunamadı"
        rc = krep_search("zzzqwerty", [small_corpus], limit=5)
        assert rc == 1
        captured = capsys.readouterr()
        out = captured.out + captured.err
        assert any(s in out for s in (
            "bulunamadı", "çıkarılamadı",
            "no results", "could not extract",
            "no semantically similar",
        )), f"Unexpected output: {out[:200]!r}"

    def test_dispatch_recursive_passes_to_rg(self, tmp_path, capsys):
        """Recursive mod rg'ye -r olmadan da paths verince rg recurse eder."""
        from kishi.krep import krep_search, _HAS_RG
        if not _HAS_RG:
            pytest.skip("rg not installed")
        subdir = tmp_path / "deeper"
        subdir.mkdir()
        (subdir / "buried.log").write_text("auth token expired\n")
        rc = krep_search("auth login", [str(tmp_path)], recursive=True, limit=5)
        captured = capsys.readouterr()
        assert rc == 0
        assert "auth token expired" in captured.out

    def test_dispatch_rg_spawn_failed_falls_back(self, tmp_path, capsys, monkeypatch):
        """rg spawn fail olursa fallback walker devreye girmeli ve uyarı yazılmalı."""
        # rg'yi mock'la: subprocess.Popen OSError fırlatıyor gibi yap
        from kishi.krep import krep_search
        import kishi.krep as krep_mod
        import subprocess as _sp

        original_popen = _sp.Popen

        def boom_popen(cmd, *a, **kw):
            # Sadece rg çağrısında OSError fırlat
            if cmd and cmd[0] == "rg":
                raise OSError("simulated spawn failure")
            return original_popen(cmd, *a, **kw)

        monkeypatch.setattr(_sp, "Popen", boom_popen)
        monkeypatch.setattr(krep_mod, "_HAS_RG", True)  # rg yokmuş gibi DEĞIL

        (tmp_path / "log.txt").write_text("auth login succeeded\n")
        rc = krep_search("auth login", [str(tmp_path)], recursive=True, limit=5)
        captured = capsys.readouterr()
        # Fallback'e düştüğü için uyarı stderr'de olmalı
        assert "spawn başarısız" in captured.err or "ripgrep spawn" in captured.err
        # Fallback walker eşleşmeyi bulmalı
        assert rc == 0
        assert "auth login succeeded" in captured.out

    def test_streaming_hard_timeout_safety_net(self, tmp_path, monkeypatch):
        """hard_timeout parametresi tetiklenebilir — sıfır timeout ile."""
        import shutil
        if shutil.which("rg") is None:
            pytest.skip("ripgrep not installed")
        from kishi.krep import _krep_rg_streaming, vectorize_text
        # 100 dosya × 50 satır match
        for i in range(100):
            (tmp_path / f"f{i}.txt").write_text("auth login\n" * 50)

        q_vec = vectorize_text("auth login")
        # hard_timeout=0.001 → ilk iterasyondan sonra tetiklenmeli
        matches, stats = _krep_rg_streaming(
            query_str="auth login",
            q_vec=q_vec,
            paths=[str(tmp_path)],
            limit=5,
            hard_timeout=0.001,
        )
        # Ya hard_timeout ya early_stop_factor tetiklendi; her halükarda early_stopped True
        # ve matches sınırlı kaldı (5000 değil, çok daha az)
        assert stats["early_stopped"] is True
        assert stats["matches_found"] < 100  # 5000 değil

    def test_streaming_terminates_cleanly_on_early_stop(self, tmp_path):
        """Early-stop sonrası proc.wait() makul sürede dönmeli (≤ 1s).

        Pipe buffer dolu olsa bile stdout.close() SIGPIPE göndereceği
        için rg anında çıkmalı. 3 saniyelik regresyon bug'ı yok."""
        import shutil
        if shutil.which("rg") is None:
            pytest.skip("ripgrep not installed")
        import time as _t
        from kishi.krep import _krep_rg_streaming, vectorize_text
        # Yeterince satır üret ki early-stop kesin tetiklensin
        for i in range(500):
            (tmp_path / f"f{i}.txt").write_text("auth login\n" * 20)
        q_vec = vectorize_text("auth")

        t0 = _t.perf_counter()
        matches, stats = _krep_rg_streaming(
            query_str="auth login",
            q_vec=q_vec,
            paths=[str(tmp_path)],
            limit=5,
        )
        elapsed = _t.perf_counter() - t0
        assert stats["early_stopped"] is True
        # 1 saniyenin altında dönmeli — proc.wait gecikmesi olmamalı
        assert elapsed < 1.0, (
            f"Early-stop should be fast: took {elapsed:.2f}s "
            f"(pipe close regression?)"
        )
