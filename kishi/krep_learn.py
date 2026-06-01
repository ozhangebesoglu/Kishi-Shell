"""
Krep Local Semantic Model — PPMI + SVD rank-3

Per-corpus latent semantic embedding (LSA). Manuel keyword listesinden
bağımsız; corpus'un kendi kelime dağılımından 3D anlam ekseni çıkarır.

Algoritma:
  1. Tüm dosyaları satır satır oku, kelimeleri tokenize et (vocab).
  2. Her satırı "context window" olarak ele al; cooccurrence sayımı.
  3. PPMI (Positive Pointwise Mutual Information) ile normalize et.
  4. SVD rank-3 ile her kelimeye 3D vektör ata.
  5. Eksenleri otomatik etiketle (her eksenin top-5 kelimesi).

Çıktı: ~/.cache/kishi/krep_models/<path>_<hash>/
  - vectors.npz     numerik veri (word_vecs)
  - metadata.json   vocab, axis_labels, source_paths, build_time
"""
import os
import re
import sys
import json
import time
import hashlib
import math
from collections import Counter, defaultdict

try:
    import numpy as np
    from scipy.sparse import csr_matrix
    from scipy.sparse.linalg import svds
    LEARN_AVAILABLE = True
except ImportError:
    LEARN_AVAILABLE = False


# --- Sabitler ---
_MIN_TOKEN_LEN = 3       # 3-karakterden kısa kelimeler atılır (a, to, if)
_MIN_TERM_FREQ = 2       # 1 kez geçen kelimeler atılır (gürültü/typo)
_MAX_VOCAB = 50_000      # Üst sınır
_RANK = 3                # 3D embedding
_AXIS_TOP_N = 5          # Eksen auto-label kelime sayısı
_MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB üstü dosya atlanır
_SKIP_DIRS = (
    "/.git/", "/__pycache__/", "/.mypy_cache/", "/.pytest_cache/",
    "/.venv/", "/venv/", "/node_modules/", "/build/", "/dist/",
    "/.cache/", "/.serena/", "/.vscode/",
)
_SKIP_EXTS = (
    ".pyc", ".so", ".o", ".a", ".dll", ".dylib", ".class",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".ico",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z",
    ".mp3", ".mp4", ".webm", ".mkv", ".wav", ".ogg",
    ".pkl", ".npz", ".npy", ".bin",
    ".coverage", ".db", ".sqlite",
    # Cython generated — insan kodu değil, vocab'i bozar
    ".c", ".cpp", ".cxx", ".cc", ".h", ".hpp",
    # Lock dosyaları, generated artifact'lar
    ".lock", ".min.js", ".min.css", ".map",
)
# Sample first N bytes to detect binary (NUL/non-UTF8)
_BINARY_SAMPLE_BYTES = 512


def _cache_dir():
    """Model klasörü: $XDG_CACHE_HOME/kishi/krep_models/."""
    xdg = os.environ.get("XDG_CACHE_HOME") or os.path.join(
        os.environ.get("HOME", "/"), ".cache"
    )
    return os.path.join(xdg, "kishi", "krep_models")


def model_dir_for(source_paths):
    """source_paths kombinasyonu için deterministik klasör yolu."""
    canon = "|".join(sorted(os.path.abspath(p) for p in source_paths))
    h = hashlib.blake2b(canon.encode("utf-8"), digest_size=6).hexdigest()
    primary = os.path.basename(os.path.abspath(source_paths[0])) or "root"
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", primary)[:40]
    return os.path.join(_cache_dir(), f"{safe}_{h}")


