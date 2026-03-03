#!/usr/bin/env python3

import os
import sys

def kishi_cd(args):
    if len(args) < 2:
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
    print(os.getcwd())

def kishi_exit(args):
    print("kishi: gorusuruz!")
    sys.exit(0)

def kishi_help(args):
    print("""
Kishi Shell v0.3 (Final)

Built-in komutlar:
  cd [dizin]     Dizin degistir
  pwd            Mevcut dizini goster
  clear          Ekrani temizle
  help           Bu menuyu goster
  exit           Shell'den cik

Ek Özellikler:
  | (Pipe):         Örn: ls | grep py
  > (Yönlendirme):  Örn: echo merhaba > dosya.txt
""")

def kishi_clear(args):
    print("\033[H\033[2J", end="")

BUILTINS = {
    "cd": kishi_cd,
    "pwd": kishi_pwd,
    "exit": kishi_exit,
    "help": kishi_help,
    "clear": kishi_clear,
}

def exec_with_redirect(cmd_str):
    if ">" in cmd_str:
        parts = cmd_str.split(">", 1)
        args = parts[0].split()
        dosya_adi = parts[1].strip()

        if not dosya_adi or not args:
            print("kishi: sozdizimi hatasi (syntax error near >)")
            sys.exit(1)

        try:
            fd = os.open(dosya_adi, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        except Exception as e:
            print(f"kishi: dosya acilamadi ({e})")
            sys.exit(1)

        os.dup2(fd, 1)
        os.close(fd)
    else:
        args = cmd_str.split()

    if not args:
        sys.exit(0)

    try:
        os.execvp(args[0], args)
    except FileNotFoundError:
        print(f"kishi: {args[0]}: komut bulunamadi")
        sys.exit(1)


def execute_command(cmd_str):
    cmd_str = cmd_str.strip()
    if not cmd_str:
        return

    komutlar = cmd_str.split("|")

    if len(komutlar) == 1:
        args = cmd_str.split()
        if args[0] in BUILTINS:
            BUILTINS[args[0]](args)
            return

        pid = os.fork()
        if pid == 0:
            exec_with_redirect(komutlar[0])
        else:
            os.waitpid(pid, 0)

    elif len(komutlar) == 2:
        cmd1 = komutlar[0].strip()
        cmd2 = komutlar[1].strip()

        r, w = os.pipe()

        pid1 = os.fork()
        if pid1 == 0:
            os.dup2(w, 1)
            os.close(r)
            os.close(w)
            
            exec_with_redirect(cmd1)

        pid2 = os.fork()
        if pid2 == 0:
            os.dup2(r, 0)
            os.close(w)
            os.close(r)
            
            exec_with_redirect(cmd2)

        os.close(r)
        os.close(w)

        os.waitpid(pid1, 0)
        os.waitpid(pid2, 0)

    else:
         print("kishi: Bu surumde yalnizca tek pipe (|) desteklenmektedir.")


if __name__ == "__main__":
    while True:
        try:
            girdi = input("kishi$ -> ")
            execute_command(girdi)
        except EOFError:
            print("\nkishi: gorusuruz!")
            break
        except KeyboardInterrupt:
            print()
            continue
