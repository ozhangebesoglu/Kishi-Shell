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


def _walk_files(paths, max_files=None):
    """paths altındaki uygun dosya yollarını üret (filter dahil)."""
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
                low = fname.lower()
                if any(low.endswith(ext) for ext in _SKIP_EXTS):
                    continue
                if fname.startswith(".") and "." not in fname[1:]:
                    if low in (".coverage", ".ds_store"):
                        continue
                fpath = os.path.join(dirpath, fname)
                yield fpath
                file_count += 1


def _read_file_from_offset(fpath, offset=0):
    """Bir dosyayı offset'ten itibaren oku; satırları + son offset döner.

    Filter: boş, çok büyük, binary atlanır → (None, None) döner.
    """
    try:
        sz = os.path.getsize(fpath)
        if sz > _MAX_FILE_SIZE or sz == 0:
            return None, None
        if offset > sz:
            # truncate/rotate olmuş — baştan oku
            offset = 0
        # Binary detection (sadece ilk açışta)
        if offset == 0:
            with open(fpath, "rb") as f:
                sample = f.read(_BINARY_SAMPLE_BYTES)
            if b"\x00" in sample:
                return None, None
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(offset)
            lines = f.readlines()
            new_offset = f.tell()
        return lines, new_offset
    except (OSError, IOError):
        return None, None


def _file_state_entry(fpath, offset, mtime=None, size=None):
    """Bir dosya için state dict üret."""
    try:
        if mtime is None:
            mtime = os.path.getmtime(fpath)
        if size is None:
            size = os.path.getsize(fpath)
    except OSError:
        return None
    return {"offset": int(offset), "mtime": float(mtime), "size": int(size)}


def _iter_lines(paths, max_files=None):
    """LEGACY full-scan satır iteratörü (geriye uyum için)."""
    for fpath in _walk_files(paths, max_files):
        lines, _ = _read_file_from_offset(fpath, offset=0)
        if lines is None:
            continue
        for line in lines:
            yield line


def _scan_corpus(paths, prev_file_state=None, max_files=None, verbose=False):
    """Corpus'u tara, doc_lines (set of token indices listesi yerine ham
    string set) + güncellenen file_state döndür.

    prev_file_state varsa: değişmeyen dosyaları atla, sadece yeni satırları al
    (tail-aware). Rotation/truncate detect: cur_size < prev_size → baştan oku.

    Returns: (doc_token_sets, file_state_new, n_files_processed, n_lines_new)
    """
    doc_token_sets = []
    file_state_new = dict(prev_file_state) if prev_file_state else {}
    n_files = 0
    n_lines = 0
    seen_paths = set()

    for fpath in _walk_files(paths, max_files):
        seen_paths.add(fpath)
        prev = (prev_file_state or {}).get(fpath)
        try:
            cur_size = os.path.getsize(fpath)
            cur_mtime = os.path.getmtime(fpath)
        except OSError:
            continue

        # Karar: tail-only mu, full-rescan mı?
        offset = 0
        if prev is not None:
            if cur_size < prev["size"]:
                # truncate/rotate → baştan oku
                offset = 0
            elif cur_size == prev["size"] and cur_mtime <= prev["mtime"]:
                # Değişmedi — atla
                continue
            else:
                # Tail: prev offset'ten itibaren
                offset = prev["offset"]

        lines, new_offset = _read_file_from_offset(fpath, offset=offset)
        if lines is None or new_offset is None:
            # Skip etmiş ama state'i güncelle
            entry = _file_state_entry(fpath, cur_size, cur_mtime, cur_size)
            if entry:
                file_state_new[fpath] = entry
            continue

        for line in lines:
            toks = _tokenize(line)
            if not toks:
                continue
            doc_token_sets.append(set(toks))
            n_lines += 1
        file_state_new[fpath] = _file_state_entry(fpath, new_offset, cur_mtime, cur_size)
        n_files += 1
        if verbose and n_files % 100 == 0:
            print(f"[krep --learn]   ...scanned {n_files} files, "
                  f"{n_lines} new lines", file=sys.stderr)

    # Silinmiş dosyaları file_state'ten çıkar (prev'de var ama walk'ta yok)
    if prev_file_state:
        for old_path in list(file_state_new.keys()):
            if old_path not in seen_paths and not os.path.exists(old_path):
                file_state_new.pop(old_path, None)

    return doc_token_sets, file_state_new, n_files, n_lines


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