def _iter_lines(paths, max_files=None):
    """paths altındaki dosyaları satır satır verir."""
    file_count = 0
    for root in paths:
        if not os.path.exists(root):
            continue
        if os.path.isfile(root):
            files_iter = [(os.path.dirname(root), [], [os.path.basename(root)])]
        else:
            files_iter = os.walk(root)
        for dirpath, _, filenames in files_iter:
            if any(skip in dirpath for skip in _SKIP_DIRS):
                continue
            for fname in filenames:
                if max_files and file_count >= max_files:
                    return
                # Extension filter
                low = fname.lower()
                if any(low.endswith(ext) for ext in _SKIP_EXTS):
                    continue
                # No-extension binary names (.coverage)
                if fname.startswith(".") and "." not in fname[1:]:
                    if low in (".coverage", ".ds_store"):
                        continue
                fpath = os.path.join(dirpath, fname)
                try:
                    sz = os.path.getsize(fpath)
                    if sz > _MAX_FILE_SIZE or sz == 0:
                        continue
                    # Binary detection: NUL byte içeriyorsa atla
                    with open(fpath, "rb") as f:
                        sample = f.read(_BINARY_SAMPLE_BYTES)
                    if b"\x00" in sample:
                        continue
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            yield line
                except (OSError, IOError):
                    continue
                file_count += 1


def _tokenize(line):
    """Bir satırı küçük harfli kelime token'larına böl. Unicode-aware.

    Filtreler:
    - >= 3 karakter
    - En az 1 harf içermeli (saf-rakam tokenları '033', '12345' atılır)
    - '_' ile başlayan + rakam içerenler atılır (Cython __pyx_t_2 vb.)
    """
    out = []
    for w in re.findall(r"[\w]+", line.lower()):
        if len(w) < _MIN_TOKEN_LEN:
            continue
        # En az bir harf gerekli — pure-digit tokenları at
        if not any(c.isalpha() for c in w):
            continue
        # Cython/compiler internal token'ları at (__pyx_*, __cpp_*)
        if w.startswith("__") and any(c.isdigit() for c in w):
            continue
        out.append(w)
    return out


