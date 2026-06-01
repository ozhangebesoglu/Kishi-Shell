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
        
    if target == '-':
        target = os.environ.get("OLDPWD")
        if not target:
            print(f"{COLOR_RED}cd:{COLOR_RESET} OLDPWD not set.")
            return 1
        print(target)
        
    old_dir = os.getcwd()
    try:
        os.chdir(target)
        os.environ["OLDPWD"] = old_dir
        os.environ["PWD"] = os.getcwd()
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
    code = 0
    if len(args) > 1:
        try:
            code = int(args[1])
        except ValueError:
            code = 1
    # Goodbye message goes to stderr so 'exit > file' does not pollute stdout.
    print(f"\n{COLOR_AMBER}Kishi:{COLOR_RESET} Exiting safely. Goodbye!", file=sys.stderr)
    sys.exit(code)

def kishi_clear(args):
    clear()
    return 0
def kishi_help(args):
    help_text = f"""
{COLOR_AMBER}Kishi Shell Advanced (v2.0.2.0) - USER GUIDE{COLOR_RESET}

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
  export X=1           : Sets a persistent environment variable. (Ex: export PATH=/opt:$PATH)
  unset X              : Removes an assigned variable completely from memory.
  export CURSOR_SHAPE= : Set to BLOCK, UNDERLINE, BEAM, etc. in ~/.kishirc to change cursor.

[SETUP & INTEGRATION]:
  setup           : Add Kishi profile to Windows Terminal (Win) or show shell tips (Linux/Mac).
  setup --default : Set Kishi as the default Windows Terminal profile.

[PLUGIN MARKETPLACE]:
  plugin market   : Browse all available extensions in the official Github repository.
  plugin list     : Show currently installed plugins on your system.
  plugin install X: Download and install a plugin directly into Kishi Shell.
  plugin remove X : Uninstall an active plugin.

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
        except ValueError: print("Invalid job id"); return 1
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
        except Exception: pass
    
    return last_status

def kishi_bg(args):
    if sys.platform == "win32":
        print("bg: not supported on Windows")
        return 1

    job_id = -1
    
    if len(args) > 1:
        try: job_id = int(args[1])
        except ValueError: print("Invalid job id"); return 1
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
    if not set_default:
        print(f"     To set as default: setup --default")
    print(f"     Restart Windows Terminal to see the changes.")
    return 0

def kishi_plugin(args):
    plugin_dir = os.path.join(os.environ.get("HOME", "/"), ".kishi", "plugins")
    if not os.path.exists(plugin_dir):
        os.makedirs(plugin_dir, exist_ok=True)
        
    if len(args) < 2:
        print(f"{COLOR_AMBER}Kishi Plugin Manager{COLOR_RESET}")
        print("Usage:")
        print("  plugin list               : List installed plugins")
        print("  plugin market             : Browse available plugins in the official Marketplace")
        print("  plugin install <name/url> : Install a plugin by Github Username/Repo or raw URL")
        print("  plugin remove <name>      : Uninstall a plugin")
        return 1
        
    action = args[1].lower()
    
    if action == "list":
        plugins = [f for f in os.listdir(plugin_dir) if f.endswith(".py")]
        if not plugins:
            print("No plugins installed.")
        else:
            print(f"{COLOR_CYAN}[+] Installed Plugins:{COLOR_RESET}")
            for p in plugins:
                print(f"  - {p[:-3]}")
        return 0
        
    elif action == "market" or action == "search":
        import urllib.request
        import json
        from urllib.error import URLError
        
        url = "https://api.github.com/repos/ozhangebesoglu/Kishi-Plugins/contents/"
        print(f"[*] Contacting Kishi Marketplace...")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Kishi-Shell'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                plugins = [item['name'][:-3] for item in data if item['name'].endswith('.py')]
                
                if not plugins:
                    print("Marketplace is currently empty.")
                else:
                    print(f"\n{COLOR_CYAN}[+] Available Plugins in Marketplace:{COLOR_RESET}")
                    for p in plugins:
                        print(f"  📦 {p}")
                    print(f"\nTip: Use 'plugin install <name>' to download.")
                return 0
        except Exception as e:
            print(f"{COLOR_RED}[-] Failed to fetch marketplace data:{COLOR_RESET} {e}")
            return 1
            
    elif action == "install":
        if len(args) < 3:
            print("Usage: plugin install <url_or_name>")
            return 1
            
        target = args[2]
        # Resolve URLs nicely
        if target.startswith("http"):
            url = target
            name = url.split("/")[-1]
            if not name.endswith(".py"):
                name += ".py"
        else:
            name = target if target.endswith(".py") else target + ".py"
            # Central marketplace URL logic
            url = f"https://raw.githubusercontent.com/ozhangebesoglu/Kishi-Plugins/main/{name}"
            
        import urllib.request
        from urllib.error import URLError, HTTPError
        print(f"[*] Downloading '{name}' from marketplace...")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Kishi-Shell'})
            with urllib.request.urlopen(req) as response:
                code = response.read().decode('utf-8')
            
            filepath = os.path.join(plugin_dir, name)
            with open(filepath, "w") as f:
                f.write(code)
                
            print(f"{COLOR_GREEN}[+] Plugin '{name[:-3]}' installed successfully!{COLOR_RESET}")
            print(f"[*] Please run 'source ~/.kishirc' or restart Kishi to load it.")
            return 0
        except HTTPError as e:
            if e.code == 404:
                print(f"{COLOR_RED}[-] Plugin '{name}' not found in the official registry.{COLOR_RESET}")
                print(f"    Check the name or provide a direct raw URL.")
            else:
                print(f"{COLOR_RED}[-] HTTP Error: {e.code}{COLOR_RESET}")
            return 1
        except URLError as e:
            print(f"{COLOR_RED}[-] Network connection failed: {e.reason}{COLOR_RESET}")
            return 1
        except Exception as e:
            print(f"{COLOR_RED}[-] Installation failed:{COLOR_RESET} {e}")
            return 1
            
    elif action in ("remove", "uninstall", "delete"):
        if len(args) < 3:
            print("Usage: plugin remove <name>")
            return 1
            
        name = args[2] if args[2].endswith(".py") else args[2] + ".py"
        filepath = os.path.join(plugin_dir, name)
        
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"{COLOR_GREEN}[+] Plugin '{name[:-3]}' removed successfully.{COLOR_RESET}")
            return 0
        else:
            print(f"{COLOR_RED}[-] Plugin '{name[:-3]}' is not installed.{COLOR_RESET}")
            return 1
    else:
        print(f"Unknown action: {action}")
        return 1

def kishi_neofetch(args):
    import platform
    import getpass
    import socket
    
    os_name = f"{platform.system()} {platform.release()}"
    kernel = platform.machine()
    user = getpass.getuser()
    host = socket.gethostname()
    
    uptime = "Unknown"
    if os.path.exists("/proc/uptime"):
        try:
            with open("/proc/uptime", "r") as f:
                seconds = float(f.readline().split()[0])
                m, s = divmod(seconds, 60)
                h, m = divmod(m, 60)
                uptime = f"{int(h)}h {int(m)}m"
        except Exception:
            pass
            
    memory = "Unknown"
    try:
        import psutil
        mem = psutil.virtual_memory()
        memory = f"{mem.used // (1024*1024)}MiB / {mem.total // (1024*1024)}MiB"
    except ImportError:
        pass

    cpu = platform.processor() or "Unknown"
    if cpu == "Unknown" and os.path.exists("/proc/cpuinfo"):
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if line.startswith("model name"):
                        cpu = line.split(":", 1)[1].strip()
                        break
        except Exception:
            pass
    logo = [
        f"{COLOR_AMBER}  _______  _______  _______  _______  _______ {COLOR_RESET}",
        f"{COLOR_AMBER} |\\     /||\\     /||\\     /||\\     /||\\     /|{COLOR_RESET}",
        f"{COLOR_AMBER} | +---+ || +---+ || +---+ || +---+ || +---+ |{COLOR_RESET}",
        f"{COLOR_AMBER} | |   | || |   | || |   | || |   | || |   | |{COLOR_RESET}",
        f"{COLOR_AMBER} | |k  | || |i  | || |s  | || |h  | || |i  | |{COLOR_RESET}",
        f"{COLOR_AMBER} | +---+ || +---+ || +---+ || +---+ || +---+ |{COLOR_RESET}",
        f"{COLOR_AMBER} |/_____\\||/_____\\||/_____\\||/_____\\||/_____\\| {COLOR_RESET}",
        f"                                              "
    ]
    
    title = f"{COLOR_AMBER}{user}@{host}{COLOR_RESET}"
    
    info = [
        title,
        "-" * len(f"{user}@{host}"),
        f"{COLOR_CYAN}OS:{COLOR_RESET} {os_name}",
        f"{COLOR_CYAN}Kernel:{COLOR_RESET} {kernel}",
        f"{COLOR_CYAN}Uptime:{COLOR_RESET} {uptime}",
        f"{COLOR_CYAN}Shell:{COLOR_RESET} Kishi-Shell v2.0.2.0",
        f"{COLOR_CYAN}CPU:{COLOR_RESET} {cpu}",
        f"{COLOR_CYAN}Memory:{COLOR_RESET} {memory}",
    ]
    
    lines = max(len(logo), len(info))
    print()
    for i in range(lines):
        l = logo[i] if i < len(logo) else " " * 46
        r = info[i] if i < len(info) else ""
        print(f"{l}  {r}")
    print()
    return 0

def kishi_krep(args):
    """A premium, colorized 3D Semantic AI search tool (Krep) for Kishi Shell."""
    from kishi.krep import krep_search
    import sys
    import os

    # Option parser
    line_number = True
    recursive = False
    limit = 5
    pattern = None
    paths = []
    learn_mode = False
    no_model = False
    list_models = False
    purge_models = False
    update_learn = False
    auto_refresh = None  # None = unset, 0 = disable, > 0 = seconds

    # Simple CLI argument parsing
    i = 1
    while i < len(args):
        arg = args[i]
        if arg.startswith('-') and arg != '-':
            if arg in ('--help', '-h'):
                print(f"""
{COLOR_AMBER}krep — Kishi Semantic 3D Vector Search (Krep AI){COLOR_RESET}