def _accumulate_cooc(doc_token_sets, prev_term_freq=None, prev_cooc=None):
    """Belge token-setlerinden term_freq + cooccurrence pair counter üret.

    prev_* varsa ona ek olarak biriktirir (incremental).

    Returns: (term_freq Counter, cooc defaultdict[pair] = count)
    """
    term_freq = Counter(prev_term_freq) if prev_term_freq else Counter()
    cooc = defaultdict(int)
    if prev_cooc:
        cooc.update(prev_cooc)

    for toks in doc_token_sets:
        term_freq.update(toks)
    # Cooccurrence: vocab finalize öncesi kelime stringlerini saymak yerine
    # vocab finalize sonrası index'leme yapacağız. Burada kelime çiftlerini
    # geçici string-key olarak biriktirip _compute_svd'de map'leyeceğiz.
    # Bellek için: doc_token_sets döngüsü bir kez, vocab post-cutting.
    # Bu fonksiyon yalnızca term_freq döndürür; cooc string-key dict olarak
    # bir sonraki fonksiyonda hesaplanır (vocab cut bilinmeden cooc yazmak
    # bellekte gereksiz büyük).
    return term_freq, doc_token_sets  # cooc parserı _compute_svd'de


def _compute_svd_from_docs(doc_token_sets, term_freq, prev_cooc_pairs=None,
                            verbose=False):
    """Token set listesinden vocab + PPMI + SVD ile model üret.

    prev_cooc_pairs: önceki run'dan {(word_a, word_b): count} (string-keyed).
    Yeni doc'lardan ek pair sayımları topraklanır.

    Returns: dict(vocab, vocab_idx, word_vecs, axis_labels, n_terms, n_pairs)
    """
    # --- Vocab budama ---
    vocab_list = [w for w, c in term_freq.most_common(_MAX_VOCAB)
                  if c >= _MIN_TERM_FREQ]
    if len(vocab_list) < _RANK + 1:
        raise RuntimeError(
            f"Çok az unique terim ({len(vocab_list)}); en az {_RANK+1} gerekli."
        )
    vocab_idx = {w: i for i, w in enumerate(vocab_list)}
    V = len(vocab_list)
    if verbose:
        print(f"[krep --learn] Vocab: {V} terms", file=sys.stderr)

    # --- Cooccurrence: previous string-pair sayımları + new doc_token_sets ---
    t1 = time.perf_counter()
    pair_counts = defaultdict(int)
    if prev_cooc_pairs:
        for (a, b), c in prev_cooc_pairs.items():
            if a in vocab_idx and b in vocab_idx and a != b:
                key = (a, b) if a < b else (b, a)
                pair_counts[key] += c

    for toks in doc_token_sets:
        valid = sorted({w for w in toks if w in vocab_idx})
        for i, wa in enumerate(valid):
            for wb in valid[i+1:]:
                pair_counts[(wa, wb)] += 1

    if not pair_counts:
        raise RuntimeError("Cooccurrence empty.")

    # Sparse symmetric matrix
    rows, cols, data = [], [], []
    for (wa, wb), c in pair_counts.items():
        ia, ib = vocab_idx[wa], vocab_idx[wb]
        rows.extend([ia, ib]); cols.extend([ib, ia]); data.extend([c, c])
    C = csr_matrix((data, (rows, cols)), shape=(V, V), dtype=np.float64)
    if verbose:
        print(f"[krep --learn] Cooccurrence: {len(pair_counts)} pairs, "
              f"{time.perf_counter()-t1:.1f}s", file=sys.stderr)

    # --- PPMI ---
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

    # --- SVD rank-3 ---
    t3 = time.perf_counter()
    k = _RANK
    if V <= k:
        raise RuntimeError(f"Vocab too small for rank-{k} SVD (V={V}).")
    U, sigma, _ = svds(P, k=k)
    order = np.argsort(-sigma)
    sigma = sigma[order]
    U = U[:, order]
    word_vecs = (U * np.sqrt(sigma)).astype(np.float32)
    if verbose:
        print(f"[krep --learn] SVD rank-{k}: σ={sigma.round(2).tolist()}, "
              f"{time.perf_counter()-t3:.1f}s", file=sys.stderr)

    # --- Auto-label ---
    freq_arr = np.array([term_freq[vocab_list[i]] for i in range(V)],
                         dtype=np.float32)
    log_freq = np.log1p(freq_arr)
    axis_labels = []
    for ax in range(k):
        pos_score = np.maximum(word_vecs[:, ax], 0.0) * log_freq
        min_freq_mask = freq_arr >= 5
        scores = np.where(min_freq_mask, pos_score, -np.inf)
        top_idx = np.argsort(-scores)[:_AXIS_TOP_N]
        top_idx = [i for i in top_idx if scores[i] > -np.inf]
        label = " ".join(vocab_list[i] for i in top_idx) if top_idx else "(none)"
        axis_labels.append(label)

    return {
        "vocab": vocab_list,
        "vocab_idx": vocab_idx,
        "word_vecs": word_vecs,
        "axis_labels": axis_labels,
        "n_terms": V,
        "pair_counts": dict(pair_counts),  # state for incremental update
    }


