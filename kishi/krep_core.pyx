# cython: boundscheck=False, wraparound=False, nonecheck=False, cdivision=True
import math
cimport cython
from libc.math cimport sqrt

# Kelime haznesi bazlı 3D kavramsal eşlemeler (X=Hata, Y=Güvenlik, Z=Veri)
cdef list X_KEYWORDS = ['error', 'fail', 'crash', 'bug', 'warning', 'exception', 'fatal', 
                        'timeout', 'kill', 'stop', 'exit', 'quit', 'terminate', 
                        'disconnect', 'break', 'close', 'abort',
                        'hata', 'ariza', 'cokme', 'bozuk', 'kusur', 'problem', 'sorun', 'engel', 'limit', 'uyari', 'istisna']

cdef list Y_KEYWORDS = ['auth', 'login', 'password', 'key', 'token', 'user', 'admin', 
                        'secure', 'crypto', 'cert', 'ssh', 'encrypt', 'decrypt', 
                        'privilege', 'allow', 'denied', 'permission', 'sign',
                        'guvenlik', 'giris', 'sifre', 'anahtar', 'kullanici', 'yetki', 'izin', 'yasak', 'kripto', 'sertifika']

cdef list Z_KEYWORDS = ['database', 'sql', 'db', 'file', 'save', 'write', 'read', 'query', 
                        'list', 'select', 'update', 'insert', 'delete', 'table', 
                        'column', 'row', 'csv', 'json', 'xml', 'storage', 'log',
                        'veri', 'dosya', 'veritabani', 'kayit', 'yaz', 'oku', 'sorgu', 'liste', 'tablo', 'sutun', 'satir', 'depo', 'gunluk', 'bellek']

# Bigram setlerini önbellekleme
cdef list X_BIGRAMS = [{w[i:i+2] for i in range(len(w) - 1)} if len(w) >= 2 else {w} for w in X_KEYWORDS]
cdef list Y_BIGRAMS = [{w[i:i+2] for i in range(len(w) - 1)} if len(w) >= 2 else {w} for w in Y_KEYWORDS]
cdef list Z_BIGRAMS = [{w[i:i+2] for i in range(len(w) - 1)} if len(w) >= 2 else {w} for w in Z_KEYWORDS]

# Yüksek hızlı C-seviyesi Kosinüs Benzerliği
cdef double c_cosine_similarity(double[3] v1, double[3] v2) nogil:
    cdef double dot = v1[0]*v2[0] + v1[1]*v2[1] + v1[2]*v2[2]
    if dot == 0.0:
        return 0.0
    cdef double len1 = sqrt(v1[0]**2 + v1[1]**2 + v1[2]**2)
    cdef double len2 = sqrt(v2[0]**2 + v2[1]**2 + v2[2]**2)
    if len1 == 0.0 or len2 == 0.0:
        return 0.0
    return dot / (len1 * len2)

# C-seviyesi Jaccard Benzerliği (Bigram Kesişimi)
cdef double jaccard_sim(set s1, set s2):
    cdef int intersect_len = len(s1 & s2)
    cdef int union_len = len(s1) + len(s2) - intersect_len
    if union_len == 0:
        return 0.0
    return <double>intersect_len / <double>union_len

# C-seviyesi Kelime Vektörleştirici
cpdef list get_semantic_vector_c(str word):
    cdef str w = word.lower().strip()
    if not w:
        return [0.0, 0.0, 0.0]

    # 1. Tam veya önek eşleşmesi
    for k in X_KEYWORDS:
        if w.startswith(k):
            return [1.0, 0.0, 0.0]
    for k in Y_KEYWORDS:
        if w.startswith(k):
            return [0.0, 1.0, 0.0]
    for k in Z_KEYWORDS:
        if w.startswith(k):
            return [0.0, 0.0, 1.0]

    # 2. Yumuşak Harf Benzerliği (Bigram Jaccard)
    cdef set wb = {w[i:i+2] for i in range(len(w) - 1)} if len(w) >= 2 else {w}
    
    cdef double x_score = 0.0
    cdef double y_score = 0.0
    cdef double z_score = 0.0
    cdef double sim = 0.0
    
    for xb in X_BIGRAMS:
        sim = jaccard_sim(wb, xb)
        if sim > x_score:
            x_score = sim

    for yb in Y_BIGRAMS:
        sim = jaccard_sim(wb, yb)
        if sim > y_score:
            y_score = sim

    for zb in Z_BIGRAMS:
        sim = jaccard_sim(wb, zb)
        if sim > z_score:
            z_score = sim

    # Eşik filtresi
    if x_score < 0.4: x_score = 0.0
    if y_score < 0.4: y_score = 0.0
    if z_score < 0.4: z_score = 0.0

    return [x_score, y_score, z_score]

# Metin/Satır Vektörleştirici
cpdef list vectorize_text_c(str text):
    import re
    cdef list words = re.findall(r'[A-Za-z0-9_]+', text)
    if not words:
        return [0.0, 0.0, 0.0]

    cdef double vec[3]
    vec[0] = 0.0
    vec[1] = 0.0
    vec[2] = 0.0
    cdef int matched_count = 0
    cdef list v
    cdef str w

    for w in words:
        v = get_semantic_vector_c(w)
        if v[0] > 0.0 or v[1] > 0.0 or v[2] > 0.0:
            vec[0] += v[0]
            vec[1] += v[1]
            vec[2] += v[2]
            matched_count += 1

    if matched_count == 0:
        return [0.0, 0.0, 0.0]

    cdef double length = sqrt(vec[0]**2 + vec[1]**2 + vec[2]**2)
    if length > 0.0:
        return [vec[0] / length, vec[1] / length, vec[2] / length]
    return [0.0, 0.0, 0.0]

# Python'a açılan C-seviyesi Kosinüs Benzerliği sarmalayıcısı
cpdef double cosine_similarity_c(list v1, list v2):
    cdef double[3] cv1
    cdef double[3] cv2
    cv1[0] = v1[0]
    cv1[1] = v1[1]
    cv1[2] = v1[2]
    cv2[0] = v2[0]
    cv2[1] = v2[1]
    cv2[2] = v2[2]
    return c_cosine_similarity(cv1, cv2)
