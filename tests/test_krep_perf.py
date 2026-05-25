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
