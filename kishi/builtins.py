import os
import sys
import signal
from prompt_toolkit.shortcuts import clear

from .state import COLOR_AMBER, COLOR_RED, COLOR_YELLOW, COLOR_GREEN, COLOR_RESET, COLOR_CYAN, LOCAL_VARS, ALIASES
from .job_control import JobManager
try:
    from .tui_dashboard import kishi_dashboard
except ImportError:
    kishi_dashboard = None

try:
    from .tui_explorer import kishi_explore
except ImportError:
    kishi_explore = None

def kishi_cd(args):
    if len(args) < 2:
        target = os.environ.get("HOME", "/")
    else:
        target = args[1]
    try:
        os.chdir(target)
        return 0
    except FileNotFoundError:
        print(f"{COLOR_RED}OS Error:{COLOR_RESET} Directory '{target}' not found.")
        return 1
    except NotADirectoryError:
        print(f"{COLOR_RED}OS Error:{COLOR_RESET} '{target}' is not a directory.")
        return 1
    except PermissionError:
        print(f"{COLOR_RED}Access Denied:{COLOR_RESET} No permission to enter '{target}'.")
        return 1

def kishi_pwd(args):
    print(os.getcwd())
    return 0

def kishi_exit(args):
    print(f"\n{COLOR_AMBER}Kishi:{COLOR_RESET} Exiting safely. Goodbye!")
    sys.exit(0)

def kishi_clear(args):
    clear()
    return 0
def kishi_help(args):
    help_text = f"""
{COLOR_AMBER}Kishi Shell Advanced (v1.9.7) - USER GUIDE{COLOR_RESET}

[BASIC COMMANDS]:
  cd <dir>       : Changes the directory. (Ex: cd /home, cd ..)
  pwd            : Prints the absolute path of the current directory.
  clear          : Clears the terminal screen. (Shortcut: Ctrl + L)
  exit / q       : Exits Kishi Shell.

[ADVANCED TUI INTERFACES]:
  explore        : Opens the dual-pane IDE File Explorer.
                   You can navigate folders and edit code directly in the right pane.
  dashboard      : Opens the full-screen System Monitor (CPU/RAM/GPU/Net/Disk).

[SPECIAL SHORTCUTS]:
  [Ctrl + R]     : Fuzzy Search History. Find old commands by typing to filter.
  [Ctrl + E]     : Instantly opens the 'explore' File Explorer GUI.
  [Ctrl + L]     : Clears the screen.
  [Tab / Esc]    : Switches focus between the Directory Tree and the Editor pane.
  [Ctrl + S]     : Saves your text file while inside the Explorer IDE.

[ENVIRONMENT & SCRIPTING]:
  export X=1     : Sets a persistent environment variable. (Ex: export PATH=/opt:$PATH)
  unset X        : Removes an assigned variable completely from memory.

[SETUP & INTEGRATION]:
  setup           : Add Kishi profile to Windows Terminal (Win) or show shell tips (Linux/Mac).
  setup --default : Set Kishi as the default Windows Terminal profile.

[CUSTOM FUNCTIONS (myfunc)]:
  Create custom sub-routines for repetitive tasks:
  Example: 
    Kishi$ -> hello() {{ echo "Welcome to the system $USER"; ls -l; }}
    Kishi$ -> hello
    Welcome to the system ozhangebesoglu
    (lists the files in the directory)
"""
    if len(args) > 1 and args[1] == "less":
        print(f"{COLOR_AMBER}SHORTCUTS:{COLOR_RESET} Ctrl+R (Fuzzy Search), Ctrl+E (Explorer) | {COLOR_CYAN}COMMANDS:{COLOR_RESET} dashboard, explore, export X=y, func() {{}}")
    else:
        print(help_text)
    return 0

def kishi_history(args):
    from .state import KISHI_SESSION
    if not KISHI_SESSION:
        print(f"{COLOR_YELLOW}System Info:{COLOR_RESET} 'prompt_toolkit' is not installed, history is unavailable.")
        return 1
    
    strings = KISHI_SESSION.history.get_strings()
    start = max(0, len(strings) - 20)
    for i in range(start, len(strings)):
        print(f"{i+1:>5}  {strings[i]}")
    return 0


def kishi_jobs(args):
    JobManager.clean_jobs()
    for job in JobManager.jobs:
        status = job.status
        if status == "Running" and job.is_background:
            status = "Running &"
        print(f"[{job.job_id}]   {status:12} {job.cmd_str}")
    return 0
    