def build_model(source_paths, max_files=None, verbose=True,
                auto_refresh_seconds=0):
    """PPMI + SVD ile corpus'tan 3D word embedding üret (full scan)."""
    if not LEARN_AVAILABLE:
        raise RuntimeError(
            "krep --learn için numpy ve scipy gerekli. "
            "Kurulum: pip install numpy scipy"
        )

    if verbose:
        print(f"[krep --learn] Scanning {len(source_paths)} path(s)...",
              file=sys.stderr)
    t0 = time.perf_counter()

    doc_token_sets, file_state, n_files, n_lines = _scan_corpus(
        source_paths, prev_file_state=None, max_files=max_files, verbose=verbose
    )
    if n_lines == 0:
        raise RuntimeError(f"Corpus boş: {source_paths}")

    term_freq, _ = _accumulate_cooc(doc_token_sets)
    svd_result = _compute_svd_from_docs(doc_token_sets, term_freq, verbose=verbose)
    elapsed = time.perf_counter() - t0

    if verbose:
        for i, lab in enumerate(svd_result["axis_labels"]):
            print(f"[krep --learn] Axis {i}: {lab}", file=sys.stderr)
        print(f"[krep --learn] Done in {elapsed:.1f}s "
              f"(V={svd_result['n_terms']}, lines={n_lines})", file=sys.stderr)

    return {
        "vocab": svd_result["vocab"],
        "vocab_idx": svd_result["vocab_idx"],
        "word_vecs": svd_result["word_vecs"],
        "axis_labels": svd_result["axis_labels"],
        "build_time": time.time(),
        "source_paths": [os.path.abspath(p) for p in source_paths],
        "n_lines": n_lines,
        "n_terms": svd_result["n_terms"],
        "elapsed_s": elapsed,
        # Incremental state
        "file_state": file_state,
        "term_freq": dict(term_freq),
        "pair_counts": svd_result["pair_counts"],
        "auto_refresh_seconds": int(auto_refresh_seconds),
    }


