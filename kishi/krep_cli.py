"""
krep — standalone CLI entry point.

`pip install kishi-shell` ile birlikte gelen `krep` komutu. Bash, zsh,
fish gibi diğer shell'lerden de doğrudan çağrılabilir; Kishi REPL'i
gerektirmez.

Örnek:
    $ krep "auth failure" /var/log/
    $ krep --learn /var/log/ --auto-refresh 1h
    $ krep --list-models
    $ cat app.log | krep error

İçinde Kishi'nin kishi_krep builtin'ini yeniden kullanır — argv geçirir.
"""
import sys


def main():
    """Bash'tan çağrıldığında entry: krep komut + args."""
    from kishi.builtins import kishi_krep
    # kishi_krep argv[0] olarak "krep" bekler (kendi CLI parser'ı için)
    rc = kishi_krep(["krep"] + sys.argv[1:])
    sys.exit(rc if rc is not None else 0)


if __name__ == "__main__":
    main()
