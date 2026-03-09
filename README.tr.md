#  Kishi Shell (v1.7.6)

Kishi Shell, %100 Python ile geliştirilmiş, harici yazılım (Go, C) veya eklenti gerektirmeden tam teşekküllü bir **Terminal İşletim Sistemi Arayüzüne (TUI)** dönüşen yeni nesil komut satırıdır. Geleneksel Bash komut setini modern *IDE (Kod Editörü)* ve *Sistem Monitörü* özellikleriyle birleştirir.

##  Kurulum & Çalıştırma
Sisteminize Kishi Shell kurmak için pip aracını kullanın:
```bash
pip install --upgrade kishi-shell
```
Terminale `kishi` yazın ve yepyeni bir dünyaya giriş yapın!

---

##  İleri Düzey Görsel Arayüzler (TUI)
Kishi Shell size Midnight Commander veya `top`/`htop` indirtmez. Kendi içerisinde %100 Python ile renderladığı sıfır-gecikmeli araçlara sahiptir.

### 1-) Çift Panelli IDE (File Explorer)
Dümdüz kara ekranda dosya okumaya son.
- **Komut:** `explore` (veyahut kısayol **`Ctrl + E`**)
Kishi ekranı ikiye böler. Sol tarafta klavye yön tuşlarıyla gezebileceğiniz akıllı bir **Klasör Ağacı** oluşturur (Python, Txt ve Medya dosyalarını emojilerle tanır ).
- Düzenlemek istediğiniz dosyanın üzerine gelip **`Tab`** tuşuna basarsanız, sağdaki panel bir anda **Tam Fonksiyonel Text Editörüne** dönüşür! 
- Kodunuzu yazar, VIM formatlı satır sayılarını görür ve **`Ctrl + S`** ile saniyede kaydedersiniz. 
- Çıkmak için **`Q`** ya basabilirsiniz.

### 2-) Sistem Monitörü (Dashboard)
Bilgisayarınızın kalbini anında izleyin.
- **Komut:** `dashboard`
Arka planda (Background Daemon Thread) izole olarak çalışan bu monitör; size CPU Çekirdek Kullanımını, RAM / SWAP Metriklerini, Root Disk alanını ve Canlı Ağ (Network Down/Up) Trafiğini gösterir. Kesinlikle lag ve donma yapmaz; akıp giden bir terminal deneyimi sunar.

### 3-) Tarihçe Arama (Fuzzy Search)
Eski komutlarınızı bulmak için harici FZF kurmanıza gerek yok.
- **Kısayol:** **`Ctrl + R`**
Daktilo gibi tuşlara bastıkça binlerce eski komutunuz arasından karakter eşleşmesi yaparak istediğiniz komutu saniyede ekranınıza getirir. `Enter`'a basıp komutu çekebilirsiniz.

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

##  Yardım Merkezi (`help`)
Kishi her zaman size asistanlık yapar. Sisteme ait tüm özellikleri ve komut ipuçlarını hatırlamak isterseniz:
- Kapsamlı (Tam) Yardım İçin: `help`
- Hızlıca Kısayol Özetleri İçin: `help less`
yazmanız yeterli olacaktır.

---
**Geliştiren:** Ozhan Gebesoglu  
*Python'un sınırlarını Terminal'de zorlamak için tasarlandı.*
