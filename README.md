# Kishi Shell

Kishi Shell, modern Python tabanlı, güçlü, modüler ve platformlar arası uyumlu bir terminal kabuğudur (shell). Klasik Bash/Zsh komut satırı deneyimini `prompt_toolkit` ile birleştirerek sözdizimi renklendirmesi (syntax highlighting), otomatik tamamlama, dinamik yönlendirmeler, zeki geçmiş önerileri ve gelişmiş bir betik (scripting) altyapısı sunar.

![Kishi Shell](https://raw.githubusercontent.com/ozhangebesoglu/Kishi-Shell/main/docs/preview.png)

## Özellikler (Features)
- **SOLID Mimari:** Tamamen nesne yönelimli ve temiz kod (Clean Code) prensipleriyle (Lexer, Parser, Expander, Executor) bölünmüştür.
- **Akıllı Arayüz (Smart UI):** Komut yazarken anlık hata tespiti (kırmızı/yeşil) ve Fish-style tarihçe önerileri.
- **Gelişmiş Yönlendirme:** Çıktı ve hata akışları (`>`, `>>`, `2>`, `2>&1`, `|`)
- **İşletim Sistemi Bağımsızlığı:** Linux (Native OS) ve Windows (Experimental) desteği.
- **Dinamik Değişkenler:** Geçici değişken atamaları (`A=5 echo $A`) ve Path genişletmeleri (`~`, `*`).
- **Gömülü Betik Desteği (Scripting):** `if/else`, `while/for` döngüleri ve hafıza içi fonksiyonlar (`myfunc() { ... }`).

## Kurulum (Installation)

Gücünü doğrudan PyPI'dan alır. Kishi'yi işletim sisteminizde standart bir terminal olarak kullanmak için aşağıdaki yöntemlerden birini seçin:

### Yöntem 1: pip ile Kurulum (Önerilen)
Kishi'yi bilgisayarınıza global bir komut olarak yüklemek için standart paket yöneticisini kullanabilirsiniz:
```bash
pip install kishi
```
Bu işlem sonunda terminalinize doğrudan `kishi` yazarak giriş yapabilirsiniz.

### Yöntem 2: Hızlı Kurulum Scriptleri (Linux & Windows)

**Linux (Ubuntu/Debian, Arch, Fedora vs.):**
Kurulum betiğini çalıştırarak Kishi'yi varsayılan terminaliniz yapabilirsiniz.
```bash
chmod +x install.sh
sudo ./install.sh
```
Bu betik arka planda Kishi'yi `/usr/local/bin` dizinine kopyalar ve `/etc/shells` listesine ekleyerek `chsh` ile varsayılan yapar.

**Windows (PowerShell/CMD):**
Windows üzerinde Python yüklüyse, yönetici olarak aşağıdaki dosyayı çalıştırın:
```cmd
install.bat
```
*(Not: Windows mimarisinde arka plan işleri (`&`) ve Unix sinyalleri farklı çalıştığından, varsayılan terminal (`chsh`) yerine `kishi` komutuyla doğrudan çağrılır).*

## Built-in Komutlar
- `cd [dizin]`: Dizin değiştirir
- `pwd`: Mevcut Windows/Linux yolunu basar
- `history / h`: Ekran tarihçesini listeler
- `jobs / fg / bg`: Arka plan (Pipeline) işlemlerini ön plana alır
- `export / unset`: Çevre değişkenlerini yönetir
- `clear`: Terminali temizler ve UI'ı korur
- `[ condition ] / test`: Dosya, tip veya string durum sorguları yapar (Örn: `[ -f path/to.txt ]`)

## Başlangıç Konfigürasyonu
Kullanıcı dizininde `.kishirc` adında bir dosya oluşturarak Kishi'nin her açılışında çalıştırılacak alias ve ortam değişkenlerini ayarlayabilirsiniz.
```bash
# ~/.kishirc
alias ll='ls -la'
export PATH="$PATH:/kisisel/dizin"
```

## Katkıda Bulunma (Contributing)
Projeyi çatallayıp (Fork) yeni özellikler ekleyebilir ve Pull Request gönderebilirsiniz. 
`kishi/` modül dizinindeki `lexer.py`, `parser.py` veya `executor.py` bloklarını geliştirerek çekirdek motoru iyileştirebilirsiniz.

## Lisans
GNU General Public License v3.0 (GPL-3.0)

Kishi Shell açık kaynaklı ve özgür bir yazılımdır. Bu lisans kapsamında, kodu kopyalamakta, değiştirmekte ve dağıtmakta özgürsünüz. **Ancak Kishi Shell kaynak kodlarını kullanarak geliştirdiğiniz veya değiştirdiğiniz her türlü türev yazılımı (derivative work) yine açık kaynaklı (GPL-3.0) olarak topluluğa sunmak zorundasınız.** Kapalı kaynaklı ticari ürünlerde kullanılamaz.
