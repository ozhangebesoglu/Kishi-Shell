import re
import math
import os
import sys
import shutil
import subprocess
import time as _time

# Cython C-Engine Entegrasyon Kontrolü
try:
    from kishi.krep_core import vectorize_text_c, cosine_similarity_c
    CYTHON_AVAILABLE = True
except ImportError:
    CYTHON_AVAILABLE = False

# Local Semantic Model (PPMI + SVD) — LAZY IMPORT
# numpy/scipy ~1.2 sn yüklüyor; her krep çağrısında bunu ödememeliyiz.
# krep_learn ve numpy/scipy SADECE --learn/--update-learn/model lookup
# zamanında import edilir. Saf keyword arama numpy'siz çalışır.
LEARN_AVAILABLE = None  # tri-state: None=henüz kontrol edilmedi, True/False=tespit edildi
krep_learn = None


def _try_import_krep_learn():
    """Lazy import. İlk çağrıda numpy/scipy yüklemeyi tetikler.
    Yüklü değilse LEARN_AVAILABLE=False olarak işaretlenir, tekrar denenmez."""
    global LEARN_AVAILABLE, krep_learn
    if LEARN_AVAILABLE is not None:
        return LEARN_AVAILABLE
    try:
        from kishi import krep_learn as _kl
        krep_learn = _kl
        LEARN_AVAILABLE = bool(_kl.LEARN_AVAILABLE)
    except ImportError:
        LEARN_AVAILABLE = False
        krep_learn = None
    return LEARN_AVAILABLE


# Yüklenmiş modeli paths bazında cache (REPL ömrü)
_MODEL_CACHE = {}

# === ripgrep tabanlı streaming prefilter (opsiyonel sistem ikilisi) ===
import shutil as _shutil
import subprocess
import time as _time
_HAS_RG = _shutil.which("rg") is not None


def _build_rg_pattern(query):
    """Sorgu metninden ripgrep regex pattern'i üret.

    - En az 3 karakter uzunluğundaki kelimeler alınır (kısa kelimeler
      false positive üretir, "a", "to", "if" gibi).
    - Her kelime re.escape ile geçirilir; meta-karakterler güvenli.
    """
    words = re.findall(r'[\w]+', query)
    long_words = [w for w in words if len(w) >= 3]
    if not long_words:
        return None
    return "|".join(re.escape(w) for w in long_words)


def _krep_rg_streaming(query_str, q_vec, paths, limit=5,
                       max_per_file=20, early_stop_factor=10,
                       hard_timeout=10.0, model=None):
    """ripgrep tabanlı streaming prefilter + vektörleştirme.

    model verilirse satır vektörleştirme krep_learn HD vec ile yapılır;
    aksi halde mevcut keyword vectorize_text fallback.
    Returns: (matches, stats). matches tuple: (l_vec, sim, output_str, raw_text)
    """
    pattern = _build_rg_pattern(query_str)
    if pattern is None:
        return [], {"reason": "no_pattern", "elapsed_ms": 0.0,
                    "lines_read": 0, "lines_vectorized": 0,
                    "matches_found": 0, "early_stopped": False}

    cmd = ["rg", "-i", "--no-heading", "-n",
           f"--max-count={max_per_file}",
           pattern] + list(paths)

    t_start = _time.perf_counter()
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
    except (OSError, FileNotFoundError):
        return [], {"reason": "rg_spawn_failed", "elapsed_ms": 0.0,
                    "lines_read": 0, "lines_vectorized": 0,
                    "matches_found": 0, "early_stopped": False}

    matches = []
    lines_read = 0
    lines_vectorized = 0
    early_stopped = False
    target = max(limit * early_stop_factor, limit)

    try:
        for raw in proc.stdout:
            lines_read += 1
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            fpath, lineno_str, text = parts
            text = text.strip()
            if not text:
                continue
            # Model varsa HD vec, yoksa keyword
            l_vec = _vectorize_dispatch(text, model)
            lines_vectorized += 1
            if not any(l_vec):
                continue
            sim = _cosine_anyd(q_vec, l_vec)
            if sim < 0.3:
                continue
            output_str = (
                f"{COLOR_CYAN}{fpath}{COLOR_RESET}:"
                f"{COLOR_GREEN}{lineno_str}{COLOR_RESET}: {text}"
            )
            matches.append((l_vec, sim, output_str, text))
            if len(matches) >= target:
                early_stopped = True
                break
            if (_time.perf_counter() - t_start) > hard_timeout:
                early_stopped = True
                break
    finally:
        try:
            if proc.stdout is not None:
                proc.stdout.close()
        except OSError:
            pass
        if early_stopped:
            proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass

    elapsed_ms = (_time.perf_counter() - t_start) * 1000.0
    return matches, {
        "elapsed_ms": elapsed_ms,
        "lines_read": lines_read,
        "lines_vectorized": lines_vectorized,
        "matches_found": len(matches),
        "early_stopped": early_stopped,
    }

