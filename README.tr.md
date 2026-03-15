#  Kishi Shell (v2.0.0.1)

[![CI](https://github.com/ozhangebesoglu/Kishi-Shell/actions/workflows/ci.yml/badge.svg)](https://github.com/ozhangebesoglu/Kishi-Shell/actions/workflows/ci.yml)

> **Bu projeyi beğendiyseniz lütfen [GitHub](https://github.com/ozhangebesoglu/Kishi-Shell)'da ⭐ yıldız verin ve [AUR](https://aur.archlinux.org/packages/kishi-shell)'da oy kullanın! Desteğiniz projenin büyümesine yardımcı olur.**

[![asciicast](https://asciinema.org/a/LQ7jQXtlGHgNoEVa.svg)](https://asciinema.org/a/LQ7jQXtlGHgNoEVa)

Kishi Shell, %100 Python ile geliştirilmiş, harici yazılım (Go, C) veya eklenti gerektirmeden tam teşekküllü bir **Terminal İşletim Sistemi Arayüzüne (TUI)** dönüşen yeni nesil komut satırıdır. Geleneksel Bash komut setini modern *IDE (Kod Editörü)* ve *Sistem Monitörü* özellikleriyle birleştirir.

##  Kurulum & Çalıştırma

### Seçenek 1: AUR ile Kurulum (Arch Linux) — Önerilen
```bash
yay -S kishi-shell
```

### Seçenek 2: Kaynaktan Kurulum
```bash
git clone https://github.com/ozhangebesoglu/Kishi-Shell.git
cd Kishi-Shell
chmod +x install.sh
./install.sh
```
Yükleyici önce `pip3 install .` deneyecektir. Sisteminiz PEP 668 koruması kullanıyorsa, size **sanal ortam** (önerilen) veya `--break-system-packages` seçeneği sunacaktır.

### Seçenek 3: pip ile Kurulum (PyPI)
```bash
pip install --upgrade kishi-shell
```

Terminale `kishi` yazarak Kishi Shell'i başlatabilirsiniz. Çıkmak için `exit` yazmanız yeterlidir.

---

##  Kishi'yi Login Shell Olarak Kullanma

Kishi güvenle varsayılan login shell olarak ayarlanabilir. Profile sourcing, non-interactive çalıştırma ve otomatik fallback desteği vardır.

```bash
# Kishi'yi izin verilen shell'lere ekle
echo /usr/local/bin/kishi | sudo tee -a /etc/shells

# Varsayılan shell olarak ayarla
chsh -s /usr/local/bin/kishi
```

**Login Shell Özellikleri:**
- **Profile sourcing:** Giriş yapıldığında `/etc/profile` ve `~/.profile` (veya `~/.bash_profile`) otomatik yüklenir
- **Non-interactive mod:** Masaüstü yöneticileri (GDM, SDDM, LightDM) için `kishi -c "komut"` düzgün çalışır
- **Pipe/script modu:** `echo "echo merhaba" | kishi` takılmadan çalışır
- **Fallback güvenliği:** Kishi başlangıçta çökerse otomatik olarak `/bin/bash` veya `/bin/sh`'a düşer — sisteminiz asla kilitlenmez
- **Sinyal yönetimi:** SIGHUP (terminal kapanma) ve SIGTERM (kapatma) sinyalleri düzgün işlenir

**Çalıştırma Modları:**
```bash
kishi                              # İnteraktif mod (prompt + arayüz)
kishi -c "ls -la"                  # Tek komut çalıştır ve çık
kishi --login                      # Login shell modu (profilleri yükle)
kishi -l -c "exec gnome-session"   # Login + komut (masaüstü yöneticileri kullanır)
echo "echo merhaba" | kishi        # Pipe modu (non-interactive, banner yok)
```

---

##  İleri Düzey Görsel Arayüzler (TUI)
Kishi Shell size Midnight Commander veya `top`/`htop` indirtmez. Kendi içerisinde %100 Python ile renderladığı sıfır-gecikmeli araçlara sahiptir.

### 1-) VSCode-like Unified IDE & Dashboard
Dümdüz kara ekranda dosya okumaya son! Kishi Shell size Midnight Commander veya `top`/`htop` indirtmez. İkisini mükemmel bir VSCode düzeninde birleştirir.
- **Komut:** `dashboard`
Arka planda izole olarak çalışan bu sistem; CPU Çekirdek Kullanımını, RAM / SWAP Metriklerini, Root Disk alanını ve Canlı Ağ Trafiğini (Down/Up) yan panellerde gösterir. 
![Dashboard UI](assets/dashboard.png)
![Dark Mode](assets/darkmode.png)

- **`Ctrl + E`** tuşuna bastığınızda, ortadaki devasa terminal anında **Çift Panelli bir IDE'ye (Geliştirme Ortamı)** dönüşür. Ekran üst bölümden ikiye bölünerek Sol tarafa Klasör Ağacını (Tree), Sağ tarafa Kod Editörünü yerleştirir. Alt kısım Kishi Terminali olarak kalır.
- Paneller arası gezinmek için **`Tab`** tuşunu kullanarak Ağaç -> Editör -> Terminal -> Girdi Satırı arasında mükemmel bir döngü kurabilirsiniz.
- Kodunuzu yazar, **`Ctrl + S`** ile saniyede kaydedersiniz. 
![IDE Layout](assets/ide_layout.png)
![IDE + Vite Dev Server](assets/dashboard_ide_vite.png)

#### Dashboard Klavye Kısayolları

| Kısayol | İşlev |
|---------|-------|
| `Enter` | Komut çalıştır |
| `Tab` | Komut ve yol otomatik tamamlama |
| `Ctrl + E` | IDE Explorer'ı aç/kapat (dosya ağacı + editör) |
| `Shift + Tab` | Paneller arası geçiş |
| `Ctrl + R` | Komut geçmişinde fuzzy arama |
| `Ctrl + C` | Çalışan programa SIGINT gönder |
| `Ctrl + Q` | Dashboard'dan çık |
| `PgUp / PgDn` | Terminal çıktısını kaydır |
| `Home / End` | Çıktının başına / sonuna atla |

### 2-) İnteraktif Terminal & Dizin Senkronizasyonu
Ekranın altındaki Kishi Terminali, Klasör Ağacıyla canlı senkronize çalışır! 
- Komut satırına `cd` yazıp klasör değiştirdiğinizde Ağaç da otomatik güncellenir.
- `input()` gibi sizden veri bekleyen uzun soluklu Python veya Bash scriptlerini çalıştırdığınızda arayüz asla donmaz! Arka plan ikili veri akışı (binary streaming) sayesinde komut çıkıntıları direkt arayüze basılır ve en alttaki komut satırından yazdığınız girdiler doğrudan kodun `stdin` girişine yönlendirilir.
- **`Ctrl + C`** ile çalışan process'i dashboard'u kapatmadan öldürebilir, ardından terminali kullanmaya devam edebilirsiniz.
- Terminal gerektiren programlar (`python`, `node`, `java`) tam pseudo-terminal (PTY) desteği sayesinde düzgün çalışır.
![Interactive Terminal](assets/interactive_terminal.png)
![Ctrl+C Sinyal Yönetimi](assets/dashboard_sigint.png)
![Terminal Komutları](assets/dashboard_terminal_ls.png)
![Dashboard Bash Help](assets/dashboard_bash_help.png)

### 3-) Bağımsız Dosya Gezgini
IDE Explorer, dashboard dışında bağımsız bir çift panelli dosya tarayıcısı olarak da çalışır. Tüm dosya sisteminizde gezinin, dizinleri önizleyin ve satır numaralı editörle kod düzenleyin.
- **Komut:** `explore`
- **Kısayol:** **`Ctrl + E`**
![Bağımsız Explorer](assets/explorer_standalone.png)
![Kod Düzenleme & Kaydetme](assets/explorer_code_editing.png)

### 4-) Tab Completion & Sözdizimi Renklendirme
Kishi, sistem komutları, yerleşik komutlar ve dosya yolları için gerçek zamanlı tab completion sunar. Bilinen komutlar yeşil, bilinmeyenler kırmızı görünür.
![Tab Completion](assets/tab_completion.png)

### 5-) Yardım Sistemi & Tarihçe Arama (Fuzzy Search)
- Kapsamlı Yardım İçin: `help` — Hızlı Kısayollar İçin: `help less`
![Yardım Rehberi](assets/help_guide.png)
![Yardım Genel Bakış](assets/help_overview.png)

Eski komutlarınızı bulmak için harici FZF kurmanıza gerek yok.
- **Kısayol:** **`Ctrl + R`**
Daktilo gibi tuşlara bastıkça binlerce eski komutunuz arasından karakter eşleşmesi yaparak istediğiniz komutu saniyede ekranınıza getirir. `Enter`'a basıp komutu çekebilirsiniz.

---

##  Eklenti Pazaryeri (Marketplace)
Kishi Shell, Python gücüyle çalışan dinamik bir eklenti ekosistemine sahiptir. Terminalden hiç çıkmadan ve oturumu yeniden başlatmadan resmi eklentilere göz atabilir, kurabilir ve yönetebilirsiniz.

### Eklenti Komutları

| Komut | Açıklama |
|-------|----------|
| `plugin list` | Kurulu eklentileri listele |
| `plugin market` | Marketteki eklentilere göz at |
| `plugin install <isim>` | Marketten eklenti kur |
| `plugin install <url>` | Direkt GitHub raw URL'den eklenti kur |
| `plugin remove <isim>` | Eklentiyi kaldır |

### Mevcut Eklentiler

| Eklenti | Komut | Açıklama | Kullanım |
|---------|-------|----------|----------|
| **weather** | `weather` | [wttr.in](https://wttr.in) üzerinden canlı hava durumu | `weather` (otomatik konum) veya `weather Istanbul` |
| **ip** | `ip` | [ipinfo.io](https://ipinfo.io) üzerinden genel IP ve konum bilgisi | `ip` |
| **qr** | `qr` | Terminalde ASCII QR kod oluştur | `qr https://github.com` veya `qr "Merhaba"` |
| **hello** | `hello` | Demo eklenti — market bağlantınızı test edin | `hello` |

### Örnek Kullanım

```bash
# Markete göz at
Kishi$ -> plugin market
 Available Plugins in Kishi Marketplace:
  - hello.py
  - weather.py
  - ip.py
  - qr.py

# Eklenti kur
Kishi$ -> plugin install weather
[*] Downloading 'weather.py' from marketplace...
[+] Plugin 'weather' installed successfully!

# Hemen kullan — yeniden başlatmaya gerek yok
Kishi$ -> weather Istanbul
Istanbul: ⛅️ +18°C

# Kurulu eklentileri kontrol et
Kishi$ -> plugin list
 Installed Plugins:
  - weather

# Artık gerekmiyorsa kaldır
Kishi$ -> plugin remove weather
[+] Plugin 'weather' removed.
```

Eklentiler bir kez kurulduğunda normal komutlar kadar hızlı çalışır ve Kishi'nin olay döngüsüne entegre olur. Eklentiler `~/.kishi/plugins/` dizininde saklanır ve shell başlangıcında otomatik olarak yüklenir.

### Kendi Eklentinizi Oluşturma

Bir `.py` dosyası oluşturun — **dosya adı, dışa aktardığı komut adıyla birebir aynı olmalıdır:**

```python
# benikomutum.py
def benikomutum(args):
    """args[0] = komut adı, args[1:] = kullanıcı argümanları"""
    if len(args) < 2:
        print("Kullanım: benikomutum <metin>")
        return 1

    print(f"Merhaba, {args[1]}!")
    return 0  # çıkış kodu: 0 = başarılı

PLUGIN_COMMANDS = {
    "benikomutum": benikomutum  # anahtar dosya adıyla EŞLEŞMELİ (benikomutum.py -> "benikomutum")
}
```

Herhangi bir kaynaktan kurun:
```bash
# Resmi marketten (Kishi-Plugins reposuna PR gönderin)
plugin install benikomutum

# Veya herhangi bir raw GitHub URL'den
plugin install https://raw.githubusercontent.com/kullanici/repo/main/benikomutum.py
```

Daha fazla bilgi için [Kishi-Plugins](https://github.com/ozhangebesoglu/Kishi-Plugins) deposuna göz atın.

---

##  Scripting ve Çevre Değişkenleri (Environment)

### Değişken Atamak ve Okumak (`export`)
Kishi ortamına diğer programların da okuyabilmesi için yeni değişkenler tanımlayabilirsiniz.
```bash
Kishi$ -> export MY_KEY="12345"
Kishi$ -> echo $MY_KEY
12345
```
Silmek için `unset MY_KEY` yazmanız yeterlidir. Ortamda yüklü tüm değişkenleri sadece `export` yazarak listeleyebilirsiniz.

### Kendi Komutlarınızı Üretin (`myfunc`)
Bir işi sürekli tekrar ediyorsanız Kishi'ye anında kod blokları (Sub-Routines) öğretebilirsiniz. Fonksiyon tanımlamak çok kolaydır:

```bash
Kishi$ -> merhaba() { echo "Sisteme Hosgeldiniz $USER"; ls -l; }
Kishi$ -> merhaba
Sisteme Hosgeldiniz ozhangebesoglu
drwxrwxr-x 2 user user 4096 ...
```
Fonksiyonları ard arda noktalı virgül (`;`) ile zincirleyebilir, tek satırda devasa otomasyon scriptleri çalıştırabilirsiniz. Dahası, komutlarınızın ve çıktılarınızın ortasına `|`, `&&`, `>`, `>>` gibi karmaşık Shell operatörleri de sıkıştırabilirsiniz!

---

##  Mimari

Kishi, SOLID prensiplerine uygun klasik bir **derleyici hattı (compiler pipeline)** üzerine inşa edilmiştir:

```
Girdi → Lexer → Parser → Expander → Executor
          │        │         │          │
       token'lar   AST    genişletilmiş fork/exec
                           argümanlar   pipeline'lar
```

| Modül | Sorumluluk |
|-------|-----------|
| `lexer.py` | Tokenizasyon, tırnak takibi |
| `parser.py` | Recursive descent parser, AST oluşturma |
| `expander.py` | `$VAR`, glob, tilde, `$(cmd)` genişletme |
| `executor.py` | fork/exec, pipeline'lar, yönlendirmeler, iş kontrolü |
| `builtins.py` | 26 yerleşik komut |
| `tui_dashboard.py` | VS Code tarzı dashboard (5 SOLID sınıfı) |
| `tui_explorer.py` | Çift panelli IDE explorer |
| `tui_fuzzy.py` | Ctrl+R fuzzy arama motoru |
| `ui.py` | Sözdizimi vurgulama, tamamlama, kısayollar |
| `main.py` | Login shell, mod algılama, profile sourcing |

---

##  Yardım Merkezi (`help`)
Kishi her zaman size asistanlık yapar. Sisteme ait tüm özellikleri ve komut ipuçlarını hatırlamak isterseniz:
- Kapsamlı (Tam) Yardım İçin: `help`
- Hızlıca Kısayol Özetleri İçin: `help less`
yazmanız yeterli olacaktır.

---

## Katkıda Bulunun

Katkılarınızı bekliyoruz! Başlamak için [CONTRIBUTING.md](CONTRIBUTING.md) dosyasına göz atın.

---
**Geliştiren:** Ozhan Gebesoglu  
*Python'un sınırlarını Terminal'de zorlamak için tasarlandı.*

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=ozhangebesoglu/Kishi-Shell&type=Date)](https://star-history.com/#ozhangebesoglu/Kishi-Shell&Date)