def update_model(existing_model, source_paths=None, max_files=None, verbose=True):
    """Mevcut modeli tail-aware incremental olarak güncelle.

    Sadece DEĞİŞMİŞ dosyaları okur (mtime/size karşılaştır), tail offset'ten
    itibaren yeni satırları işler. Truncate/rotate detect edilirse o dosya
    baştan okunur. Silinmiş dosyalar state'ten çıkar.

    source_paths None ise existing_model'in source_paths'i kullanılır.
    """
    if not LEARN_AVAILABLE:
        raise RuntimeError("update_model için numpy/scipy gerekli.")
    paths = source_paths or existing_model["source_paths"]
    if verbose:
        print(f"[krep --update-learn] Tail scan {len(paths)} path(s)...",
              file=sys.stderr)
    t0 = time.perf_counter()
    prev_state = existing_model.get("file_state") or {}
    new_doc_token_sets, file_state_new, n_files, n_lines_new = _scan_corpus(
        paths, prev_file_state=prev_state, max_files=max_files, verbose=verbose
    )

    if verbose:
        print(f"[krep --update-learn] {n_files} files updated, "
              f"{n_lines_new} new lines, {time.perf_counter()-t0:.1f}s",
              file=sys.stderr)

    if n_lines_new == 0 and prev_state:
        if verbose:
            print(f"[krep --update-learn] No changes detected — "
                  f"model unchanged.", file=sys.stderr)
        # Sadece build_time'ı güncelle (yeni model dosyası yazılırken refresh
        # tetiklemesin diye)
        existing_model = dict(existing_model)
        existing_model["build_time"] = time.time()
        existing_model["elapsed_s"] = time.perf_counter() - t0
        return existing_model

    # Term freq + pair counts ek (previous'a topla)
    prev_term_freq = existing_model.get("term_freq") or {}
    prev_pair_counts = existing_model.get("pair_counts") or {}
    term_freq, _ = _accumulate_cooc(new_doc_token_sets,
                                      prev_term_freq=prev_term_freq)
    svd_result = _compute_svd_from_docs(
        new_doc_token_sets, term_freq,
        prev_cooc_pairs=prev_pair_counts, verbose=verbose
    )

    elapsed = time.perf_counter() - t0
    if verbose:
        for i, lab in enumerate(svd_result["axis_labels"]):
            print(f"[krep --update-learn] Axis {i}: {lab}", file=sys.stderr)
        print(f"[krep --update-learn] Done in {elapsed:.1f}s "
              f"(V={svd_result['n_terms']}, +{n_lines_new} lines)", file=sys.stderr)

    n_lines_total = existing_model.get("n_lines", 0) + n_lines_new
    return {
        "vocab": svd_result["vocab"],
        "vocab_idx": svd_result["vocab_idx"],
        "word_vecs": svd_result["word_vecs"],
        "axis_labels": svd_result["axis_labels"],
        "build_time": time.time(),
        "source_paths": existing_model["source_paths"],
        "n_lines": n_lines_total,
        "n_terms": svd_result["n_terms"],
        "elapsed_s": elapsed,
        "file_state": file_state_new,
        "term_freq": dict(term_freq),
        "pair_counts": svd_result["pair_counts"],
        "auto_refresh_seconds": existing_model.get("auto_refresh_seconds", 0),
    }