# Kavramsal ANSI Renk Kodları
COLOR_RESET = "\033[0m"
COLOR_AMBER = "\033[38;2;255;191;0m"
COLOR_RED = "\033[1;31m"
COLOR_GREEN = "\033[1;32m"
COLOR_CYAN = "\033[1;36m"
COLOR_PURPLE = "\033[1;35m"

# Kelime haznesi bazlı 3D kavramsal eşlemeler (X=Hata, Y=Güvenlik, Z=Veri)
X_KEYWORDS = ['error', 'fail', 'crash', 'bug', 'warning', 'exception', 'fatal', 
              'timeout', 'kill', 'stop', 'exit', 'quit', 'terminate', 
              'disconnect', 'break', 'close', 'abort',
              'hata', 'ariza', 'cokme', 'bozuk', 'kusur', 'problem', 'sorun', 'engel', 'limit', 'uyari', 'istisna']

Y_KEYWORDS = ['auth', 'login', 'password', 'key', 'token', 'user', 'admin', 
              'secure', 'crypto', 'cert', 'ssh', 'encrypt', 'decrypt', 
              'privilege', 'allow', 'denied', 'permission', 'sign',
              'guvenlik', 'giris', 'sifre', 'anahtar', 'kullanici', 'yetki', 'izin', 'yasak', 'kripto', 'sertifika']

Z_KEYWORDS = ['database', 'sql', 'db', 'file', 'save', 'write', 'read', 'query', 
              'list', 'select', 'update', 'insert', 'delete', 'table', 
              'column', 'row', 'csv', 'json', 'xml', 'storage', 'log',
              'veri', 'dosya', 'veritabani', 'kayit', 'yaz', 'oku', 'sorgu', 'liste', 'tablo', 'sutun', 'satir', 'depo', 'gunluk', 'bellek']

# Bigram setlerini önbellekleme
def _to_bigrams(w):
    return {w[i:i+2] for i in range(len(w) - 1)} if len(w) >= 2 else {w}

X_BIGRAMS = [_to_bigrams(k) for k in X_KEYWORDS]
Y_BIGRAMS = [_to_bigrams(k) for k in Y_KEYWORDS]
Z_BIGRAMS = [_to_bigrams(k) for k in Z_KEYWORDS]

# Küresel Semantik Konsept Önbelleği (Dosya yolları -> (mtime, concept_vector))
CONCEPT_CACHE = {}

def get_file_concept_vector(file_path):
    """Dosyanın tüm kelimelerinin semantik toplamını mtime kontrolü ile hesaplar."""
    try:
        mtime = os.path.getmtime(file_path)
    except OSError:
        return None
        
    if file_path in CONCEPT_CACHE:
        cached_mtime, vec = CONCEPT_CACHE[file_path]
        if cached_mtime == mtime:
            return vec
            
    # Dosya konsept vektörünü oluştur
    vec = [0.0, 0.0, 0.0]
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            words = set(re.findall(r'[A-Za-z0-9_]+', content))
            for w in words:
                v = get_semantic_vector(w)
                if any(v):
                    vec[0] += v[0]
                    vec[1] += v[1]
                    vec[2] += v[2]
        CONCEPT_CACHE[file_path] = (mtime, vec)
        return vec
    except OSError:
        return None

