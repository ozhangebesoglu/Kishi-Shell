import os
import sys
import re
import signal


# ---------------------------------------------------------------------------
# Fallback — eğer Kishi kritik hata verirse /bin/bash veya /bin/sh'a düş
# ---------------------------------------------------------------------------

def _fallback_shell():
    for sh in ("/bin/bash", "/bin/sh"):
        if os.path.exists(sh):
            try:
                os.execv(sh, [sh])
            except OSError:
                continue
    sys.exit(1)


# ---------------------------------------------------------------------------
# Profile sourcing — login shell modunda environment kurulumu
# ---------------------------------------------------------------------------

def _source_profile(filepath):
    """Source a profile file: handle export, variable assignment, and comments."""
    if not os.path.isfile(filepath):
        return
    try:
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # export VAR=value veya export VAR="value"
                if line.startswith("export "):
                    line = line[7:]

                # VAR=value atamaları
                if "=" in line and not line.startswith("("):
                    name, _, val = line.partition("=")
                    name = name.strip()
                    val = val.strip().strip("'").strip('"')
                    # $VAR referanslarını genişlet
                    val = re.sub(
                        r'\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?',
                        lambda m: os.environ.get(m.group(1), ""),
                        val,
                    )
                    if name and re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name):
                        os.environ[name] = val
    except (OSError, IOError):
        pass


def _source_login_profiles():
    """Source system and user login profiles in standard order."""
    _source_profile("/etc/profile")

    home = os.environ.get("HOME", "")
    if home:
        # Standart sıralama: bash_profile > bash_login > profile
        for candidate in (".bash_profile", ".bash_login", ".profile"):
            path = os.path.join(home, candidate)
            if os.path.isfile(path):
                _source_profile(path)
                break


# ---------------------------------------------------------------------------
# RC file and plugin loading (preserved from original)
# ---------------------------------------------------------------------------

