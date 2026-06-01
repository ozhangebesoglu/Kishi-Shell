"""
Krep i18n — sade çeviri tablosu.

Tasarım kararı: küçük (~20 string) olduğu için gettext/.mo overhead'i
yerine düz Python dict. Yeni dil eklemek 5 satır iş.

Varsayılan dil: en
Override: krep --lang tr / --lang en
Programatik: kishi.krep_i18n.set_lang('tr')
"""

_LANG = "en"


_STRINGS = {
    "en": {
        # Header
        "results_header": "krep · {n} results · {q!r} · {model_info}",
        "no_results_header": "krep · no results · {q!r} · {model_info}",
        "model_lsa": "LSA model ({n_terms} terms, {n_lines} lines)",
        "model_keyword": "keyword engine",
        # Errors
        "err_no_query": "krep: pattern (query) is required. Type 'krep --help'.",
        "err_no_concept": "krep: could not extract a semantic concept from the query.",
        "err_no_match": "krep: no semantically similar lines found.",
        "err_no_numpy": (
            "krep --learn requires numpy and scipy.\n"
            "  Install: pip install \"kishi-shell[krep]\"\n"
            "  Arch:    sudo pacman -S python-numpy python-scipy"
        ),
        "err_invalid_interval": "krep: invalid interval {val!r}: {err}",
        "err_invalid_lang": "krep: invalid --lang {val!r} (use 'en' or 'tr')",
        # Status
        "model_saved": "model saved: {path}",
        "model_updated": "model updated: {path}",
        "model_stats": "{n_terms} terms, {n_lines} lines, {elapsed:.1f}s",
        "no_changes": "no changes detected — model unchanged.",
        "purged": "purged {n} model(s).",
        "rg_spawn_warning": "krep: ripgrep spawn failed, falling back to Python engine.",
        # List
        "models_empty": "No cached models. Build one with `krep --learn PATH`.",
        "label_size": "size",
        "label_vocab": "vocab",
        "label_lines": "lines",
        "label_age": "age",
        "label_ago": "ago",
        "label_sources": "sources",
        "label_axis": "axis",
        "label_fresh": "FRESH",
        "label_stale": "STALE",
        "auto_refresh_off": "auto-refresh off",
        "auto_refresh_on": "auto-refresh {interval}",
        # Scatter
        "scatter_title": "KREP AI — 3D Semantic Vector Space",
        "axis_x": "X (Errors)",
        "axis_y": "Y (Security)",
        "axis_z": "Z (Data)",
    },
    "tr": {
        # Header
        "results_header": "krep · {n} sonuç · {q!r} · {model_info}",
        "no_results_header": "krep · sonuç yok · {q!r} · {model_info}",
        "model_lsa": "LSA modeli ({n_terms} kelime, {n_lines} satır)",
        "model_keyword": "anahtar kelime motoru",
        # Errors
        "err_no_query": "krep: sorgu (pattern) gerekli. 'krep --help' ile yardım al.",
        "err_no_concept": "krep: sorgudan semantik konsept çıkarılamadı.",
        "err_no_match": "krep: semantik olarak benzer satır bulunamadı.",
        "err_no_numpy": (
            "krep --learn için numpy ve scipy gerekli.\n"
            "  Kurulum: pip install \"kishi-shell[krep]\"\n"
            "  Arch:    sudo pacman -S python-numpy python-scipy"
        ),
        "err_invalid_interval": "krep: geçersiz aralık {val!r}: {err}",
        "err_invalid_lang": "krep: geçersiz --lang {val!r} ('en' veya 'tr' kullanın)",
        # Status
        "model_saved": "model kaydedildi: {path}",
        "model_updated": "model güncellendi: {path}",
        "model_stats": "{n_terms} kelime, {n_lines} satır, {elapsed:.1f}s",
        "no_changes": "değişiklik yok — model güncellenmedi.",
        "purged": "{n} model silindi.",
        "rg_spawn_warning": "krep: ripgrep başlatılamadı, Python motoruna düşülüyor.",
        # List
        "models_empty": "Model bulunamadı. `krep --learn YOL` ile bir tane oluştur.",
        "label_size": "boyut",
        "label_vocab": "kelime",
        "label_lines": "satır",
        "label_age": "yaş",
        "label_ago": "önce",
        "label_sources": "kaynaklar",
        "label_axis": "eksen",
        "label_fresh": "TAZE",
        "label_stale": "BAYAT",
        "auto_refresh_off": "otomatik yenileme kapalı",
        "auto_refresh_on": "otomatik yenileme {interval}",
        # Scatter
        "scatter_title": "KREP AI — 3D Semantik Vektör Alanı",
        "axis_x": "X (Hata)",
        "axis_y": "Y (Güvenlik)",
        "axis_z": "Z (Veri)",
    },
}


def set_lang(lang):
    """Aktif dili ayarla. Geçersiz dil ValueError fırlatır."""
    global _LANG
    if lang not in _STRINGS:
        raise ValueError(f"unsupported language: {lang!r} (available: {list(_STRINGS)})")
    _LANG = lang


def get_lang():
    return _LANG


def t(key, **kwargs):
    """Çeviri lookup + format. Anahtar yoksa İngilizce'ye fallback."""
    table = _STRINGS.get(_LANG) or _STRINGS["en"]
    template = table.get(key) or _STRINGS["en"].get(key, key)
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template