def get_semantic_vector(word):
    word = word.lower().strip()
    if not word:
        return [0.0, 0.0, 0.0]
    
    # 1. Tam veya önek eşleşmesi (Doğrudan eşleşen anahtar kelimeler için maksimum hız ve doğruluk)
    if any(word.startswith(k) for k in X_KEYWORDS):
        return [1.0, 0.0, 0.0]
    if any(word.startswith(k) for k in Y_KEYWORDS):
        return [0.0, 1.0, 0.0]
    if any(word.startswith(k) for k in Z_KEYWORDS):
        return [0.0, 0.0, 1.0]
        
    # 2. Yumuşak Harf Karakter Overlap (2-Gram Jaccard Benzerliği) fall-back
    wb = _to_bigrams(word)
    
    x_score = 0.0
    for xb in X_BIGRAMS:
        intersection = len(wb & xb)
        union = len(wb) + len(xb) - intersection
        sim = intersection / union if union > 0 else 0.0
        if sim > x_score:
            x_score = sim
            
    y_score = 0.0
    for yb in Y_BIGRAMS:
        intersection = len(wb & yb)
        union = len(wb) + len(yb) - intersection
        sim = intersection / union if union > 0 else 0.0
        if sim > y_score:
            y_score = sim
            
    z_score = 0.0
    for zb in Z_BIGRAMS:
        intersection = len(wb & zb)
        union = len(wb) + len(zb) - intersection
        sim = intersection / union if union > 0 else 0.0
        if sim > z_score:
            z_score = sim
            
    # Küçük gürültüleri filtrelemek için alt eşik (n-gram gürültüsünü önlemek için 0.4)
    if x_score < 0.4: x_score = 0.0
    if y_score < 0.4: y_score = 0.0
    if z_score < 0.4: z_score = 0.0
    
    return [x_score, y_score, z_score]

def vectorize_text(text):
    """Verilen metindeki tüm kelimeleri ayıklar, 3D vektörlerini toplar ve normalize eder."""
    if CYTHON_AVAILABLE:
        return vectorize_text_c(text)
        
    words = re.findall(r'[A-Za-z0-9_]+', text)
    if not words:
        return [0.0, 0.0, 0.0]
        
    vec = [0.0, 0.0, 0.0]
    matched_count = 0
    for w in words:
        v = get_semantic_vector(w)
        if any(v):
            vec[0] += v[0]
            vec[1] += v[1]
            vec[2] += v[2]
            matched_count += 1
            
    if matched_count == 0:
        return [0.0, 0.0, 0.0]
        
    length = math.sqrt(vec[0]**2 + vec[1]**2 + vec[2]**2)
    if length > 0:
        return [vec[0] / length, vec[1] / length, vec[2] / length]
    return [0.0, 0.0, 0.0]

def cosine_similarity(v1, v2):
    """İki normalize edilmiş 3D vektör arasındaki kosinüs benzerliğini hesaplar."""
    if CYTHON_AVAILABLE:
        return cosine_similarity_c(v1, v2)
        
    if not any(v1) or not any(v2):
        return 0.0
    return v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2]