def load_rc_file():
    import kishi.state as state

    startup_cmds = []
    rc_path = os.path.join(os.environ.get("HOME", "/"), ".kishirc")
    if not os.path.exists(rc_path):
        try:
            with open(rc_path, "w") as f:
                f.write("# Kishi Shell Initialization File\n")
                f.write("alias ll='ls -la'\n")
                f.write("alias h='history'\n")
        except (OSError, IOError):
            pass
        return startup_cmds

    try:
        with open(rc_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("alias "):
                    parts = line[6:].split("=", 1)
                    if len(parts) == 2:
                        name = parts[0].strip()
                        val = parts[1].strip().strip("'").strip('"')
                        state.ALIASES[name] = val
                elif line.startswith("export "):
                    parts = line[7:].split("=", 1)
                    if len(parts) == 2:
                        name = parts[0].strip()
                        val = parts[1].strip().strip("'").strip('"')
                        val = re.sub(
                            r'\$([A-Za-z0-9_]+)',
                            lambda m: os.environ.get(m.group(1), ""),
                            val,
                        )
                        os.environ[name] = val
                else:
                    startup_cmds.append(line)
    except Exception as e:
        print(f"Warning: Could not read .kishirc - {e}", file=sys.stderr)

    return startup_cmds


def load_plugins():
    import importlib.util
    import kishi.state as state

    plugin_dir = os.path.join(os.environ.get("HOME", "/"), ".kishi", "plugins")
    if not os.path.exists(plugin_dir):
        return

    for filename in os.listdir(plugin_dir):
        if filename.endswith(".py"):
            filepath = os.path.join(plugin_dir, filename)
            module_name = "kishi.plugins." + filename[:-3]
            try:
                spec = importlib.util.spec_from_file_location(module_name, filepath)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    if hasattr(mod, "PLUGIN_COMMANDS") and isinstance(mod.PLUGIN_COMMANDS, dict):
                        expected_cmd = filename[:-3]
                        if expected_cmd in mod.PLUGIN_COMMANDS:
                            state.BUILTINS[expected_cmd] = mod.PLUGIN_COMMANDS[expected_cmd]
                        elif state.IS_INTERACTIVE:
                            print(f"{state.COLOR_YELLOW}Plugin Warning:{state.COLOR_RESET} "
                                  f"'{filename}' ignored. It must export exactly "
                                  f"'{expected_cmd}' in PLUGIN_COMMANDS.")
            except Exception as e:
                if state.IS_INTERACTIVE:
                    print(f"{state.COLOR_RED}Plugin Error:{state.COLOR_RESET} "
                          f"Failed to load {filename} - {e}")


# ---------------------------------------------------------------------------
# Signal setup
# ---------------------------------------------------------------------------

def _setup_signals():
    signal.signal(signal.SIGINT, lambda s, f: None)
    signal.signal(signal.SIGHUP, lambda s, f: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
    try:
        signal.signal(signal.SIGTSTP, signal.SIG_IGN)
        signal.signal(signal.SIGTTOU, signal.SIG_IGN)
        signal.signal(signal.SIGTTIN, signal.SIG_IGN)
    except AttributeError:
        pass


# ---------------------------------------------------------------------------
# Core startup — protected inner function
# ---------------------------------------------------------------------------

def _main_inner():
    import kishi.state as state
    from kishi.builtins import BUILTINS_DICT
    from kishi.executor import process_command_line

    state.BUILTINS.update(BUILTINS_DICT)

    # --- 1. Login shell algılama ---
    argv0 = os.path.basename(sys.argv[0])
    is_login = (argv0.startswith("-")
                or "--login" in sys.argv
                or "-l" in sys.argv)
    state.IS_LOGIN_SHELL = is_login

    # Argümanlardan flag'leri temizle
    args = [a for a in sys.argv[1:] if a not in ("--login", "-l")]

    # --- 2. --setup modu (early exit) ---
    if args and args[0] == "--setup":
        from kishi.builtins import kishi_setup
        sys.exit(kishi_setup(["setup"] + args[1:]))

    # --- 3. Signal setup ---
    _setup_signals()

    # --- 4. Profile sourcing (login modda) ---
    if is_login:
        _source_login_profiles()

    # --- 5. Temel yükleme: system commands, rc, plugins ---
    state.load_system_commands()
    startup_cmds = load_rc_file()
    load_plugins()

    # --- 6. -c modu: komutu çalıştır ve çık ---
    if len(args) >= 2 and args[0] == "-c":
        cmd = args[1]
        for sc in startup_cmds:
            process_command_line(sc)
        result = process_command_line(cmd)
        sys.exit(result or 0)

    # --- 7. Interactive mi değil mi? ---
    is_interactive = sys.stdin.isatty()
    state.IS_INTERACTIVE = is_interactive

    # --- 8. Non-interactive mod: stdin'den satır satır oku ---
    if not is_interactive:
        for sc in startup_cmds:
            process_command_line(sc)
        try:
            for line in sys.stdin:
                line = line.strip()
                if line:
                    process_command_line(line)
        except (EOFError, KeyboardInterrupt):
            pass
        sys.exit(0)

    # --- 9. Interactive mod ---
    state.IS_INTERACTIVE = True

    for sc in startup_cmds:
        process_command_line(sc)

    # prompt_toolkit yükleme (başarısız olursa düz input fallback)
    try:
        from kishi.ui import init_prompt_toolkit, get_prompts
        state.KISHI_SESSION = init_prompt_toolkit()
    except Exception as e:
        print(f"Warning: prompt_toolkit failed: {e}", file=sys.stderr)
        get_prompts = None

    from kishi.job_control import JobManager

    print(f"{state.COLOR_AMBER}Kishi Shell Advanced (v2.0.0.1){state.COLOR_RESET}")
    print("Type 'help' for the command guide.")

    while True:
        try:
            JobManager.clean_jobs()

            if state.KISHI_SESSION:
                from kishi.ui import get_prompts
                l_prompt, r_prompt = get_prompts()
                cmd_line = state.KISHI_SESSION.prompt(l_prompt, rprompt=r_prompt)
            else:
                cmd_line = input("Kishi$ -> ")

            if not cmd_line.strip():
                continue

            process_command_line(cmd_line)

        except EOFError:
            print(f"\n{state.COLOR_AMBER}Kishi:{state.COLOR_RESET} "
                  f"Exit signal received. Goodbye!")
            break
        except KeyboardInterrupt:
            print()
        except Exception as e:
            print(f"{state.COLOR_RED}Kishi Panic:{state.COLOR_RESET} {e}",
                  file=sys.stderr)


# ---------------------------------------------------------------------------
# Public entry point — tüm hataları yakalar, fallback sağlar
# ---------------------------------------------------------------------------

def main():
    try:
        _main_inner()
    except SystemExit:
        raise
    except Exception as e:
        print(f"Kishi fatal error: {e}", file=sys.stderr)
        _fallback_shell()


if __name__ == "__main__":
    main()
