"""
Krep performans benchmark + regresyon kontrolü.

Çalıştırma: pytest tests/test_krep_perf.py -v -s --tb=no

Sentetik 200-dosya × 100-satır korpusu üretir, baseline + post-change ölçer.
"""
import os
import time
import shutil
import contextlib
import pytest

KEYWORDS = [
    "database connection error", "auth token expired",
    "user login successful", "file save complete",
    "system startup ok", "memory limit reached",
    "network timeout occurred", "permission denied for user",
]
NOISE = [
    "lorem ipsum dolor sit amet", "the quick brown fox jumps",
    "consectetur adipiscing elit", "sed do eiusmod tempor incididunt",
]


def _make_corpus(root, num_files=200, lines_per_file=100):
    for i in range(num_files):
        with open(os.path.join(root, f"log_{i:04d}.txt"), "w") as f:
            for j in range(lines_per_file):
                line = KEYWORDS[(i + j) % len(KEYWORDS)] if j % 5 == 0 \
                    else NOISE[(i * j) % len(NOISE)] + f" [seq {j}]"
                f.write(line + "\n")


@contextlib.contextmanager
def _silent():
    devnull = open(os.devnull, "w")
    import sys
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = devnull, devnull
    try:
        yield
    finally:
        sys.stdout, sys.stderr = old_out, old_err
        devnull.close()


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    root = tmp_path_factory.mktemp("krep_perf")
    _make_corpus(str(root))
    return str(root)


def test_recursive_search_under_threshold(corpus, capsys):
    """200 dosya × 100 satır 'login authorization' araması ≤ 100ms olmalı.

    Baseline (rg-streaming öncesi): ~1900ms
    Post-change beklenti: ~40ms (rg varsa) veya ~1900ms (rg yoksa, fallback)
    Bu test, rg'nin sistemde olduğunu varsayar.
    """
    if shutil.which("rg") is None:
        pytest.skip("ripgrep not installed; benchmark target unavailable")

    from kishi.krep import krep_search

    # Warm-up: import + first JIT
    with _silent():
        krep_search("login", [corpus], recursive=True, limit=5)

    # Üç ölçüm ortalaması
    times = []
    for _ in range(3):
        t0 = time.perf_counter()
        with _silent():
            rc = krep_search("login authorization", [corpus],
                             recursive=True, limit=10)
        times.append((time.perf_counter() - t0) * 1000)
        assert rc == 0

    avg = sum(times) / len(times)
    print(f"\n[BENCH] recursive 'login auth' avg={avg:.1f}ms "
          f"min={min(times):.1f}ms max={max(times):.1f}ms")

    # Implement sonrası hedef: 100ms. Baseline'da bu fail edecek (TDD).
    assert avg < 100, f"Recursive search too slow: {avg:.1f}ms (target <100ms)"


def test_no_rg_fallback_still_works(corpus, capsys, monkeypatch):
    """rg sistemde olsa bile --no-rg ile fallback yolu çalışmalı."""
    from kishi.krep import krep_search
    # _HAS_RG'yi geçici olarak False yap
    import kishi.krep as krep_mod
    monkeypatch.setattr(krep_mod, "_HAS_RG", False)

    with _silent():
        rc = krep_search("login", [corpus], recursive=True, limit=5)
    assert rc == 0


def test_p99_under_strict_threshold(corpus):
    """10 ardışık koşunun p99'u ≤ 50ms olmalı (variance guard)."""
    if shutil.which("rg") is None:
        pytest.skip("ripgrep not installed")
    from kishi.krep import krep_search
    import kishi.krep as krep_mod

    # Warm-up
    with _silent():
        krep_search("login", [corpus], recursive=True, limit=5)

    times = []
    for _ in range(10):
        krep_mod.CONCEPT_CACHE.clear()
        t0 = time.perf_counter()
        with _silent():
            krep_search("login authorization", [corpus],
                        recursive=True, limit=5)
        times.append((time.perf_counter() - t0) * 1000)

    s = sorted(times)
    p99 = s[int(len(s) * 0.99)] if len(s) > 1 else s[0]
    p50 = s[len(s) // 2]
    print(f"\n[BENCH] p50={p50:.1f}ms p99={p99:.1f}ms max={max(times):.1f}ms")
    # CI guard: p99 < 50ms. Bu eşik ölçümlerden ~5x güvenlik payıyla seçildi
    # (gerçek p99 genelde 10ms civarı).
    assert p99 < 50, f"p99 latency too high: {p99:.1f}ms (target <50ms)"


def test_no_memory_leak_100_iterations(corpus):
    """100 ardışık krep_search çağrısı RSS'te ciddi artış üretmemeli."""
    if shutil.which("rg") is None:
        pytest.skip("ripgrep not installed")
    try:
        import resource
    except ImportError:
        pytest.skip("resource module not available (non-Unix)")

    import gc
    from kishi.krep import krep_search
    import kishi.krep as krep_mod

    # Warm-up
    with _silent():
        krep_search("login", [corpus], recursive=True, limit=5)

    gc.collect()
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    for _ in range(100):
        krep_mod.CONCEPT_CACHE.clear()
        with _silent():
            krep_search("login auth", [corpus], recursive=True, limit=5)
    gc.collect()
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

    delta = rss_after - rss_before
    print(f"\n[MEM] RSS before={rss_before:.1f}MB after={rss_after:.1f}MB "
          f"delta={delta:.1f}MB after 100 calls")
    # 100 çağrıda 10MB'dan fazla artış memory leak'e işaret eder
    # (gerçek ölçümlerde 0.3MB civarı).
    assert delta < 10, f"Potential memory leak: {delta:.1f}MB after 100 calls"


def test_thread_safety_smoke(corpus):
    """8 thread × 5 paralel çağrı; hiç exception olmamalı."""
    if shutil.which("rg") is None:
        pytest.skip("ripgrep not installed")

    import threading
    import builtins
    from kishi.krep import krep_search

    results = {"ok": 0, "fail": 0, "errors": []}
    lock = threading.Lock()

    # Print'i tüm threadlerde no-op yap (capsys thread-safe değil)
    _real_print = builtins.print
    builtins.print = lambda *a, **k: None

    def worker():
        for _ in range(5):
            try:
                rc = krep_search("login", [corpus], recursive=True, limit=3)
                with lock:
                    results["ok" if rc == 0 else "fail"] += 1
            except Exception as e:
                with lock:
                    results["errors"].append(str(e))

    try:
        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads: t.start()
        for t in threads: t.join()
    finally:
        builtins.print = _real_print

    assert results["errors"] == [], (
        f"Thread safety violated: {len(results['errors'])} exceptions: "
        f"{results['errors'][:3]}"
    )
    assert results["ok"] == 40, (
        f"Expected 40 successful runs, got ok={results['ok']} fail={results['fail']}"
    )
