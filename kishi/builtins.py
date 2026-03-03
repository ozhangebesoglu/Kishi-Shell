import os
import sys
import signal
from prompt_toolkit.shortcuts import clear

from .state import COLOR_AMBER, COLOR_RED, COLOR_YELLOW, COLOR_GREEN, COLOR_RESET, COLOR_CYAN, LOCAL_VARS, ALIASES
from .job_control import JobManager

def kishi_cd(args):
    if len(args) < 2:
        hedef = os.environ.get("HOME", "/")
    else:
        hedef = args[1]
    try:
        os.chdir(hedef)
    except FileNotFoundError:
        print(f"{COLOR_RED}İşletim Sistemi Hatası:{COLOR_RESET} '{hedef}' isimli dizin bulunamadı.")
    except NotADirectoryError:
        print(f"{COLOR_RED}İşletim Sistemi Hatası:{COLOR_RESET} '{hedef}' bir dizin değil.")
    except PermissionError:
        print(f"{COLOR_RED}Erişim Reddedildi:{COLOR_RESET} '{hedef}' dizinine girmek için yetkiniz yok.")
    return 0

def kishi_pwd(args):
    print(os.getcwd())
    return 0

def kishi_exit(args):
    print(f"\n{COLOR_AMBER}Kishi:{COLOR_RESET} Güvenli şekilde çıkılıyor. Hoşça kal!")
    sys.exit(0)

def kishi_clear(args):
    clear()
    return 0

def kishi_help(args):
    print(f"""
{COLOR_AMBER}Kishi Shell Gelişmiş Sürüm (v1.6 SOLID){COLOR_RESET}

Built-in (Dahili) Komutlar:
  cd [dizin]     Dizin değiştirir
  pwd            Mevcut dizini gösterir
  history        Geçmiş komutları listeler
  clear          Ekranı temizler
  jobs           Arka plan işlemlerini gösterir
  bg / fg        İşlemleri arka plana/ön plana alır
  export         Global ortam değişkeni atar
  unset          Ortam değişkenini siler
  test / [ ]     Mantıksal kontroller yapar
  help           Bu menüyü gösterir
  exit           Shell'den çıkar

Gelişmiş Özellikler:
  | (Pipe):         Örn: ls -l | grep py | wc -l
  > / >> / 2> :     Çıktı ve Hata Yönlendirmeleri
  & (Arka Plan):    Örn: sleep 10 &
  && / || / ;       Mantıksal ve Sıralı Zincirler
  $(cmd) / `cmd`    Komut Çıktısı Yakalama
  !! / !$           Geçmiş Hızlandırıcıları
  if/for/while      Betik (Scripting) Döngüleri
  myfunc() {{...}}    Bellek içi Sub-Routines
""")
    return 0

def kishi_history(args):
    from .state import KISHI_SESSION
    if not KISHI_SESSION:
        print(f"{COLOR_YELLOW}Sistem Bilgisi:{COLOR_RESET} 'prompt_toolkit' modülü yüklü değil, geçmiş gösterilemiyor.")
        return 1
    
    strings = KISHI_SESSION.history.get_strings()
    start = max(0, len(strings) - 20)
    for i in range(start, len(strings)):
        print(f"{i+1:>5}  {strings[i]}")
    return 0


def kishi_jobs(args):
    JobManager.clean_jobs()
    for jid, job in JobManager.jobs.items() if isinstance(JobManager.jobs, dict) else enumerate(JobManager.jobs):
        if not isinstance(JobManager.jobs, dict):
            jid = job.job_id
        state = job.status
        if state == "Running" and job.is_background:
            state = "Running &"
        print(f"[{jid}]   {state:12} {job.cmd_str}")
    return 0
    
def kishi_fg(args):
    job_id = -1
    dict_mode = isinstance(JobManager.jobs, dict)
    
    if len(args) > 1:
        try: job_id = int(args[1])
        except: print("Hatalı job ids"); return 1
    else:
        if not JobManager.jobs:
            print("Arka planda iş yok")
            return 1
        job_id = max(JobManager.jobs.keys()) if dict_mode else JobManager.jobs[-1].job_id
        
    job = JobManager.jobs.get(job_id) if dict_mode else JobManager.get_job(job_id)
    if not job:
        print("İş bulunamadı")
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
                    print(f"\n{COLOR_YELLOW}[{job.job_id}]+  Durduruldu{COLOR_RESET}      {job.cmd_str}")
                    break
                else:
                    last_status = os.waitstatus_to_exitcode(status)
            except ChildProcessError:
                pass
        
        if job.status != "Stopped":
            JobManager.remove_job(job.job_id)
            
    except Exception as e:
        print("fg hatası:", e)
    finally:
        try: os.tcsetpgrp(shell_tty, old_pgrp)
        except: pass
    
    return last_status

def kishi_bg(args):
    job_id = -1
    dict_mode = isinstance(JobManager.jobs, dict)
    
    if len(args) > 1:
        try: job_id = int(args[1])
        except: print("Hatalı job ids"); return 1
    else:
        if not JobManager.jobs:
            print("Durdurulmuş iş yok")
            return 1
            
        jobs_list = sorted(JobManager.jobs.keys(), reverse=True) if dict_mode else reversed(JobManager.jobs)
        for j in jobs_list:
            tj = JobManager.jobs[j] if dict_mode else j
            if tj.status == "Stopped":
                job_id = tj.job_id
                break
        if job_id == -1:
            print("Durdurulmuş iş yok")
            return 1
            
    job = JobManager.jobs.get(job_id) if dict_mode else JobManager.get_job(job_id)
    if not job:
        print("İş bulunamadı")
        return 1
        
    if job.status == "Stopped":
        job.status = "Running"
        job.is_background = True
        print(f"[{job.job_id}]+ {job.cmd_str} &")
        os.killpg(job.pgid, signal.SIGCONT)
    else:
        print(f"Kishi: job {job_id} zaten arka planda çalışıyor")
        
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
        print("unset: parametre eksik")
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
            print("test: kosesiz parantez kapatilmamis")
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
        
    print("test: hatali argumanlar")
    return 1

# Export dictionary for main initializer
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
    "unset": kishi_unset
}