def save_model(model, dir_path=None):
    """Modeli kaydet: vectors.npz (numerik) + metadata.json (text) +
    state.json (incremental state: file_state, term_freq, pair_counts)."""
    if dir_path is None:
        dir_path = model_dir_for(model["source_paths"])
    os.makedirs(dir_path, exist_ok=True)
    # Numerik: word_vecs
    np.savez_compressed(
        os.path.join(dir_path, "vectors.npz"),
        word_vecs=model["word_vecs"],
    )
    # Metadata (kullanıcıya görünür, hızlı load)
    meta = {
        "vocab": model["vocab"],
        "axis_labels": model["axis_labels"],
        "build_time": model["build_time"],
        "source_paths": model["source_paths"],
        "n_lines": model["n_lines"],
        "n_terms": model["n_terms"],
        "auto_refresh_seconds": int(model.get("auto_refresh_seconds", 0)),
        "format_version": 2,
    }
    with open(os.path.join(dir_path, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)

    # Incremental state — sadece update için lazım, lazy load
    if "file_state" in model or "term_freq" in model or "pair_counts" in model:
        state = {
            "file_state": model.get("file_state", {}),
            "term_freq": model.get("term_freq", {}),
            # pair_counts dict tuple-keyed → JSON için string-key ile flatten
            "pair_counts": [
                {"a": a, "b": b, "c": c}
                for (a, b), c in (model.get("pair_counts") or {}).items()
            ],
        }
        with open(os.path.join(dir_path, "state.json"), "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    return dir_path


def load_model(dir_path, with_state=False):
    """Modeli yükle. with_state=True ise incremental state'i de yükle.

    Default (with_state=False): sadece vocab + word_vecs + meta (sorgu için).
    Update gerekiyorsa with_state=True (file_state + term_freq + pair_counts).
    """
    if not LEARN_AVAILABLE:
        return None
    if not os.path.isdir(dir_path):
        return None
    npz_path = os.path.join(dir_path, "vectors.npz")
    json_path = os.path.join(dir_path, "metadata.json")
    if not (os.path.isfile(npz_path) and os.path.isfile(json_path)):
        return None
    try:
        with np.load(npz_path) as data:
            word_vecs = data["word_vecs"]
        with open(json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        vocab = meta["vocab"]
        model = {
            "vocab": vocab,
            "vocab_idx": {w: i for i, w in enumerate(vocab)},
            "word_vecs": word_vecs,
            "axis_labels": meta["axis_labels"],
            "build_time": float(meta["build_time"]),
            "source_paths": meta["source_paths"],
            "n_lines": int(meta["n_lines"]),
            "n_terms": int(meta["n_terms"]),
            "auto_refresh_seconds": int(meta.get("auto_refresh_seconds", 0)),
        }
        if with_state:
            state_path = os.path.join(dir_path, "state.json")
            if os.path.isfile(state_path):
                with open(state_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
                model["file_state"] = state.get("file_state") or {}
                model["term_freq"] = state.get("term_freq") or {}
                # pair_counts reconstruct tuple-keyed
                pc_list = state.get("pair_counts") or []
                model["pair_counts"] = {
                    (item["a"], item["b"]): int(item["c"])
                    for item in pc_list
                }
            else:
                model["file_state"] = {}
                model["term_freq"] = {}
                model["pair_counts"] = {}
        return model
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None


def find_model_for(paths, with_state=False):
    """Verilen paths için kayıtlı model varsa yükle.

    with_state=True: incremental update için file_state/term_freq/pair_counts da.
    """
    if not LEARN_AVAILABLE or not paths:
        return None
    return load_model(model_dir_for(paths), with_state=with_state)


def model_age_seconds(model):
    """Model build_time'dan şu ana kadar geçen saniye sayısı."""
    return time.time() - float(model.get("build_time", 0))


def is_stale(model):
    """auto_refresh_seconds > 0 ve model_age > auto_refresh ise True."""
    interval = int(model.get("auto_refresh_seconds", 0))
    if interval <= 0:
        return False
    return model_age_seconds(model) > interval


def parse_interval(s):
    """İnsancıl interval string'ini saniyeye çevir.

    Örnek: '1h' → 3600, '30m' → 1800, '1d' → 86400, '45s' → 45.
    Plain integer (saniye varsayılır). Hata durumunda ValueError.
    """
    if s is None:
        return 0
    s = str(s).strip().lower()
    if s in ("0", "off", "false", "no", "disable", "disabled"):
        return 0
    # Plain number → seconds
    if s.isdigit():
        return int(s)
    # Suffix: s/m/h/d
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    if len(s) >= 2 and s[-1] in units and s[:-1].replace(".", "").isdigit():
        return int(float(s[:-1]) * units[s[-1]])
    raise ValueError(f"invalid interval: {s!r} (e.g. '1h', '30m', '1d')")


def format_age(seconds):
    """İnsancıl yaş formatı: 45s, 12m, 3h, 2d."""
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    if s < 86400:
        return f"{s // 3600}h"
    return f"{s // 86400}d"


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
            "auto_refresh_seconds": int(m.get("auto_refresh_seconds", 0)),
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