def build_model(source_paths, max_files=None, verbose=True):
    """PPMI + SVD ile corpus'tan 3D word embedding üret."""
    if not LEARN_AVAILABLE:
        raise RuntimeError(
            "krep --learn için numpy ve scipy gerekli. "
            "Kurulum: pip install numpy scipy"
        )

    # --- 1. Vocab + line tokens ---
    if verbose:
        print(f"[krep --learn] Scanning {len(source_paths)} path(s)...",
              file=sys.stderr)
    t0 = time.perf_counter()
    term_freq = Counter()
    doc_lines = []
    for line in _iter_lines(source_paths, max_files=max_files):
        toks = _tokenize(line)
        if not toks:
            continue
        unique_toks = set(toks)
        doc_lines.append(unique_toks)
        term_freq.update(unique_toks)

    n_lines = len(doc_lines)
    if n_lines == 0:
        raise RuntimeError(f"Corpus boş: {source_paths}")

    # --- 2. Vocab budama ---
    vocab_list = [w for w, c in term_freq.most_common(_MAX_VOCAB)
                  if c >= _MIN_TERM_FREQ]
    if len(vocab_list) < _RANK + 1:
        raise RuntimeError(
            f"Çok az unique terim ({len(vocab_list)}); en az {_RANK+1} gerekli."
        )
    vocab_idx = {w: i for i, w in enumerate(vocab_list)}
    V = len(vocab_list)
    if verbose:
        print(f"[krep --learn] Vocab: {V} terms, {n_lines} lines, "
              f"{time.perf_counter()-t0:.1f}s", file=sys.stderr)

    # --- 3. Cooccurrence matrix (sparse, symmetric) ---
    t1 = time.perf_counter()
    cooc = defaultdict(int)
    for toks in doc_lines:
        valid = sorted({vocab_idx[w] for w in toks if w in vocab_idx})
        for i, a in enumerate(valid):
            for b in valid[i+1:]:
                cooc[(a, b)] += 1

    if not cooc:
        raise RuntimeError("Cooccurrence empty.")
    rows, cols, data = [], [], []
    for (a, b), c in cooc.items():
        rows.append(a); cols.append(b); data.append(c)
        rows.append(b); cols.append(a); data.append(c)
    C = csr_matrix((data, (rows, cols)), shape=(V, V), dtype=np.float64)
    if verbose:
        print(f"[krep --learn] Cooccurrence: {len(cooc)} pairs, "
              f"{time.perf_counter()-t1:.1f}s", file=sys.stderr)

    # --- 4. PPMI normalize ---
    t2 = time.perf_counter()
    row_sums = np.asarray(C.sum(axis=1)).ravel()
    total = row_sums.sum()
    if total == 0:
        raise RuntimeError("Cooccurrence sum 0.")

    coo = C.tocoo()
    pmi_data = np.log((total * coo.data) /
                       (row_sums[coo.row] * row_sums[coo.col]))
    ppmi_data = np.maximum(pmi_data, 0.0)
    P = csr_matrix((ppmi_data, (coo.row, coo.col)), shape=(V, V))
    P.eliminate_zeros()
    if verbose:
        print(f"[krep --learn] PPMI: {P.nnz} non-zero, "
              f"{time.perf_counter()-t2:.1f}s", file=sys.stderr)

    # --- 5. SVD rank-3 ---
    t3 = time.perf_counter()
    k = _RANK
    if V <= k:
        raise RuntimeError(f"Vocab too small for rank-{k} SVD (V={V}).")
    U, sigma, _ = svds(P, k=k)
    order = np.argsort(-sigma)
    sigma = sigma[order]
    U = U[:, order]
    word_vecs = (U * np.sqrt(sigma)).astype(np.float32)  # (V, 3)
    if verbose:
        print(f"[krep --learn] SVD rank-{k}: σ={sigma.round(2).tolist()}, "
              f"{time.perf_counter()-t3:.1f}s", file=sys.stderr)

    # --- 6. Auto-label axes ---
    # Frequency-weighted seçim: nadir outlier kelimeleri elemine et.
    # En yüksek vec[ax] olan ama aynı zamanda yeterli sıklıkta geçen kelimeler.
    freq_arr = np.array([term_freq[vocab_list[i]] for i in range(V)], dtype=np.float32)
    # Logaritmik tartışım — yüksek-frekans bias'ını sınırla
    log_freq = np.log1p(freq_arr)
    axis_labels = []
    for ax in range(k):
        # Score = pozitif vec[ax] × log(freq)
        # Negatif yöndeki kelimeler etiket olmaz (eksen yönünü temsil etmez)
        pos_score = np.maximum(word_vecs[:, ax], 0.0) * log_freq
        # En az 5 kez geçmiş kelimelerden seç
        min_freq_mask = freq_arr >= 5
        scores = np.where(min_freq_mask, pos_score, -np.inf)
        top_idx = np.argsort(-scores)[:_AXIS_TOP_N]
        # Inf kalan olursa atla (yetersiz vocab)
        top_idx = [i for i in top_idx if scores[i] > -np.inf]
        label = " ".join(vocab_list[i] for i in top_idx) if top_idx else "(none)"
        axis_labels.append(label)
    if verbose:
        for i, lab in enumerate(axis_labels):
            print(f"[krep --learn] Axis {i}: {lab}", file=sys.stderr)

    elapsed = time.perf_counter() - t0
    if verbose:
        print(f"[krep --learn] Done in {elapsed:.1f}s "
              f"(V={V}, lines={n_lines})", file=sys.stderr)

    return {
        "vocab": vocab_list,
        "vocab_idx": vocab_idx,
        "word_vecs": word_vecs,
        "axis_labels": axis_labels,
        "build_time": time.time(),
        "source_paths": [os.path.abspath(p) for p in source_paths],
        "n_lines": n_lines,
        "n_terms": V,
        "elapsed_s": elapsed,
    }