def render_3d_scatter(query_vec, matches):
    """
    Sorgu vektörünü ve en iyi eşleşen satırların vektörlerini
    3 boyutlu bir koordinat düzlemine izdüşürerek terminalde ASCII olarak çizer.
    """
    # Grid boyutları
    width = 50
    height = 18
    grid = [[" " for _ in range(width)] for _ in range(height)]
    
    # Koordinat merkezimiz (Origin)
    cx = 18
    cy = 9
    
    # 1. Z Ekseni (Veri / Depolama) - Dikey eksen yukarı
    for r in range(1, 8):
        if cy - r >= 0:
            grid[cy - r][cx] = "│"
    grid[cy - 8][cx] = "▲"
    from kishi.krep_i18n import t as _t
    grid[cy - 8][cx + 2] = _t("axis_z")
    
    # 2. Y Ekseni (Güvenlik / Erişim) - Yatay eksen sağa
    for c in range(1, 26):
        if cx + c < width:
            grid[cy][cx + c] = "─"
    grid[cy][cx + 26] = "▶"
    grid[cy - 1][cx + 23] = _t("axis_y")
    
    # 3. X Ekseni (Stabilite / Hata) - Çapraz eksen sol-aşağı
    for d in range(1, 7):
        if cy + d < height and cx - d * 2 >= 0:
            grid[cy + d][cx - d * 2] = "╲"
            grid[cy + d][cx - d * 2 + 1] = "╲"
    if cy + 7 < height and cx - 14 >= 0:
        grid[cy + 7][cx - 14] = "▼"
    if cy + 7 < height and cx - 13 >= 0:
        grid[cy + 7][cx - 12] = _t("axis_x")
        
    # Origin göstergesi
    grid[cy][cx] = "┼"
    
    def project_3d_to_2d(vec):
        """3D vektör koordinatlarını [0,1] aralığından 2D grid piksel koordinatına taşır."""
        x, y, z = vec
        # X çapraz sol-aşağı, Y yatay sağa, Z dikey yukarı
        col_offset = int((y * 22) - (x * 12))
        row_offset = int(-(z * 7) + (x * 4))
        
        px = cx + col_offset
        py = cy + row_offset
        return px, py
        
    # En iyi eşleşenleri çiz
    # Çizimde çakışmaları önlemek için sorguyu en son çizeceğiz.
    for idx, (v_match, similarity, _) in enumerate(matches, 1):
        if not any(v_match):
            continue
        px, py = project_3d_to_2d(v_match)
        if 0 <= px < width and 0 <= py < height:
            grid[py][px] = f"{idx}"
            
    # Sorgu vektörünü çiz (Sarı renkli yıldız)
    if any(query_vec):
        qx, qy = project_3d_to_2d(query_vec)
        if 0 <= qx < width and 0 <= qy < height:
            grid[qy][qx] = f"{COLOR_AMBER}*{COLOR_RESET}"

    # Ekrana bas
    out = []
    out.append("\n" + "=" * 55)
    out.append(f"            {COLOR_AMBER}{_t('scatter_title')}{COLOR_RESET}")
    out.append("=" * 55)
    for row in grid:
        out.append("".join(row))
    out.append("=" * 55 + "\n")
    return "\n".join(out)


def _resolve_model(files_or_dirs):
    """Verilen paths için kayıtlı LSA modeli varsa yükle (cache'le).

    Cache key: (paths, model_file_mtime). Dosya değiştiyse (örn. background
    refresh tamamlandı) cache invalid → reload.

    Lazy refresh: stale ise background subprocess tetiklenir, bu sorgu eski
    modelle devam, sıradaki sorgu yeni modeli görür.
    """
    if not files_or_dirs:
        return None
    real_paths = [p for p in files_or_dirs if p != "-" and os.path.exists(p)]
    if not real_paths:
        return None

    # OPTIMIZATION: Önce model dosyasının disk'te var olup olmadığını kontrol
    # et — numpy/scipy YÜKLEMEDEN. Model yoksa hızlıca None dön; saf keyword
    # arama numpy'siz devam etsin. (~1.2 sn startup kazancı.)
    paths_key = tuple(sorted(os.path.abspath(p) for p in real_paths))
    _model_dir = _quick_model_dir_for(real_paths)
    if _model_dir is None:
        return None
    meta_path = os.path.join(_model_dir, "metadata.json")
    if not os.path.isfile(meta_path):
        return None  # Model yok → numpy gerekmez

    # Model dosyası var → şimdi numpy/scipy yüklemeyi göze al
    if not _try_import_krep_learn():
        return None

    try:
        model_mtime = os.path.getmtime(meta_path)
    except OSError:
        model_mtime = 0.0
    cache_key = (paths_key, model_mtime)
    if cache_key in _MODEL_CACHE:
        m = _MODEL_CACHE[cache_key]
    else:
        m = krep_learn.find_model_for(list(real_paths))
        _MODEL_CACHE[cache_key] = m
    # Her resolve'da stale check — cache hit olsa bile background refresh
    if m is not None and krep_learn.is_stale(m):
        _trigger_background_refresh(real_paths)
    return m