{COLOR_CYAN}Usage:{COLOR_RESET}
  krep [OPTIONS] PATTERN [FILE...]
  cat file.txt | krep [OPTIONS] PATTERN
  krep --learn PATH...           Build a local LSA model for PATHs.
  krep --list-models             List built models.
  krep --purge-models            Delete all built models.

{COLOR_CYAN}Options:{COLOR_RESET}
  -n                  : Print line numbers (default).
  -r, -R              : Search recursively in directories.
  -l, --limit         : Max visual matches to display (default: 5).
  --learn             : Build PPMI+SVD semantic model for given PATH(s).
  --update-learn      : Tail-aware incremental update (only new lines).
  --auto-refresh I    : Set auto-refresh interval (e.g. 1h, 30m, 1d, 0=off).
                        On query, if model is older than I, a background
                        --update-learn is fired (lazy refresh, no daemon).
  --no-model          : Bypass any pre-built model; use keyword fallback.
  --list-models       : Show all cached models with age and freshness.
  --purge-models      : Delete all cached models.
  -h, --help          : Show this help guide.

{COLOR_CYAN}Examples:{COLOR_RESET}
  krep --learn /var/log/ --auto-refresh 1h
  krep "auth failure" /var/log/         # auto-uses model, refreshes lazily
  krep --update-learn /var/log/         # manual tail-only update
  krep --list-models