def kishi_fg(args):
    if sys.platform == "win32":
        print("fg: not supported on Windows")
        return 1

    job_id = -1
    
    if len(args) > 1:
        try: job_id = int(args[1])
        except: print("Invalid job id"); return 1
    else:
        if not JobManager.jobs:
            print("No jobs in background")
            return 1
        job_id = JobManager.jobs[-1].job_id
        
    job = JobManager.get_job(job_id)
    if not job:
        print("Job not found")
        return 1
        
    print(f"{job.cmd_str}")
    shell_tty = -1
    old_pgrp = -1
    try:
        import termios
        shell_tty = sys.stdin.fileno()
        old_pgrp = os.tcgetpgrp(shell_tty)
    except ImportError:
        pass
    
    try:
        os.tcsetpgrp(shell_tty, job.pgid)
        if job.status == "Stopped":
            os.killpg(job.pgid, signal.SIGCONT)
            
        job.status = "Running"
        job.is_background = False
        
        last_status = 0
        for p in job.pids:
            try:
                pid, status = os.waitpid(p, os.WUNTRACED)
                if os.WIFSTOPPED(status):
                    job.status = "Stopped"
                    job.is_background = True
                    print(f"\n{COLOR_YELLOW}[{job.job_id}]+  Stopped{COLOR_RESET}      {job.cmd_str}")
                    break
                else:
                    last_status = os.waitstatus_to_exitcode(status)
            except ChildProcessError:
                pass
        
        if job.status != "Stopped":
            JobManager.remove_job(job.job_id)
            
    except Exception as e:
        print("fg error:", e)
    finally:
        try: os.tcsetpgrp(shell_tty, old_pgrp)
        except: pass
    
    return last_status

def kishi_bg(args):
    if sys.platform == "win32":
        print("bg: not supported on Windows")
        return 1

    job_id = -1
    
    if len(args) > 1:
        try: job_id = int(args[1])
        except: print("Invalid job id"); return 1
    else:
        if not JobManager.jobs:
            print("No stopped jobs")
            return 1
            
        for j in reversed(JobManager.jobs):
            if j.status == "Stopped":
                job_id = j.job_id
                break
        if job_id == -1:
            print("No stopped jobs")
            return 1
            
    job = JobManager.get_job(job_id)
    if not job:
        print("Job not found")
        return 1
        
    if job.status == "Stopped":
        job.status = "Running"
        job.is_background = True
        print(f"[{job.job_id}]+ {job.cmd_str} &")
        os.killpg(job.pgid, signal.SIGCONT)
    else:
        print(f"Kishi: job {job_id} is already in background")
        
    return 0

def kishi_export(args):
    if len(args) < 2:
        for k, v in os.environ.items():
            print(f"export {k}='{v}'")
        return 0
    
    for arg in args[1:]:
        if '=' in arg:
            key, val = arg.split('=', 1)
            import re
            def replacer(m):
                return os.environ.get(m.group(1), "")
            val = re.sub(r'\$([A-Za-z0-9_]+)', replacer, val)
            os.environ[key] = val
            if key in LOCAL_VARS:
                del LOCAL_VARS[key]
        else:
            if arg in LOCAL_VARS:
                os.environ[arg] = LOCAL_VARS[arg]
                del LOCAL_VARS[arg]
    return 0

def kishi_unset(args):
    if len(args) < 2:
        print("unset: missing parameter")
        return 1
        
    for arg in args[1:]:
        if arg in os.environ:
            del os.environ[arg]
        if arg in LOCAL_VARS:
            del LOCAL_VARS[arg]
    return 0

def kishi_test(args):
    if not args: return 1
    
    if args[0] == '[':
        if args[-1] == ']':
            args = args[1:-1]
        else:
            print("test: missing closing bracket")
            return 1
    elif args[0] == 'test':
        args = args[1:]
        
    if not args: return 1
    
    if len(args) == 3:
        if args[1] in ('==', '='): return 0 if args[0] == args[2] else 1
        if args[1] == '!=': return 0 if args[0] != args[2] else 1
        
        try:
            val1 = float(args[0])
            val2 = float(args[2])
            if args[1] == '-eq': return 0 if val1 == val2 else 1
            if args[1] == '-ne': return 0 if val1 != val2 else 1
            if args[1] == '-gt': return 0 if val1 > val2 else 1
            if args[1] == '-ge': return 0 if val1 >= val2 else 1
            if args[1] == '-lt': return 0 if val1 < val2 else 1
            if args[1] == '-le': return 0 if val1 <= val2 else 1
        except ValueError:
            pass
            
    if len(args) == 2:
        op, val = args[0], args[1]
        if op == '-f': return 0 if os.path.isfile(val) else 1
        if op == '-d': return 0 if os.path.isdir(val) else 1
        if op == '-z': return 0 if not val else 1
        if op == '-n': return 0 if val else 1
        
    if len(args) == 1:
        return 0 if args[0] else 1
        
    print("test: invalid arguments")
    return 1