def _quick_model_dir_for(paths):
    """krep_learn.model_dir_for'un numpy'siz versiyonu (hash hesaplaması için
    sadece hashlib + os gerekiyor, krep_learn import etmiyor).

    Bu sayede model dosyası disk'te yoksa numpy'yi hiç yüklemeyiz.
    """
    import hashlib
    import re as _re
    xdg = os.environ.get("XDG_CACHE_HOME") or os.path.join(
        os.environ.get("HOME", "/"), ".cache"
    )
    cache_dir = os.path.join(xdg, "kishi", "krep_models")
    canon = "|".join(sorted(os.path.abspath(p) for p in paths))
    h = hashlib.blake2b(canon.encode("utf-8"), digest_size=6).hexdigest()
    primary = os.path.basename(os.path.abspath(paths[0])) or "root"
    safe = _re.sub(r"[^A-Za-z0-9_-]", "_", primary)[:40]
    return os.path.join(cache_dir, f"{safe}_{h}")


# Bir sorguda en fazla bir kez tetikle (concurrent spawn'u engelle)
_REFRESH_TRIGGERED = set()


def _trigger_background_refresh(paths):
    """Detached subprocess ile model refresh tetikle. Kullanıcı sorgusunu
    bekletmez; sonraki sorgu yeni modeli görür."""
    import subprocess
    key = tuple(sorted(os.path.abspath(p) for p in paths))
    if key in _REFRESH_TRIGGERED:
        return  # bu paths için zaten tetiklendi
    _REFRESH_TRIGGERED.add(key)
    # repr() ile escape — shell injection riski yok (shell=False)
    paths_repr = ", ".join(repr(p) for p in paths)
    code = (
        "import sys; "
        f"sys.path.insert(0, {repr(os.path.dirname(os.path.dirname(__file__)))}); "
        "from kishi import krep_learn as kl; "
        f"m = kl.find_model_for([{paths_repr}], with_state=True); "
        "m2 = kl.update_model(m, verbose=False) if m else None; "
        "kl.save_model(m2) if m2 else None"
    )
    try:
        subprocess.Popen(
            [sys.executable, "-c", code],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,  # parent ölse bile devam etsin
        )
    except OSError:
        pass


def _vectorize_dispatch(text, model):
    """text → vektör. Model varsa HD vec (50D), yoksa keyword 3D."""
    if model is not None:
        v, _ = krep_learn.vectorize_with_model(text, model, dim="hd")
        return v  # numpy array; cosine_similarity boyut agnostik çalışır
    return vectorize_text(text)


def _vectorize_3d(text, model):
    """3D scatter için — keyword 3D ya da model'in PCA-3 vec'i."""
    if model is not None:
        v, _ = krep_learn.vectorize_with_model(text, model, dim="3d")
        return [float(v[0]), float(v[1]), float(v[2])]
    return vectorize_text(text)


def _cosine_anyd(a, b):
    """Boyut-agnostik cosine. List veya ndarray kabul eder.

    Vec'ler vectorize_with_model'da zaten L2-normalize edildiği için
    sadece dot product yeter; ama defansif olarak normalize edelim.
    """
    if not any(a) or not any(b):
        return 0.0
    if hasattr(a, "dot") and hasattr(b, "dot"):
        # numpy hızlı yol
        na = float((a * a).sum()) ** 0.5
        nb = float((b * b).sum()) ** 0.5
        if na == 0 or nb == 0:
            return 0.0
        return float((a * b).sum()) / (na * nb)
    # Liste fallback
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _term_width(default=80):
    """Terminal genişliği (stdout TTY değilse default)."""
    try:
        import shutil as _sh
        return max(40, _sh.get_terminal_size((default, 20)).columns)
    except Exception:
        return default


