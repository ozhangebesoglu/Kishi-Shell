# Kishi Shell

Kishi Shell, modern Python tabanlı, güçlü, modüler ve platformlar arası uyumlu bir terminal kabuğudur (shell). Klasik Bash/Zsh komut satırı deneyimini `prompt_toolkit` ile birleştirerek sözdizimi renklendirmesi (syntax highlighting), otomatik tamamlama, dinamik yönlendirmeler, zeki geçmiş önerileri ve gelişmiş bir betik (scripting) altyapısı sunar.

*For English documentation, please scroll down below.*

![Kishi Shell](https://raw.githubusercontent.com/ozhangebesoglu/Kishi-Shell/main/docs/preview.png)

## 🇹🇷 Türkçe Dokümantasyon

### Özellikler
- **SOLID Mimari:** Tamamen nesne yönelimli ve temiz kod (Clean Code) prensipleriyle (Lexer, Parser, Expander, Executor) bölünmüştür.
- **Akıllı Arayüz (Smart UI):** Komut yazarken anlık hata tespiti (kırmızı/yeşil), Fish-style tarihçe önerileri ve açılır tamamlama menüsü (Drop-down Completions).
- **Gelişmiş Yönlendirme:** Çıktı ve hata akışları (`>`, `>>`, `2>`, `2>&1`, `|`).
- **İşletim Sistemi Bağımsızlığı:** Linux (Native OS) ve Windows (Gelişmiş `subprocess` Pipeline Desteği) uyumluluğu.
- **Dinamik Değişkenler:** Geçici değişken atamaları (`A=5 echo $A`) ve Path genişletmeleri (`~`, `*`).
- **Gömülü Betik Desteği (Scripting):** `if/else`, `while/for` döngüleri ve hafıza içi fonksiyonlar (`myfunc() { ... }`).

### Kurulum

**Yöntem 1: pip ile Kurulum (Önerilen)**
```bash
pip install kishi
```

**Yöntem 2: Hızlı Kurulum Scriptleri (Linux & Windows)**
Linux (Ubuntu/Arch/Fedora vb.) için varsayılan terminal yapar:
```bash
chmod +x install.sh
sudo ./install.sh
```
Windows (PowerShell/CMD) için varsayılan Python ortamına kurar:
```cmd
install.bat
```

### Başlangıç Konfigürasyonu
Kullanıcı dizininde `.kishirc` adında bir dosya oluşturarak Kishi'nin her açılışında çalıştırılacak alias ve ortam değişkenlerini ayarlayabilirsiniz.
```bash
# ~/.kishirc
alias ll='ls -la'
export PATH="$PATH:/kisisel/dizin"
```

---

## 🇬🇧 English Documentation

Kishi Shell is a modern, Python-based, powerful, modular, and cross-platform terminal shell. By combining the classic Bash/Zsh command-line experience with `prompt_toolkit`, it offers syntax highlighting, smart auto-completion menus, dynamic pipeline routing, intelligent history suggestions (Fish style), and an advanced built-in scripting infrastructure.

### Features
- **SOLID Architecture:** Fully object-oriented and divided by Clean Code principles (Lexer, Parser, Expander, Executor components).
- **Smart UI:** Real-time syntax error detection (red/green rendering), Fish-style ghost suggestions, and drop-down auto-completion menus for paths/commands.
- **Advanced Redirection:** Output and error streams support (`>`, `>>`, `2>`, `2>&1`, `|`).
- **OS Independence:** Linux Native OS compatibility along with full Windows support via a specialized `subprocess` pipeline fallback.
- **Dynamic Variables:** Temporary variable assignments (`A=5 echo $A`) and path expansions (`~`, `*`).
- **Built-in Scripting Engine:** `if/else`, `while/for` loop structures, and in-memory callable routines (`myfunc() { ... }`).

### Installation

**Method 1: via pip (Recommended)**
```bash
pip install kishi
```

**Method 2: Quick Installer Scripts (Linux & Windows)**
For Linux systems, this will make Kishi your default `chsh` shell:
```bash
chmod +x install.sh
sudo ./install.sh
```
For Windows (PowerShell/CMD), run this as Administrator:
```cmd
install.bat
```

### Startup Configuration
Create a `.kishirc` file in your home directory to set up aliases and environment variables executed every time Kishi starts.
```bash
# ~/.kishirc
alias ll='ls -la'
export PATH="$PATH:/personal/paths"
```

## License
GNU General Public License v3.0 (GPL-3.0)

Kishi Shell is a free and open-source software. Under this license, you are free to copy, modify, and distribute the code. **However, any derivative work or project using Kishi Shell's source code MUST also be distributed as open-source under the GPL-3.0 license.** It cannot be used in completely closed-source commercial products.