def kishi_deactivate(args):
    if "VIRTUAL_ENV" in os.environ:
        bin_dir = "Scripts" if sys.platform == "win32" else "bin"
        venv_bin = os.path.join(os.environ["VIRTUAL_ENV"], bin_dir)
        if "PATH" in os.environ:
            path_list = os.environ["PATH"].split(os.pathsep)
            if venv_bin in path_list:
                path_list.remove(venv_bin)
                os.environ["PATH"] = os.pathsep.join(path_list)
        
        if "_OLD_VIRTUAL_PATH" in os.environ:
            os.environ["PATH"] = os.environ["_OLD_VIRTUAL_PATH"]
            del os.environ["_OLD_VIRTUAL_PATH"]
            
        del os.environ["VIRTUAL_ENV"]
        print(f"{COLOR_GREEN}Virtual environment deactivated.{COLOR_RESET}")
    else:
        print("No virtual environment (venv) is active.")
    return 0

def kishi_source(args):
    if len(args) < 2:
        print("source: filename required (Ex: source venv/bin/activate)")
        return 1
        
    raw_path = args[1].strip().strip("'").strip('"')
    
    # Try multiple path resolutions
    path_candidates = [
        raw_path,
        os.path.expanduser(raw_path),
        os.path.abspath(os.path.expanduser(raw_path)),
        os.path.join(os.getcwd(), raw_path)
    ]
    
    script_path = None
    for p in path_candidates:
        if os.path.exists(p):
            script_path = p
            break
            
    if not script_path:
        print(f"{COLOR_RED}source error:{COLOR_RESET} '{raw_path}' not found.")
        return 1
        
    try:
        import subprocess
        if sys.platform == "win32":
            print(f"{COLOR_YELLOW}Warning:{COLOR_RESET} 'source' is not fully supported on Windows.")
            print("  Use 'python -m venv <dir>' and activate manually.")
            return 1

        env_cmd = f"source {__import__('shlex').quote(script_path)} && env && echo '---KISHI_SEP---' && alias"
        result = subprocess.run(['bash', '-c', env_cmd], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"{COLOR_RED}KS source error:{COLOR_RESET} Failed to process bash script.")
            return result.returncode
            
        parts = result.stdout.split('---KISHI_SEP---')
        env_output = parts[0]
        alias_output = parts[1] if len(parts) > 1 else ""
        
        for line in env_output.splitlines():
            line = line.strip()
            if not line: continue
            if '=' in line:
                key, val = line.split('=', 1)
                # Import into Kishi environment
                os.environ[key] = val
                
        for line in alias_output.splitlines():
            line = line.strip()
            if line.startswith("alias "):
                line = line[6:]
                if '=' in line:
                    k, v = line.split('=', 1)
                    ALIASES[k] = v.strip("'").strip('"')
                    
        print(f"{COLOR_CYAN}[+]{COLOR_RESET} '{script_path}' successfully loaded into Kishi environment.")
    except Exception as e:
        print(f"{COLOR_RED}system error in source:{COLOR_RESET} {e}")
        return 1
    return 0

