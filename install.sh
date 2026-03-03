#!/bin/bash
set -e

echo "========================================="
echo "        Kishi Shell Linux Kurulumu       "
echo "========================================="

echo "[1/4] Python Bağımlılıkları ve Kishi Paketini Kuruyor..."
# Kullanıcı bazlı kurulum veya system-wide kurulum. Modern sistemler uyarısını es geçmek için:
pip3 install . --break-system-packages 2>/dev/null || pip3 install .

echo "[2/4] Doğrudan Çalıştırılabilir Dosya Oluşturuluyor..."
sudo cp kishi_runner.py /usr/local/bin/kishi
sudo chmod +x /usr/local/bin/kishi

echo "[3/4] Sisteme Varsayılan Shell Olarak Tanıtılıyor..."
if ! grep -q "/usr/local/bin/kishi" /etc/shells; then
    echo "/usr/local/bin/kishi" | sudo tee -a /etc/shells > /dev/null
    echo "- /etc/shells dosyasına Kishi eklendi."
else
    echo "- Kishi zaten /etc/shells dosyasında kayıtlı."
fi

echo "[4/4] Varsayılan Terminal Değiştiriliyor... (Parolanız İstenilebilir)"
chsh -s /usr/local/bin/kishi

echo "========================================="
echo "✅ Kurulum Tamamlandı!"
echo "Lütfen bilgisayarınızı veya terminal emülatörünüzü yeniden başlatın."
echo "Eğer her şey yolundaysa, terminal direkt olarak Kishi Shell ile açılacaktır."
echo "Kaldırmak için: chsh -s /bin/bash (veya fish)"
echo "========================================="