def save_model(model, dir_path=None):
    """Modeli kaydet: vectors.npz (numerik) + metadata.json (text)."""
    if dir_path is None:
        dir_path = model_dir_for(model["source_paths"])
    os.makedirs(dir_path, exist_ok=True)
    # Numerik: word_vecs
    np.savez_compressed(
        os.path.join(dir_path, "vectors.npz"),
        word_vecs=model["word_vecs"],
    )
    # Metadata: vocab, labels, paths, times — JSON ile güvenli
    meta = {
        "vocab": model["vocab"],
        "axis_labels": model["axis_labels"],
        "build_time": model["build_time"],
        "source_paths": model["source_paths"],
        "n_lines": model["n_lines"],
        "n_terms": model["n_terms"],
        "format_version": 1,
    }
    with open(os.path.join(dir_path, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)
    return dir_path


def load_model(dir_path):
    """Modeli yükle. Eksik/bozuk path'te None döner."""
    if not LEARN_AVAILABLE:
        return None
    if not os.path.isdir(dir_path):
        return None
    npz_path = os.path.join(dir_path, "vectors.npz")
    json_path = os.path.join(dir_path, "metadata.json")
    if not (os.path.isfile(npz_path) and os.path.isfile(json_path)):
        return None
    try:
        # vectors.npz — sadece float32 array, pickle yok
        with np.load(npz_path) as data:
            word_vecs = data["word_vecs"]
        with open(json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        vocab = meta["vocab"]
        return {
            "vocab": vocab,
            "vocab_idx": {w: i for i, w in enumerate(vocab)},
            "word_vecs": word_vecs,
            "axis_labels": meta["axis_labels"],
            "build_time": float(meta["build_time"]),
            "source_paths": meta["source_paths"],
            "n_lines": int(meta["n_lines"]),
            "n_terms": int(meta["n_terms"]),
        }
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None


def find_model_for(paths):
    """Verilen paths için kayıtlı model varsa yükle."""
    if not LEARN_AVAILABLE or not paths:
        return None
    return load_model(model_dir_for(paths))


def vectorize_with_model(text, model):
    """text'i model'in 3D uzayında vektörleştir."""
    tokens = _tokenize(text)
    if not tokens:
        return np.zeros(_RANK, dtype=np.float32), 0
    vocab_idx = model["vocab_idx"]
    word_vecs = model["word_vecs"]
    vecs = [word_vecs[vocab_idx[w]] for w in tokens if w in vocab_idx]
    if not vecs:
        return np.zeros(_RANK, dtype=np.float32), 0
    v = np.sum(vecs, axis=0)
    n = float(np.linalg.norm(v))
    if n > 0:
        v = v / n
    return v.astype(np.float32), len(vecs)


def cosine(a, b):
    """Cosine similarity, 3D float vektör."""
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def list_models():
    """Kayıtlı modellerin özetini döner."""
    d = _cache_dir()
    if not os.path.isdir(d):
        return []
    out = []
    for entry in sorted(os.listdir(d)):
        dir_path = os.path.join(d, entry)
        if not os.path.isdir(dir_path):
            continue
        m = load_model(dir_path)
        if m is None:
            continue
        size_kb = sum(
            os.path.getsize(os.path.join(dir_path, f))
            for f in os.listdir(dir_path)
        ) / 1024
        out.append({
            "dir": dir_path,
            "size_kb": size_kb,
            "n_terms": m["n_terms"],
            "n_lines": m["n_lines"],
            "build_time": m["build_time"],
            "source_paths": m["source_paths"],
            "axis_labels": m["axis_labels"],
        })
    return out


def purge_models():
    """Tüm modelleri sil. Silinen sayısını döner."""
    import shutil
    d = _cache_dir()
    if not os.path.isdir(d):
        return 0
    count = 0
    for entry in os.listdir(d):
        dir_path = os.path.join(d, entry)
        if os.path.isdir(dir_path):
            try:
                shutil.rmtree(dir_path)
                count += 1
            except OSError:
                pass
    return count
