import re
import math
import os
import sys

# Cython C-Engine Entegrasyon Kontrolü
try:
    from kishi.krep_core import vectorize_text_c, cosine_similarity_c
    CYTHON_AVAILABLE = True
except ImportError:
    CYTHON_AVAILABLE = False

# Local Semantic Model (PPMI + SVD) — opsiyonel numpy bağımlılığı
try:
    from kishi import krep_learn
    LEARN_AVAILABLE = krep_learn.LEARN_AVAILABLE
except ImportError:
    LEARN_AVAILABLE = False
    krep_learn = None

# Yüklenmiş modeli paths bazında cache (REPL ömrü)
_MODEL_CACHE = {}

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
    grid[cy - 8][cx + 2] = "Z (Veri)"
    
    # 2. Y Ekseni (Güvenlik / Erişim) - Yatay eksen sağa
    for c in range(1, 26):
        if cx + c < width:
            grid[cy][cx + c] = "─"
    grid[cy][cx + 26] = "▶"
    grid[cy - 1][cx + 23] = "Y (Guvenlik)"
    
    # 3. X Ekseni (Stabilite / Hata) - Çapraz eksen sol-aşağı
    for d in range(1, 7):
        if cy + d < height and cx - d * 2 >= 0:
            grid[cy + d][cx - d * 2] = "╲"
            grid[cy + d][cx - d * 2 + 1] = "╲"
    if cy + 7 < height and cx - 14 >= 0:
        grid[cy + 7][cx - 14] = "▼"
    if cy + 7 < height and cx - 13 >= 0:
        grid[cy + 7][cx - 12] = "X (Hata)"
        
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
    out.append(f"            {COLOR_AMBER}KREP AI — 3D SEMANTİK VEKTÖR ALANI{COLOR_RESET}")
    out.append("=" * 55)
    for row in grid:
        out.append("".join(row))
    out.append("=" * 55 + "\n")
    return "\n".join(out)

def _resolve_model(files_or_dirs):
    """Verilen paths için kayıtlı LSA modeli varsa yükle (cache'le)."""
    if not LEARN_AVAILABLE or not files_or_dirs:
        return None
    # Stdin modu ("-") veya path olmayanlar atla
    real_paths = [p for p in files_or_dirs if p != "-" and os.path.exists(p)]
    if not real_paths:
        return None
    cache_key = tuple(sorted(os.path.abspath(p) for p in real_paths))
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]
    m = krep_learn.find_model_for(list(real_paths))
    _MODEL_CACHE[cache_key] = m
    return m


def _vectorize_dispatch(text, model):
    """text → 3D vektör. Model varsa model'den, yoksa keyword tabanlı."""
    if model is not None:
        v, _ = krep_learn.vectorize_with_model(text, model)
        return [float(v[0]), float(v[1]), float(v[2])]
    return vectorize_text(text)


def krep_search(query_str, files_or_dirs, line_number=True, recursive=False, limit=5):
    """
    Ana vektör arama arayüzü. Sorguyu vektörleştirir, dosyaları mmap / ham olarak okur
    ve en yakın benzerlikteki satırları koordinatlarıyla listeler.

    Dispatch:
    - Bu paths için kayıtlı PPMI+SVD modeli varsa → model ile vectorize (sözlüksüz).
    - Yoksa → mevcut keyword (X/Y/Z_KEYWORDS) yolu.
    """
    import mmap

    # 0. Model lookup (varsa)
    model = _resolve_model(files_or_dirs)

    # 1. Sorgunun 3D vektörünü bul
    q_vec = _vectorize_dispatch(query_str, model)
    if not any(q_vec):
        print(f"{COLOR_RED}krep: Sorgudan semantik konsept çıkarılamadı.{COLOR_RESET}")
        return 1

    if model is not None:
        labels = model["axis_labels"]
        print(f"{COLOR_CYAN}[krep AI · LSA model]{COLOR_RESET} "
              f"V={model['n_terms']} terms · {model['n_lines']} lines · "
              f"Axes: [{labels[0][:20]}] [{labels[1][:20]}] [{labels[2][:20]}]")
        print(f"{COLOR_CYAN}[krep AI]{COLOR_RESET} Sorgu Vektörü: "
              f"A0={q_vec[0]:+.2f}, A1={q_vec[1]:+.2f}, A2={q_vec[2]:+.2f}")
    else:
        print(f"{COLOR_CYAN}[krep AI]{COLOR_RESET} Sorgu Vektörü: "
              f"X(Hata)={q_vec[0]:.2f}, Y(Guvenlik)={q_vec[1]:.2f}, Z(Veri)={q_vec[2]:.2f}")
    
    matches = []
    
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
                    similarity = cosine_similarity(q_vec, l_vec)
                    if similarity >= 0.3:
                        matches.append((l_vec, similarity,
                                        f"{COLOR_CYAN}{file_path}{COLOR_RESET}:"
                                        f"{COLOR_GREEN}{idx}{COLOR_RESET}: {line_clean}"))
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
            similarity = cosine_similarity(q_vec, l_vec)
            if similarity >= 0.3:
                matches.append((l_vec, similarity, f"{COLOR_CYAN}stdin{COLOR_RESET}:{COLOR_GREEN}{idx}{COLOR_RESET}: {line_clean}"))
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
        
    if not matches:
        print(f"{COLOR_RED}krep: Semantik olarak benzer satır bulunamadı.{COLOR_RESET}")
        return 1
        
    # En yakın eşleşenleri benzerliğe göre sırala
    matches.sort(key=lambda x: x[1], reverse=True)
    top_matches = matches[:limit]
    
    # 3D ASCII Grafiği Render Et
    print(render_3d_scatter(q_vec, top_matches))
    
    # Eşleşen satırları bas
    print(f"{COLOR_CYAN}[EŞLEŞEN SATIRLAR - Semantik Benzerliğe Göre Sıralı]{COLOR_RESET}:")
    for idx, (l_vec, similarity, line_output) in enumerate(top_matches, 1):
        print(f"{idx}. [{COLOR_GREEN}Mesafe/Sim: {similarity:.2f}{COLOR_RESET}] [X={l_vec[0]:.2f}, Y={l_vec[1]:.2f}, Z={l_vec[2]:.2f}] -> {line_output}")
        
    return 0
