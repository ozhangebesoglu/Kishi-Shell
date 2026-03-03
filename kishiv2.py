#!/usr/bin/env python3
"""
Kishi Shell - Adım 2
Yeni: Built-in komutlar (cd, pwd, exit, help, clear)
"""

import os
import sys

# ==================== BUILT-IN KOMUTLAR ====================
# Bunlar fork+exec ile DEĞİL, shell'in kendi içinde çalışır
# Çünkü shell'in kendi state'ini değiştirmeleri gerekir

def kishi_cd(args):
    """Dizin değiştir - fork ile yapılamaz!"""
    if len(args) < 2:
        # cd tek başına yazılırsa → home dizinine git
        hedef = os.environ.get("HOME", "/")
    else:
        hedef = args[1]

    try:
        os.chdir(hedef)
    except FileNotFoundError:
        print(f"kishi: cd: {hedef}: dizin bulunamadi")
    except PermissionError:
        print(f"kishi: cd: {hedef}: izin reddedildi")

def kishi_pwd(args):
    """Mevcut dizini göster"""
    print(os.getcwd())

def kishi_exit(args):
    """Shell'den çık"""
    print("kishi: gorusuruz!")
    sys.exit(0)

def kishi_help(args):
    """Yardım menüsü"""
    print("""
Kishi Shell v0.2

Built-in komutlar:
  cd [dizin]     Dizin degistir
  pwd            Mevcut dizini goster
  clear          Ekrani temizle
  help           Bu menuyu goster
  exit           Shell'den cik

Herhangi bir Linux komutu calistirilabilir:
  ls, cat, df, whoami, date, grep, wc ...
""")

def kishi_clear(args):
    """Ekranı temizle"""
    print("\033[H\033[2J", end="")


# Built-in komutları sözlükte tut
# Yeni built-in eklemek istersen buraya eklemen yeterli
BUILTINS = {
    "cd": kishi_cd,
    "pwd": kishi_pwd,
    "exit": kishi_exit,
    "help": kishi_help,
    "clear": kishi_clear,
    
}

# ==================== ANA DÖNGÜ ====================
while True:
    try:
        komut = input("kishi$ -> ")
        args = komut.split()

        if not args:
            continue

        # ÖNCE built-in mi kontrol et
        # cd, pwd, exit gibi komutlar burada yakalanır
        if args[0] in BUILTINS:
            BUILTINS[args[0]](args)
            continue  # fork'a gitme, sonraki komutu bekle

        # Built-in değilse → fork + exec ile çalıştır
        pid = os.fork()

        if pid == 0:
            try:
                os.execvp(args[0], args)
            except FileNotFoundError:
                print(f"kishi: {args[0]}: komut bulunamadi")
                sys.exit(1)
        else:
            os.waitpid(pid, 0)

    except EOFError:
        # Ctrl+D basılırsa
        print("\nkishi: gorusuruz!")
        break