def _color_score(sim):
    """Skoru renge eşle: yeşil (>=0.8), sarı (>=0.5), kırmızı (<0.5)."""
    if sim >= 0.8:
        return COLOR_GREEN
    if sim >= 0.5:
        return "\033[1;33m"  # yellow
    return COLOR_RED


def _shorten_path(path, max_len):
    """Path'i max_len'e kıs. Sadece basename'i tut, çok uzunsa kes."""
    if len(path) <= max_len:
        return path
    base = os.path.basename(path) or path
    if len(base) <= max_len:
        return base
    return "…" + base[-(max_len - 1):]


def _krep_finalize(matches, q_vec, limit, model=None,
                   query_str="", elapsed_ms=0.0, scatter=False,
                   per_line_timings=None):
    """Sade çıktı: header (top-right ms), sonuçlar (per-line ms), opt-in scatter.

    Args:
        matches: List of (l_vec, sim, output_str) or (..., raw_text).
        q_vec: query vector.
        limit: top-K.
        model: LSA model or None.
        query_str: original user query (for header display).
        elapsed_ms: total search time in ms (shown top-right).
        scatter: if True, also render 3D ASCII scatter at bottom.
        per_line_timings: optional list of ms per match (right-aligned).
    """
    from kishi.krep_i18n import t

    width = _term_width()

    # ── HEADER ─────────────────────────────────────────────────────────
    if model is not None:
        model_info = t("model_lsa",
                       n_terms=model.get("n_terms", 0),
                       n_lines=model.get("n_lines", 0))
    else:
        model_info = t("model_keyword")

    if not matches:
        header_key = "no_results_header"
        n_matches = 0
    else:
        header_key = "results_header"
        n_matches = min(len(matches), limit)

    # Sağa hizalanmış ms — header sonu ile ms arası padding
    base = t(header_key, n=n_matches, q=query_str,
             model_info=model_info).rstrip()
    ms_str = f"{int(elapsed_ms)} ms"
    # ANSI'den arınmış uzunluk ölç (renk kodları sayılmasın)
    import re as _re
    plain_len = len(_re.sub(r"\x1b\[[0-9;]*m", "", base))
    pad = max(2, width - plain_len - len(ms_str))
    header = f"{base}{' ' * pad}{COLOR_CYAN}{ms_str}{COLOR_RESET}"
    print(header)
    print("─" * width)

    if not matches:
        return 1

    # ── RESULTS ────────────────────────────────────────────────────────
    matches.sort(key=lambda x: x[1], reverse=True)
    top_matches = matches[:limit]

    # output_str içinde ANSI ve format zaten var — burada da kendi sade
    # formatımızı yapıyoruz çünkü "0.41 path:line text [SPACE] Xms" istiyoruz.
    # output_str'den path:line:text çıkarmak için regex.
    line_re = _re.compile(r"\x1b\[[0-9;]*m([^\x1b]+?)\x1b\[0m:\x1b\[[0-9;]*m(\d+)\x1b\[0m:\s*(.*)$")

    for idx, item in enumerate(top_matches):
        sim = item[1]
        output_str = item[2]
        # path:line:text parse
        m = line_re.search(output_str)
        if m:
            path, lineno, text = m.group(1), m.group(2), m.group(3)
        else:
            # Fallback: tüm string
            path, lineno, text = "?", "?", output_str
        # text içindeki ANSI strip
        text = _re.sub(r"\x1b\[[0-9;]*m", "", text)

        ms = (per_line_timings[idx] if per_line_timings and idx < len(per_line_timings) else None)
        ms_str = f"{ms:.1f} ms" if ms is not None else ""

        # Layout: "0.41  shortpath:line  text…………………………  Xms"
        score_str = f"{_color_score(sim)}{sim:.2f}{COLOR_RESET}"
        path_short = _shorten_path(path, max(20, width // 4))
        prefix = f"{score_str}  {COLOR_CYAN}{path_short}{COLOR_RESET}:{COLOR_GREEN}{lineno}{COLOR_RESET}  "

        # Calculate available space for text
        prefix_plain_len = len(_re.sub(r"\x1b\[[0-9;]*m", "", prefix))
        ms_plain_len = len(ms_str) + 2 if ms_str else 0
        text_budget = max(20, width - prefix_plain_len - ms_plain_len)
        if len(text) > text_budget:
            text = text[: text_budget - 1] + "…"
        text_pad = max(1, width - prefix_plain_len - len(text) - ms_plain_len)
        if ms_str:
            print(f"{prefix}{text}{' ' * text_pad}{COLOR_CYAN}{ms_str}{COLOR_RESET}")
        else:
            print(f"{prefix}{text}")

    # ── SCATTER (opt-in) ───────────────────────────────────────────────
    if scatter:
        q_vec_3d = _vectorize_3d_from_query_text(q_vec, model)
        scatter_matches = []
        for item in top_matches:
            if len(item) >= 4:
                _hd, sim, output_str, raw_text = item[0], item[1], item[2], item[3]
                l_vec_3d = _vectorize_3d(raw_text, model)
            else:
                _hd, sim, output_str = item[0], item[1], item[2]
                try:
                    l_vec_3d = [float(_hd[0]), float(_hd[1]), float(_hd[2])]
                except (IndexError, TypeError):
                    l_vec_3d = [0.0, 0.0, 0.0]
            scatter_matches.append((l_vec_3d, sim, output_str))
        print()
        print(render_3d_scatter(q_vec_3d, scatter_matches))

    return 0


def _vectorize_3d_from_query_text(q_vec, model):
    """q_vec model'in HD uzayında olabilir; scatter için 3D'ye düşür.
    Mevcut q_vec zaten 3D ise olduğu gibi döner."""
    try:
        return [float(q_vec[0]), float(q_vec[1]), float(q_vec[2])]
    except (IndexError, TypeError):
        return [0.0, 0.0, 0.0]


def krep_search(query_str, files_or_dirs, line_number=True, recursive=False,
                limit=5, scatter=False):
    """
    Ana vektör arama arayüzü. Sorguyu vektörleştirir, dosyaları mmap / ham olarak okur
    ve en yakın benzerlikteki satırları koordinatlarıyla listeler.

    Dispatch:
    - Path başına kayıtlı PPMI+SVD modeli varsa → model ile vectorize (sözlüksüz).
    - ripgrep sistemde varsa + dosya argümanı varsa → _krep_rg_streaming
      (150-3000x daha hızlı line-level prefilter). Model varsa rg motoru da
      HD vec ile cosine yapar.
    - Aksi halde (rg yok veya stdin modu): yerleşik process_file walker.
    """
    import mmap
    from kishi.krep_i18n import t

    # Toplam süre ölçümü için başlangıç
    _search_t0 = _time.perf_counter()

    # 0. Model lookup (varsa)
    model = _resolve_model(files_or_dirs)

    # 1. Sorgunun vektörünü bul (model varsa HD, yoksa keyword 3D)
    q_vec = _vectorize_dispatch(query_str, model)
    if not any(q_vec):
        print(f"{COLOR_RED}{t('err_no_concept')}{COLOR_RESET}")
        return 1

    matches = []

    # === DISPATCH: rg streaming yolu (varsa ve dosya argümanı varsa) ===
    read_from_stdin_check = (not files_or_dirs) or ("-" in files_or_dirs)
    use_rg = _HAS_RG and not read_from_stdin_check
    if use_rg:
        rg_matches, stats = _krep_rg_streaming(
            query_str=query_str,
            q_vec=q_vec,
            paths=files_or_dirs,
            limit=limit,
            model=model,
        )
        if stats.get("reason") == "rg_spawn_failed":
            print(f"{COLOR_AMBER}{t('rg_spawn_warning')}{COLOR_RESET}",
                  file=sys.stderr)
        elif rg_matches:
            return _krep_finalize(
                rg_matches, q_vec, limit, model=model,
                query_str=query_str,
                elapsed_ms=(_time.perf_counter() - _search_t0) * 1000.0,
                scatter=scatter,
            )
        elif stats.get("reason") == "no_pattern":
            # Sorgu kelimeleri çok kısa (<3 char) — fallback'in
            # bigram benzerliği genişletmesi tek şans, devam.
            pass
        else:
            # rg pattern ürettiği halde 0 match bulduysa: kullanıcı
            # "login authorization" yazdı ama dosyada "auth token" var
            # gibi semantic-eşleşme durumu. Fallback walker'a düş ki
            # bigram-tabanlı concept-vector eşleşmesi şansı kalsın.
            pass
    
    def process_file(file_path):
        if not os.path.isfile(file_path):
            return

        # Model yoksa: keyword-based concept pruning. Model varsa: pruning yok
        # (file-level vec hesaplaması SVD uzayında pahalı + gerek yok).
        if model is None:
            file_vec = get_file_concept_vector(file_path)
            if file_vec is not None:
                has_overlap = False
                for idx in range(3):
                    if q_vec[idx] > 0.0 and file_vec[idx] > 0.0:
                        has_overlap = True
                        break
                if not has_overlap:
                    return

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                size = os.path.getsize(file_path)
                if size == 0:
                    return
                lines = []
                if size > 1024 * 1024:
                    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                        content = mm.read().decode('utf-8', errors='ignore')
                        lines = content.splitlines()
                else:
                    lines = f.read().splitlines()

                for idx, line in enumerate(lines, 1):
                    line_clean = line.strip()
                    if not line_clean:
                        continue
                    l_vec = _vectorize_dispatch(line_clean, model)
                    if not any(l_vec):
                        continue
                    similarity = _cosine_anyd(q_vec, l_vec)
                    if similarity >= 0.3:
                        matches.append((l_vec, similarity,
                                        f"{COLOR_CYAN}{file_path}{COLOR_RESET}:"
                                        f"{COLOR_GREEN}{idx}{COLOR_RESET}: {line_clean}",
                                        line_clean))
        except OSError as e:
            print(f"{COLOR_RED}krep: {file_path} okunurken hata: {e.strerror}{COLOR_RESET}")

    # Stdin okuma kontrolü
    read_from_stdin = False
    if not files_or_dirs or "-" in files_or_dirs:
        read_from_stdin = True

    if read_from_stdin:
        idx = 1
        while True:
            try:
                line = sys.stdin.readline()
            except KeyboardInterrupt:
                break
            if not line:
                break
            line_clean = line.strip()
            if not line_clean:
                idx += 1
                continue
            l_vec = _vectorize_dispatch(line_clean, model)
            if not any(l_vec):
                idx += 1
                continue
            similarity = _cosine_anyd(q_vec, l_vec)
            if similarity >= 0.3:
                matches.append((l_vec, similarity,
                                f"{COLOR_CYAN}stdin{COLOR_RESET}:{COLOR_GREEN}{idx}{COLOR_RESET}: {line_clean}",
                                line_clean))
            idx += 1
    else:
        # Dosya yollarını topla
        target_paths = []
        if recursive:
            for sdir in files_or_dirs:
                if os.path.isfile(sdir):
                    target_paths.append(sdir)
                elif os.path.isdir(sdir):
                    for root, _, files in os.walk(sdir):
                        for fname in files:
                            target_paths.append(os.path.join(root, fname))
        else:
            for sdir in files_or_dirs:
                if os.path.isfile(sdir):
                    target_paths.append(sdir)
                elif os.path.isdir(sdir):
                    try:
                        for entry in os.scandir(sdir):
                            if entry.is_file():
                                target_paths.append(entry.path)
                    except OSError:
                        pass

        # Tarama işlemini yap
        for fpath in target_paths:
            process_file(fpath)

    return _krep_finalize(
        matches, q_vec, limit, model=model,
        query_str=query_str,
        elapsed_ms=(_time.perf_counter() - _search_t0) * 1000.0,
        scatter=scatter,
    )