""")
                return 0
            elif arg == '--learn':
                learn_mode = True
            elif arg == '--update-learn':
                update_learn = True
            elif arg == '--no-model':
                no_model = True
            elif arg == '--list-models':
                list_models = True
            elif arg == '--purge-models':
                purge_models = True
            elif arg == '--auto-refresh' or arg.startswith('--auto-refresh='):
                # Hem '--auto-refresh 1h' hem '--auto-refresh=1h' formatı
                if arg.startswith('--auto-refresh='):
                    val = arg.split('=', 1)[1]
                elif i + 1 < len(args):
                    i += 1
                    val = args[i]
                else:
                    print(f"{COLOR_RED}krep: --auto-refresh requires INTERVAL "
                          f"(e.g. 1h, 30m, 1d, 0=off){COLOR_RESET}")
                    return 1
                try:
                    from kishi import krep_learn as _kl
                    auto_refresh = _kl.parse_interval(val)
                except (ImportError, ValueError) as e:
                    print(f"{COLOR_RED}krep: invalid interval '{val}': {e}{COLOR_RESET}")
                    return 1
            elif arg in ('-l', '--limit'):
                if i + 1 < len(args):
                    i += 1
                    try:
                        limit = int(args[i])
                    except ValueError:
                        print(f"{COLOR_RED}krep: Invalid limit value: {args[i]}{COLOR_RESET}")
                        return 1
                else:
                    print(f"{COLOR_RED}krep: Option -l/--limit requires an argument{COLOR_RESET}")
                    return 1
            else:
                for char in arg[1:]:
                    if char == 'n': line_number = True
                    elif char in ('r', 'R'): recursive = True
                    else:
                        print(f"{COLOR_RED}krep: Invalid option -{char}{COLOR_RESET}")
                        return 1
        else:
            if pattern is None:
                pattern = arg
            else:
                paths.append(arg)
        i += 1

    # --list-models / --purge-models / --learn early-exit
    if list_models:
        try:
            from kishi import krep_learn
        except ImportError:
            print(f"{COLOR_RED}krep --list-models requires numpy/scipy.\n"
                  f"  Install: pip install kishi-shell[krep]\n"
                  f"  Arch:    sudo pacman -S python-numpy python-scipy"
                  f"{COLOR_RESET}")
            return 1
        models = krep_learn.list_models()
        if not models:
            print(f"{COLOR_AMBER}No cached models. Build one with `krep --learn PATH`.{COLOR_RESET}")
            return 0
        import time as _time
        for m in models:
            age = _time.time() - m['build_time']
            ar = int(m.get('auto_refresh_seconds', 0))
            ar_label = (f"auto-refresh {krep_learn.format_age(ar)}"
                        if ar > 0 else "auto-refresh off")
            stale = ar > 0 and age > ar
            stale_mark = (f"{COLOR_RED}STALE{COLOR_RESET}"
                          if stale else f"{COLOR_GREEN}FRESH{COLOR_RESET}")
            print(f"{COLOR_CYAN}{m['dir']}{COLOR_RESET}")
            print(f"  size: {m['size_kb']:.1f} KB · vocab: {m['n_terms']} · "
                  f"lines: {m['n_lines']}")
            print(f"  age: {krep_learn.format_age(age)} ago · {ar_label} · "
                  f"{stale_mark}")
            print(f"  sources: {', '.join(m['source_paths'])}")
            for i_ax, lab in enumerate(m['axis_labels']):
                print(f"  axis {i_ax}: {lab}")
        return 0

    if purge_models:
        try:
            from kishi import krep_learn
        except ImportError:
            print(f"{COLOR_RED}krep --purge-models requires numpy/scipy.\n"
                  f"  Install: pip install kishi-shell[krep]"
                  f"{COLOR_RESET}")
            return 1
        n = krep_learn.purge_models()
        print(f"{COLOR_GREEN}[+] Purged {n} model(s).{COLOR_RESET}")
        return 0

    if learn_mode or update_learn:
        try:
            from kishi import krep_learn
        except ImportError:
            print(f"{COLOR_RED}krep --learn requires numpy and scipy.\n"
                  f"  Install: pip install kishi-shell[krep]\n"
                  f"  Arch:    sudo pacman -S python-numpy python-scipy\n"
                  f"  (Keyword engine works without these — try `krep PATTERN PATH`)"
                  f"{COLOR_RESET}")
            return 1
        if not krep_learn.LEARN_AVAILABLE:
            print(f"{COLOR_RED}krep --learn: numpy/scipy import failed.\n"
                  f"  Run: pip install kishi-shell[krep]"
                  f"{COLOR_RESET}")
            return 1
        # --learn / --update-learn: pattern ilk path; paths geri kalanlar
        targets = ([pattern] if pattern else []) + paths
        if not targets:
            print(f"{COLOR_RED}krep --learn: en az bir PATH gerekli.{COLOR_RESET}")
            return 1
        try:
            if update_learn:
                # Mevcut modeli yükle + tail-aware update
                existing = krep_learn.find_model_for(targets, with_state=True)
                if existing is None:
                    print(f"{COLOR_AMBER}krep --update-learn: bu paths için "
                          f"model bulunamadı. Önce --learn ile build edin.{COLOR_RESET}")
                    return 1
                # auto_refresh user override
                if auto_refresh is not None:
                    existing["auto_refresh_seconds"] = auto_refresh
                model = krep_learn.update_model(existing, targets, verbose=True)
            else:
                # Full build
                refresh_val = 0 if auto_refresh is None else auto_refresh
                model = krep_learn.build_model(
                    targets, verbose=True,
                    auto_refresh_seconds=refresh_val,
                )
            saved = krep_learn.save_model(model)
            mode_label = "updated" if update_learn else "built"
            ar = model.get("auto_refresh_seconds", 0)
            ar_label = f"auto-refresh {krep_learn.format_age(ar)}" if ar > 0 else "auto-refresh off"
            print(f"{COLOR_GREEN}[+] Model {mode_label}: {saved}{COLOR_RESET}")
            print(f"    {model['n_terms']} terms, {model['n_lines']} lines, "
                  f"{model['elapsed_s']:.1f}s · {ar_label}")
            return 0
        except RuntimeError as e:
            print(f"{COLOR_RED}krep --learn failed: {e}{COLOR_RESET}")
            return 1

    if pattern is None:
        print(f"{COLOR_RED}krep: Pattern (Query) is required. Type 'krep --help' for details.{COLOR_RESET}")
        return 1

    # --no-model: model'i geçici devre dışı bırak
    if no_model:
        import kishi.krep as _krep_mod
        _saved = _krep_mod.LEARN_AVAILABLE
        _krep_mod.LEARN_AVAILABLE = False
        try:
            return krep_search(pattern, paths, line_number=line_number,
                               recursive=recursive, limit=limit)
        finally:
            _krep_mod.LEARN_AVAILABLE = _saved

    return krep_search(pattern, paths, line_number=line_number, recursive=recursive, limit=limit)

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
    "plugin": kishi_plugin,
    "neofetch": kishi_neofetch,
    "fetch": kishi_neofetch,
    "krep": kishi_krep,
    "q": kishi_exit,
}