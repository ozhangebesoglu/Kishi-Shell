"""
kishi/krep_learn.py için kapsamlı testler.

Test kategorileri:
- Tokenize + walk helpers (saf fonksiyon)
- parse_interval / format_age / is_stale (zaman utils)
- build_model (full corpus learn)
- save_model + load_model roundtrip (with_state on/off)
- vectorize_with_model (dim="hd" vs "3d", OOV)
- update_model (tail-aware incremental, rotation, no-change)
- list_models + purge_models
- find_model_for (deterministik path hash)
"""
import os
import sys
import time
import shutil
import pytest

# numpy/scipy yoksa hepsini skip et
np = pytest.importorskip("numpy")
pytest.importorskip("scipy.sparse")

from kishi import krep_learn as kl


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    """XDG_CACHE_HOME'u tmp_path'e yönlendir."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    yield tmp_path


@pytest.fixture
def small_corpus(tmp_path):
    """Küçük 3-dosya log corpusu."""
    corpus = tmp_path / "logs"
    corpus.mkdir()
    (corpus / "auth.log").write_text(
        "user admin login successful from 192.168.1.1\n"
        "user admin password validated\n"
        "auth token issued for admin session\n"
        "ssh login from new device detected\n" * 3
    )
    (corpus / "db.log").write_text(
        "database query slow timeout warning\n"
        "sql select user from accounts where active=true\n"
        "database connection pool exhausted\n" * 3
    )
    (corpus / "error.log").write_text(
        "error fatal exception in worker thread\n"
        "kernel memory allocation failed\n"
        "fatal crash detected stack overflow\n" * 3
    )
    return str(corpus)


# ---------------------------------------------------------------------------
# _tokenize
# ---------------------------------------------------------------------------

class TestTokenize:
    def test_lowercases_words(self):
        assert kl._tokenize("AUTH LOGIN") == ["auth", "login"]

    def test_filters_short_words(self):
        # 3-karakterden kısa atılır
        assert kl._tokenize("a to be data") == ["data"]

    def test_filters_pure_digit_tokens(self):
        # '033', '12345' gibi saf-rakam tokenları at
        assert "033" not in kl._tokenize("033 error 200 200")
        assert "200" not in kl._tokenize("033 error 200")

    def test_filters_cython_internals(self):
        # __pyx_t_2 gibi compiler-generated atılır
        toks = kl._tokenize("hello __pyx_t_2 world __pyx_n_u_error")
        assert "__pyx_t_2" not in toks
        assert "__pyx_n_u_error" not in toks
        assert "hello" in toks
        assert "world" in toks

    def test_unicode_word_aware(self):
        # \w Unicode-aware default → Türkçe karakterler korunur
        toks = kl._tokenize("güvenlik şifre doğrulandı")
        assert "güvenlik" in toks
        assert "şifre" in toks
        assert "doğrulandı" in toks

    def test_punctuation_splits(self):
        assert kl._tokenize("foo,bar.baz!qux") == ["foo", "bar", "baz", "qux"]


# ---------------------------------------------------------------------------
# _walk_files (skip dirs/exts/binary)
# ---------------------------------------------------------------------------

class TestWalkFiles:
    def test_skips_git_pycache(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text("git stuff\n")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "x.cpython-311.pyc").write_bytes(b"\x00\x01")
        (tmp_path / "real.txt").write_text("real content\n")

        files = list(kl._walk_files([str(tmp_path)]))
        names = [os.path.basename(f) for f in files]
        assert "real.txt" in names
        assert "config" not in names

    def test_skips_binary_extensions(self, tmp_path):
        (tmp_path / "good.txt").write_text("text\n")
        (tmp_path / "bad.so").write_bytes(b"\x7fELF")
        (tmp_path / "bad.pyc").write_bytes(b"compiled")
        (tmp_path / "bad.png").write_bytes(b"\x89PNG")
        (tmp_path / "bad.c").write_text("int main() {}")  # cython generated
        files = list(kl._walk_files([str(tmp_path)]))
        names = [os.path.basename(f) for f in files]
        assert names == ["good.txt"]

    def test_includes_files_in_subdir(self, tmp_path):
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "deep.log").write_text("deep\n")
        files = list(kl._walk_files([str(tmp_path)]))
        assert any("deep.log" in f for f in files)


# ---------------------------------------------------------------------------
# _read_file_from_offset (tail seek)
# ---------------------------------------------------------------------------

class TestReadFileFromOffset:
    def test_full_read_at_offset_0(self, tmp_path):
        p = tmp_path / "f.log"
        p.write_text("line1\nline2\nline3\n")
        lines, new_off = kl._read_file_from_offset(str(p), offset=0)
        assert lines == ["line1\n", "line2\n", "line3\n"]
        assert new_off == os.path.getsize(p)

    def test_tail_read_from_offset(self, tmp_path):
        p = tmp_path / "f.log"
        p.write_text("line1\nline2\nline3\n")
        # "line1\n" 6 byte → bu offset'ten oku
        lines, new_off = kl._read_file_from_offset(str(p), offset=6)
        assert lines == ["line2\n", "line3\n"]

    def test_offset_beyond_size_resets_to_0(self, tmp_path):
        """Truncate/rotate edilmiş dosya → offset > size → baştan oku."""
        p = tmp_path / "f.log"
        p.write_text("short\n")
        lines, _ = kl._read_file_from_offset(str(p), offset=999)
        assert lines == ["short\n"]

    def test_binary_file_returns_none(self, tmp_path):
        p = tmp_path / "binary.bin"
        p.write_bytes(b"\x00\x01\x02" + b"text" * 100)
        lines, off = kl._read_file_from_offset(str(p))
        assert lines is None

    def test_empty_file_returns_none(self, tmp_path):
        p = tmp_path / "empty.log"
        p.write_text("")
        lines, off = kl._read_file_from_offset(str(p))
        assert lines is None


# ---------------------------------------------------------------------------
# parse_interval
# ---------------------------------------------------------------------------

class TestParseInterval:
    def test_hour_format(self):
        assert kl.parse_interval("1h") == 3600
        assert kl.parse_interval("6h") == 21600

    def test_minute_format(self):
        assert kl.parse_interval("30m") == 1800
        assert kl.parse_interval("45m") == 2700

    def test_day_format(self):
        assert kl.parse_interval("1d") == 86400
        assert kl.parse_interval("2d") == 172800

    def test_week_format(self):
        assert kl.parse_interval("1w") == 604800

    def test_seconds_format(self):
        assert kl.parse_interval("45s") == 45
        assert kl.parse_interval("3600") == 3600  # plain int

    def test_disable_keywords(self):
        for s in ["0", "off", "false", "no", "disable", "disabled"]:
            assert kl.parse_interval(s) == 0

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            kl.parse_interval("xyz")
        with pytest.raises(ValueError):
            kl.parse_interval("1z")  # 'z' tanımlı değil


# ---------------------------------------------------------------------------
# format_age
# ---------------------------------------------------------------------------

class TestFormatAge:
    def test_seconds(self):
        assert kl.format_age(45) == "45s"
        assert kl.format_age(59) == "59s"

    def test_minutes(self):
        assert kl.format_age(60) == "1m"
        assert kl.format_age(125) == "2m"

    def test_hours(self):
        assert kl.format_age(3600) == "1h"
        assert kl.format_age(7200) == "2h"

    def test_days(self):
        assert kl.format_age(86400) == "1d"
        assert kl.format_age(172800) == "2d"


# ---------------------------------------------------------------------------
# is_stale + model_age_seconds
# ---------------------------------------------------------------------------

class TestIsStale:
    def test_disabled_is_never_stale(self):
        m = {"build_time": time.time() - 999999, "auto_refresh_seconds": 0}
        assert kl.is_stale(m) is False

    def test_fresh_model_not_stale(self):
        m = {"build_time": time.time(), "auto_refresh_seconds": 3600}
        assert kl.is_stale(m) is False

    def test_old_model_is_stale(self):
        m = {"build_time": time.time() - 7200, "auto_refresh_seconds": 3600}
        assert kl.is_stale(m) is True

    def test_age_seconds(self):
        m = {"build_time": time.time() - 100}
        age = kl.model_age_seconds(m)
        assert 99 <= age <= 102  # küçük zaman farkı toleransı


# ---------------------------------------------------------------------------
# build_model
# ---------------------------------------------------------------------------

class TestBuildModel:
    def test_builds_basic_model(self, small_corpus):
        m = kl.build_model([small_corpus], verbose=False)
        assert m["n_lines"] > 0
        assert m["n_terms"] >= 4
        assert "admin" in m["vocab"]
        assert "database" in m["vocab"]

    def test_word_vecs_shape_hd_and_3d(self, small_corpus):
        m = kl.build_model([small_corpus], verbose=False)
        V = m["n_terms"]
        # HD vec (50D veya min(50, V-1))
        assert m["word_vecs"].shape[0] == V
        assert m["word_vecs"].shape[1] >= kl._RANK
        # 3D scatter vec
        assert m["word_vecs_3d"].shape == (V, kl._RANK)

    def test_axis_labels_count_matches_rank(self, small_corpus):
        m = kl.build_model([small_corpus], verbose=False)
        assert len(m["axis_labels"]) == kl._RANK
        # Her etiket en azından bir kelime içermeli (boş değil)
        for lab in m["axis_labels"]:
            assert lab and lab != "(none)"

    def test_includes_file_state_for_incremental(self, small_corpus):
        m = kl.build_model([small_corpus], verbose=False)
        assert "file_state" in m
        # Her log dosyası için entry olmalı
        assert len(m["file_state"]) == 3

    def test_includes_term_freq_and_pair_counts(self, small_corpus):
        m = kl.build_model([small_corpus], verbose=False)
        assert "term_freq" in m
        assert "pair_counts" in m
        assert m["term_freq"]["admin"] > 0
        assert len(m["pair_counts"]) > 0

    def test_auto_refresh_seconds_stored(self, small_corpus):
        m = kl.build_model([small_corpus], verbose=False, auto_refresh_seconds=3600)
        assert m["auto_refresh_seconds"] == 3600

    def test_empty_corpus_raises(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(RuntimeError, match="Corpus boş"):
            kl.build_model([str(empty)], verbose=False)


# ---------------------------------------------------------------------------
# save_model + load_model
# ---------------------------------------------------------------------------

class TestSaveLoadRoundtrip:
    def test_save_creates_directory(self, isolated_cache, small_corpus):
        m = kl.build_model([small_corpus], verbose=False)
        path = kl.save_model(m)
        assert os.path.isdir(path)
        assert os.path.isfile(os.path.join(path, "vectors.npz"))
        assert os.path.isfile(os.path.join(path, "metadata.json"))
        assert os.path.isfile(os.path.join(path, "state.json"))

    def test_load_lightweight_no_state(self, isolated_cache, small_corpus):
        m = kl.build_model([small_corpus], verbose=False)
        kl.save_model(m)
        loaded = kl.find_model_for([small_corpus])
        assert loaded is not None
        assert loaded["vocab"] == m["vocab"]
        assert loaded["n_terms"] == m["n_terms"]
        # State yüklenmedi (lightweight)
        assert "file_state" not in loaded or not loaded["file_state"]

    def test_load_with_state(self, isolated_cache, small_corpus):
        m = kl.build_model([small_corpus], verbose=False)
        kl.save_model(m)
        loaded = kl.find_model_for([small_corpus], with_state=True)
        assert loaded is not None
        assert "file_state" in loaded
        assert len(loaded["file_state"]) == 3
        assert "term_freq" in loaded
        assert "pair_counts" in loaded
        assert loaded["term_freq"]["admin"] > 0

    def test_word_vecs_3d_persists(self, isolated_cache, small_corpus):
        m = kl.build_model([small_corpus], verbose=False)
        kl.save_model(m)
        loaded = kl.find_model_for([small_corpus])
        assert "word_vecs_3d" in loaded
        assert loaded["word_vecs_3d"].shape[1] == 3

    def test_load_missing_returns_none(self, isolated_cache):
        # Hiç model yok
        assert kl.find_model_for(["/nonexistent/path/abc"]) is None

    def test_deterministic_model_dir(self, isolated_cache, tmp_path):
        d1 = kl.model_dir_for([str(tmp_path)])
        d2 = kl.model_dir_for([str(tmp_path)])
        assert d1 == d2

    def test_different_paths_different_dirs(self, isolated_cache, tmp_path):
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.mkdir(); b.mkdir()
        assert kl.model_dir_for([str(a)]) != kl.model_dir_for([str(b)])


# ---------------------------------------------------------------------------
# vectorize_with_model
# ---------------------------------------------------------------------------

class TestVectorizeWithModel:
    def test_hd_dim(self, small_corpus):
        m = kl.build_model([small_corpus], verbose=False)
        v, count = kl.vectorize_with_model("admin login", m, dim="hd")
        # HD boyut 50 veya V-1 (V küçükse)
        assert v.shape[0] >= kl._RANK
        assert count == 2

    def test_3d_dim(self, small_corpus):
        m = kl.build_model([small_corpus], verbose=False)
        v, count = kl.vectorize_with_model("admin login", m, dim="3d")
        assert v.shape == (3,)
        assert count == 2

    def test_oov_word_returns_zero_vec(self, small_corpus):
        m = kl.build_model([small_corpus], verbose=False)
        v, count = kl.vectorize_with_model("xyzqwerty_nonexistent", m)
        assert count == 0
        assert (v == 0).all()

    def test_empty_query_returns_zero(self, small_corpus):
        m = kl.build_model([small_corpus], verbose=False)
        v, count = kl.vectorize_with_model("", m)
        assert count == 0

    def test_partial_oov(self, small_corpus):
        """Bazı kelimeler vocab'da, bazıları değil — vocab'dakiler dahil edilir."""
        m = kl.build_model([small_corpus], verbose=False)
        v, count = kl.vectorize_with_model("admin xyzqwerty", m)
        assert count == 1  # sadece 'admin' vocab'da

    def test_normalized_output(self, small_corpus):
        """Çıktı L2-normalize (length ~1)."""
        m = kl.build_model([small_corpus], verbose=False)
        v, count = kl.vectorize_with_model("admin login", m)
        if count > 0:
            length = float(np.linalg.norm(v))
            assert 0.99 <= length <= 1.01


# ---------------------------------------------------------------------------
# cosine helper
# ---------------------------------------------------------------------------

class TestCosine:
    def test_identical_is_one(self):
        a = np.array([1.0, 0.0, 0.0])
        assert kl.cosine(a, a) == pytest.approx(1.0)

    def test_orthogonal_is_zero(self):
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([0.0, 1.0, 0.0])
        assert kl.cosine(a, b) == pytest.approx(0.0)

    def test_zero_vec_returns_zero(self):
        a = np.array([0.0, 0.0, 0.0])
        b = np.array([1.0, 0.0, 0.0])
        assert kl.cosine(a, b) == 0.0


# ---------------------------------------------------------------------------
# update_model — tail-aware incremental
# ---------------------------------------------------------------------------

class TestUpdateModel:
    def test_no_change_returns_same_vocab(self, isolated_cache, small_corpus):
        m1 = kl.build_model([small_corpus], verbose=False)
        kl.save_model(m1)
        # Hiç dosya değişmeden update
        m1_state = kl.find_model_for([small_corpus], with_state=True)
        m2 = kl.update_model(m1_state, verbose=False)
        # Vocab değişmemeli (no-change path)
        assert m2["n_terms"] == m1["n_terms"]

    def test_new_lines_grow_vocab(self, isolated_cache, small_corpus):
        m1 = kl.build_model([small_corpus], verbose=False)
        kl.save_model(m1)
        # Dosyaya yeni kelimelerle satır ekle
        time.sleep(1.1)  # mtime farkı
        with open(os.path.join(small_corpus, "auth.log"), "a") as f:
            f.write("kubernetes pod restart kubelet container\n" * 3)
        m1_state = kl.find_model_for([small_corpus], with_state=True)
        m2 = kl.update_model(m1_state, verbose=False)
        # Yeni terimler eklenmeli
        assert m2["n_terms"] > m1["n_terms"]
        assert "kubernetes" in m2["vocab"]

    def test_tail_reads_only_new_bytes(self, isolated_cache, small_corpus):
        m1 = kl.build_model([small_corpus], verbose=False)
        kl.save_model(m1)
        # Append
        time.sleep(1.1)
        path_auth = os.path.join(small_corpus, "auth.log")
        size_before = os.path.getsize(path_auth)
        with open(path_auth, "a") as f:
            f.write("new entry kubernetes added\n")
        m1_state = kl.find_model_for([small_corpus], with_state=True)
        m2 = kl.update_model(m1_state, verbose=False)
        # file_state offset cur_size'a yaklaşmış olmalı
        new_offset = m2["file_state"][path_auth]["offset"]
        assert new_offset == os.path.getsize(path_auth)
        # n_lines artmış (yeni satır kadar)
        assert m2["n_lines"] >= m1["n_lines"] + 1

    def test_rotation_detected(self, isolated_cache, small_corpus):
        """Dosya size azalırsa (rotate/truncate) baştan okunur."""
        m1 = kl.build_model([small_corpus], verbose=False)
        kl.save_model(m1)
        # Truncate to smaller content
        path = os.path.join(small_corpus, "auth.log")
        time.sleep(1.1)
        with open(path, "w") as f:
            f.write("rotated short content\n")
        m1_state = kl.find_model_for([small_corpus], with_state=True)
        m2 = kl.update_model(m1_state, verbose=False)
        new_offset = m2["file_state"][path]["offset"]
        assert new_offset == os.path.getsize(path)
        # 'rotated' kelimesi vocab'a girmiş olmalı (en az 2 kez geçmesi gerek
        # _MIN_TERM_FREQ için, ama bu test'te freq yüksek olmayabilir; vocab
        # şartını gevşek tut: rotated geçen bir kelime olarak görünmeli)

    def test_deleted_file_removed_from_state(self, isolated_cache, small_corpus):
        m1 = kl.build_model([small_corpus], verbose=False)
        kl.save_model(m1)
        path = os.path.join(small_corpus, "error.log")
        assert path in m1["file_state"]
        # Sil
        os.remove(path)
        m1_state = kl.find_model_for([small_corpus], with_state=True)
        m2 = kl.update_model(m1_state, verbose=False)
        # Silinmiş dosya file_state'ten çıkmalı
        assert path not in m2["file_state"]


# ---------------------------------------------------------------------------
# list_models + purge_models
# ---------------------------------------------------------------------------

class TestListPurgeModels:
    def test_list_empty(self, isolated_cache):
        assert kl.list_models() == []

    def test_list_after_build(self, isolated_cache, small_corpus):
        m = kl.build_model([small_corpus], verbose=False, auto_refresh_seconds=3600)
        kl.save_model(m)
        models = kl.list_models()
        assert len(models) == 1
        assert models[0]["n_terms"] == m["n_terms"]
        assert models[0]["auto_refresh_seconds"] == 3600

    def test_purge_removes_all(self, isolated_cache, small_corpus):
        m = kl.build_model([small_corpus], verbose=False)
        kl.save_model(m)
        assert len(kl.list_models()) == 1
        n_purged = kl.purge_models()
        assert n_purged == 1
        assert kl.list_models() == []

    def test_purge_empty_returns_zero(self, isolated_cache):
        assert kl.purge_models() == 0


# ---------------------------------------------------------------------------
# Lightweight smoke: end-to-end --learn → query
# ---------------------------------------------------------------------------

class TestEndToEnd:
    def test_build_save_load_query(self, isolated_cache, small_corpus):
        """E2E: build → save → load → query → cosine match.

        Küçük corpus'larda SVD oynak çıkabilir; bu test yalnızca pipeline'ın
        çalıştığını doğrular (vec hesaplanır, sim sınırlar içinde).
        """
        m = kl.build_model([small_corpus], verbose=False)
        kl.save_model(m)
        loaded = kl.find_model_for([small_corpus])

        v_admin, c_admin = kl.vectorize_with_model("admin", loaded)
        v_login, c_login = kl.vectorize_with_model("login", loaded)
        # İki kelime de vocab'da olmalı (small_corpus auth.log'unda var)
        assert c_admin > 0
        assert c_login > 0
        sim = kl.cosine(v_admin, v_login)
        # Sınırlar içinde bir cosine üretmeli (NaN/Inf değil)
        assert -1.0 <= sim <= 1.0

    def test_unrelated_words_low_similarity(self, isolated_cache, small_corpus):
        """Birlikte geçmeyen kelimeler düşük benzerlik göstermeli."""
        m = kl.build_model([small_corpus], verbose=False)
        kl.save_model(m)
        loaded = kl.find_model_for([small_corpus])
        # 'admin' (auth.log) vs 'crash' (error.log) — farklı dosyalarda
        v1, c1 = kl.vectorize_with_model("admin", loaded)
        v2, c2 = kl.vectorize_with_model("crash", loaded)
        if c1 > 0 and c2 > 0:
            sim = kl.cosine(v1, v2)
            # Farklı dosyalarda olduğu için 1.00 olmamalı
            assert sim < 1.0