def _setup_linux(args):
    import shutil
    import subprocess

    kishi_path = shutil.which("kishi")
    if not kishi_path:
        print(f"{COLOR_RED}Error:{COLOR_RESET} 'kishi' not found in PATH.")
        print("  Install first: pip install kishi-shell")
        return 1

    set_default = "--default" in args

    shells_file = "/etc/shells"
    registered = False
    try:
        with open(shells_file, "r") as f:
            registered = kishi_path in f.read().splitlines()
    except FileNotFoundError:
        pass

    if not registered:
        print(f"  Kishi path: {kishi_path}")
        print(f"  Adding to {shells_file} (requires sudo)...")
        try:
            result = subprocess.run(
                ["sudo", "tee", "-a", shells_file],
                input=f"{kishi_path}\n",
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"  {COLOR_GREEN}[OK]{COLOR_RESET} Registered in {shells_file}")
            else:
                print(f"  {COLOR_RED}[!]{COLOR_RESET} Failed. You can do it manually:")
                print(f"    echo '{kishi_path}' | sudo tee -a {shells_file}")
                if not set_default:
                    return 1
        except Exception as e:
            print(f"  {COLOR_RED}Error:{COLOR_RESET} {e}")
            print(f"    echo '{kishi_path}' | sudo tee -a {shells_file}")
            if not set_default:
                return 1
    else:
        print(f"  {COLOR_GREEN}[OK]{COLOR_RESET} Already registered in {shells_file}")

    if set_default:
        print(f"\n  Setting default shell to {kishi_path}...")
        try:
            result = subprocess.run(["chsh", "-s", kishi_path], text=True)
            if result.returncode == 0:
                print(f"  {COLOR_GREEN}[OK]{COLOR_RESET} Default shell changed. Log out and back in to apply.")
            else:
                print(f"  {COLOR_RED}[!]{COLOR_RESET} chsh failed. Try manually:")
                print(f"    chsh -s {kishi_path}")
        except Exception as e:
            print(f"  {COLOR_RED}Error:{COLOR_RESET} {e}")
            return 1
    else:
        print(f"\n  {COLOR_AMBER}Available actions:{COLOR_RESET}")
        print(f"    setup --default    Set Kishi as your login shell")
        print(f"    Or manually:       chsh -s {kishi_path}")
        print(f"\n  To launch on terminal start without changing login shell:")
        print(f"    echo 'exec kishi' >> ~/.bashrc")

    return 0

def kishi_setup(args):
    if sys.platform != "win32":
        return _setup_linux(args)

    import json

    wt_paths = []
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        wt_paths.append(os.path.join(local, "Packages", "Microsoft.WindowsTerminal_8wekyb3d8bbwe", "LocalState", "settings.json"))
        wt_paths.append(os.path.join(local, "Microsoft", "Windows Terminal", "settings.json"))

    settings_path = None
    for p in wt_paths:
        if os.path.isfile(p):
            settings_path = p
            break

    if not settings_path:
        print(f"{COLOR_YELLOW}Windows Terminal settings not found.{COLOR_RESET}")
        print("  Make sure Windows Terminal is installed.")
        print(f"\n  You can still use Kishi in any terminal:")
        print(f"    python -m kishi")
        return 1

    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            raw = f.read()

        lines = []
        for line in raw.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("//"):
                continue
            lines.append(line)
        clean_json = "\n".join(lines)
        settings = json.loads(clean_json)
    except Exception as e:
        print(f"{COLOR_RED}Error reading settings:{COLOR_RESET} {e}")
        return 1

    profiles = settings.get("profiles", {})
    profile_list = profiles.get("list", [])

    KISHI_GUID = "{e1b5e1a0-k1sh-1sh3-ll00-000000000001}"

    for p in profile_list:
        if p.get("guid") == KISHI_GUID or p.get("name") == "Kishi Shell":
            print(f"{COLOR_GREEN}Kishi Shell profile already exists in Windows Terminal.{COLOR_RESET}")
            return 0

    kishi_profile = {
        "guid": KISHI_GUID,
        "name": "Kishi Shell",
        "commandline": "python -m kishi",
        "startingDirectory": "%USERPROFILE%",
        "colorScheme": "One Half Dark",
        "cursorShape": "filledBox",
        "hidden": False
    }

    profile_list.insert(0, kishi_profile)
    profiles["list"] = profile_list
    settings["profiles"] = profiles

    set_default = len(args) > 1 and args[1] == "--default"
    if set_default:
        settings["defaultProfile"] = KISHI_GUID

    try:
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"{COLOR_RED}Error writing settings:{COLOR_RESET} {e}")
        return 1

    print(f"{COLOR_GREEN}[OK]{COLOR_RESET} Kishi Shell profile added to Windows Terminal.")
    if set_default:
        print(f"     Kishi is now the default profile.")
    else:
        print(f"     To set as default: setup --default")
    print(f"     Restart Windows Terminal to see the changes.")
    return 0

BUILTINS_DICT = {
    "[": kishi_test,
    "test": kishi_test,
    "cd": kishi_cd,
    "pwd": kishi_pwd,
    "exit": kishi_exit,
    "clear": kishi_clear,
    "history": kishi_history,
    "h": kishi_history,
    "help": kishi_help,
    "jobs": kishi_jobs,
    "fg": kishi_fg,
    "bg": kishi_bg,
    "export": kishi_export,
    "unset": kishi_unset,
    "source": kishi_source,
    ".": kishi_source,
    "deactivate": kishi_deactivate,
    "dashboard": kishi_dashboard,
    "explore": kishi_explore,
    "setup": kishi_setup,
    "q": kishi_exit,
}