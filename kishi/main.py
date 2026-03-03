import os
import sys
import signal

import kishi.state as state
from kishi.builtins import BUILTINS_DICT
from kishi.ui import init_prompt_toolkit, get_prompts
from kishi.executor import process_command_line
from kishi.job_control import JobManager

def load_rc_file():
    rc_path = os.path.join(os.environ.get("HOME", "/"), ".kishirc")
    if not os.path.exists(rc_path):
        try:
            with open(rc_path, "w") as f:
                f.write("# Kishi Shell Baslangic Dosyasi\n")
                f.write("alias ll='ls -la'\n")
                f.write("alias h='history'\n")
        except: pass
        return

    try:
        with open(rc_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"): continue
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
                        import re
                        def replacer(m):
                            return os.environ.get(m.group(1), "")
                        val = re.sub(r'\$([A-Za-z0-9_]+)', replacer, val)
                        os.environ[name] = val
    except Exception as e:
        print(f"Uyarı: .kishirc okunamadı - {e}")

def main():
    state.BUILTINS = BUILTINS_DICT
    
    if len(sys.argv) > 2 and sys.argv[1] == "-c":
        state.load_system_commands()
        load_rc_file()
        process_command_line(sys.argv[2])
        sys.exit(0)
        
    def sigint_handler(sig, frame):
        pass
    signal.signal(signal.SIGINT, sigint_handler)
    try:
        signal.signal(signal.SIGTSTP, signal.SIG_IGN)
        signal.signal(signal.SIGTTOU, signal.SIG_IGN)
        signal.signal(signal.SIGTTIN, signal.SIG_IGN)
    except AttributeError:
        pass

    state.load_system_commands()
    try:
        state.KISHI_SESSION = init_prompt_toolkit()
    except Exception as e:
        print("prompt_toolkit yuklenemedi:", e)
        
    load_rc_file()
    
    print(f"{state.COLOR_AMBER}Kishi Shell Gelişmiş Sürüm (v1.6 SOLID){state.COLOR_RESET}")
    print("Yardım için 'help' yazabilirsiniz.")

    while True:
        try:
            JobManager.clean_jobs()
            
            l_prompt, r_prompt = get_prompts()
            if state.KISHI_SESSION:
                cmd_line = state.KISHI_SESSION.prompt(l_prompt, rprompt=r_prompt)
            else:
                cmd_line = input("Kishi$ -> ")
            
            if not cmd_line.strip(): continue
            
            process_command_line(cmd_line)
            
        except EOFError:
            print(f"\n{state.COLOR_AMBER}Kishi:{state.COLOR_RESET} Çıkış sinyali alındı. Hoşça kal!")
            break
        except KeyboardInterrupt:
            print()
        except Exception as e:
            print(f"{state.COLOR_RED}Kishi Panic:{state.COLOR_RESET} {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
