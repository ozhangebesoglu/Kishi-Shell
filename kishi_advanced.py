#!/usr/bin/env python3
"""
Kishi Shell - Gelişmiş Sürüm (v1.0)
Özellikler:
- Özel Sağ Hizalı ve Renkli Prompt (Amber)
- Çoklu Pipe (|) Desteği
- Yönlendirme (<, >) Desteği
- Arka Plan İşlemleri (&)
- Mantıksal Operatörler (&&, ||)
- Readline ile Geçmiş (Ctrl+R, Yön Tuşları) ve Tab Tamamlama
- Kurumsal Türkçe Hatalar & difflib ile Zeki Öneriler ("Şunu mu demek istediniz?")
- ~/.kishirc Yapılandırma Dosyası
"""

import os
import sys
import glob
import shlex
import difflib

# prompt_toolkit nesneleri
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.completion import Completer, Completion

KISHI_SESSION = None

# ==================== YARDIMCI VE SABİTLER ====================
COLOR_AMBER = "\033[38;2;255;191;0m"
COLOR_RESET = "\033[0m"
COLOR_RED   = "\033[1;31m"
COLOR_GREEN = "\033[1;32m"
COLOR_CYAN  = "\033[1;36m"
COLOR_YELLOW= "\033[1;33m"

ALIASES = {}
FUNCTIONS = {}
LOCAL_VARS = {}
SYSTEM_COMMANDS = []

def load_system_commands():
    """Çalıştırılabilir sistem komutlarını belleğe yükler"""
    global SYSTEM_COMMANDS
    paths = os.environ.get("PATH", "/bin:/usr/bin").split(os.pathsep)
    cmds = set()
    for p in paths:
        if os.path.exists(p) and os.path.isdir(p):
            for f in os.listdir(p):
                filepath = os.path.join(p, f)
                if os.path.isfile(filepath) and os.access(filepath, os.X_OK):
                    cmds.add(f)
    SYSTEM_COMMANDS = list(cmds)

def get_close_match_suggestion(cmd_name):
    """Bilinmeyen komutlar için öneri bulur"""
    if not SYSTEM_COMMANDS:
        return ""
    matches = difflib.get_close_matches(cmd_name, SYSTEM_COMMANDS, n=1, cutoff=0.6)
    if matches:
        return f"\nŞunu mu demek istediniz: {COLOR_CYAN}'{matches[0]}'{COLOR_RESET} ?"
    return ""

class KishiCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        words = text.split()
        is_first_word = (not text) or (len(words) == 1 and not text.endswith(" ")) or (len(words) == 0)
        
        import re
        word_before_cursor = document.get_word_before_cursor(pattern=re.compile(r'[^\s]+'))
        target_dir = os.path.dirname(word_before_cursor) or "."
        base_name = os.path.basename(word_before_cursor)
        
        # Dosya/Dizin Önerileri
        try:
            for f in os.listdir(target_dir):
                if f.lower().startswith(base_name.lower()):
                    full_path = os.path.join(target_dir, f) if target_dir != "." else f
                    if os.path.isdir(os.path.join(target_dir, f)):
                        yield Completion(full_path + '/', start_position=-len(base_name))
                    else:
                        yield Completion(full_path, start_position=-len(base_name))
        except:
            pass

        # Sistem Komutu ve Builtin Önerileri
        if is_first_word:
            text_lower = word_before_cursor.lower()
            if not '/' in word_before_cursor and word_before_cursor.strip() != "":
                for c in SYSTEM_COMMANDS:
                    if c.lower().startswith(text_lower):
                        yield Completion(c, start_position=-len(word_before_cursor))
            for b in BUILTINS.keys():
                if b.lower().startswith(text_lower):
                    yield Completion(b, start_position=-len(word_before_cursor))

from prompt_toolkit.lexers import Lexer
from prompt_toolkit.styles import Style

kishi_style = Style.from_dict({
    'command.valid': 'ansigreen bold',
    'command.invalid': 'ansired bold',
    'string': 'ansiyellow',
    'variable': 'ansicyan',
    'operator': 'ansimagenta',
    'path.invalid': 'ansired underline',
    'bottom-toolbar': 'reverse'
})

class KishiLexer(Lexer):
    def lex_document(self, document):
        def get_line(lineno):
            line = document.lines[lineno]
            if not line:
                return []
            
            result = []
            words = line.split(' ') # Boşluklara göre basit ayrıştırma
            
            for i, word in enumerate(words):
                if i > 0:
                    result.append(('', ' '))
                
                if not word:
                    continue
                    
                if word.startswith('"') or word.startswith("'") or word.endswith('"') or word.endswith("'"):
                    result.append(('class:string', word))
                elif word.startswith('$'):
                    result.append(('class:variable', word))
                elif word in ('|', '&&', '||', '>', '<', '>>', '2>', '2>>', '2>&1', '&', ';'):
                    result.append(('class:operator', word))
                elif word in ('if', 'then', 'elif', 'else', 'fi', 'for', 'while', 'in', 'do', 'done', '[', ']', '{', '}'):
                    result.append(('class:command.valid', word))
                elif i == 0 or (i > 0 and words[i-1] in ('|', '&&', '||', ';', 'then', 'do', 'else', 'elif')):
                    # Komut ise (Geçerli / Geçersiz)
                    clean_word = word.strip()
                    if clean_word in BUILTINS or clean_word in SYSTEM_COMMANDS or clean_word in ALIASES:
                        result.append(('class:command.valid', word))
                    elif os.path.exists(clean_word) or clean_word.startswith("./") or clean_word.startswith("~/"):
                        result.append(('class:command.valid', word))
                    elif '/' in clean_word:
                        result.append(('class:path.invalid', word))
                    else:
                        result.append(('class:command.invalid', word))
                else:
                    # Argüman ve Path Kontrolü
                    if '/' in word and not os.path.exists(os.path.expanduser(word)):
                        result.append(('class:path.invalid', word))
                    else:
                        result.append(('', word))
                    
            return result
        return get_line

from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.application import get_app
from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.shortcuts import clear
import subprocess

kishi_bindings = KeyBindings()

@kishi_bindings.add('c-l')
def _(event):
    " Ekranı düzgün bir şekilde temizler ve prompt'u korur. "
    import sys
    sys.stdout.write('\033[2J\033[3J\033[H')
    sys.stdout.flush()
    event.app.renderer.clear()
    event.app.invalidate()

@kishi_bindings.add('c-r')
def _(event):
    " fzf ile geçmiş araması "
    history_file = os.path.join(os.environ.get("HOME", "/"), ".kishi_history")
    if not os.path.exists(history_file):
        return
        
    def run_fzf():
        try:
            with open(history_file, 'r') as f:
                lines = f.readlines()
            
            unique_lines = list(dict.fromkeys(reversed([l.strip() for l in lines if l.strip()])))
            
            process = subprocess.Popen(
                ['fzf', '--height=40%', '--reverse', '--prompt=History> '],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=open(os.devnull, 'w'),
                text=True
            )
            stdout, _ = process.communicate("\n".join(unique_lines))
            
            if process.returncode == 0 and stdout:
                selected = stdout.strip()
                event.app.current_buffer.text = selected
                event.app.current_buffer.cursor_position = len(selected)
        except Exception:
            pass
            
    run_in_terminal(run_fzf)

def get_bottom_toolbar():
    doc = get_app().current_buffer.document
    text = doc.text_before_cursor
    words = text.split()
    if not words: return ""
    
    cmd = words[0].strip()
    if cmd == 'export': return [('class:bottom-toolbar', " Usage: export VAR=value ")]
    if cmd == 'unset':  return [('class:bottom-toolbar', " Usage: unset VAR ")]
    if cmd in BUILTINS:  return [('class:bottom-toolbar', f" Dahili Komut: {cmd} ")]
    if cmd in ALIASES:   return [('class:bottom-toolbar', f" Alias: {ALIASES[cmd]} ")]
    if cmd in FUNCTIONS: return [('class:bottom-toolbar', f" Sub-Routine: {cmd} ")]
    
    if len(words) > 0 and text.endswith(" "):
        return [('class:bottom-toolbar', " " + text)]
    return ""

def init_prompt_toolkit():
    global KISHI_SESSION
    histfile = os.path.join(os.environ.get("HOME", "/"), ".kishi_history")
    KISHI_SESSION = PromptSession(
        history=FileHistory(histfile),
        auto_suggest=AutoSuggestFromHistory(),
        completer=KishiCompleter(),
        lexer=KishiLexer(),
        style=kishi_style,
        bottom_toolbar=get_bottom_toolbar,
        key_bindings=kishi_bindings
    )

def load_rc_file():
    rc_path = os.path.join(os.environ.get("HOME", "/"), ".kishirc")
    if not os.path.exists(rc_path):
        try:
            with open(rc_path, "w") as f:
                f.write("# Kishi Shell Baslangic Dosyasi\n")
                f.write("alias ll='ls -la'\n")
                f.write("alias h='history'\n")
        except Exception:
            pass
        return

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
                        ALIASES[name] = val
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

# ==================== BUILT-IN KOMUTLAR ====================
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
    return 0 # Başarılı (veya hata mesajı verildi)

def kishi_pwd(args):
    print(os.getcwd())
    return 0

def kishi_exit(args):
    print(f"\n{COLOR_AMBER}Kishi:{COLOR_RESET} Güvenli şekilde çıkılıyor. Hoşça kal!")
    sys.exit(0)

def kishi_clear(args):
    print("\033[H\033[2J", end="")
    return 0

def kishi_help(args):
    print(f"""
{COLOR_AMBER}Kishi Shell Gelişmiş Sürüm (v1.5){COLOR_RESET}

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
    if not readline:
        print(f"{COLOR_YELLOW}Sistem Bilgisi:{COLOR_RESET} 'readline' modülü yüklü değil, geçmiş gösterilemiyor.")
        return 1
    
    length = readline.get_current_history_length()
    start = max(1, length - 20)
    for i in range(start, length + 1):
        item = readline.get_history_item(i)
        if item:
             print(f"{i:>5}  {item}")
    return 0

# ==================== JOB CONTROL (SÜREÇ YÖNETİMİ) ====================

class Job:
    def __init__(self, job_id, pids, cmd_str, is_background):
        self.job_id = job_id
        self.pids = pids # Pipeline içindeki PID listesi
        self.pgid = pids[0] if pids else 0 # İlk süreç Process Group Leader olur
        self.cmd_str = cmd_str
        self.status = "Running" # veya "Stopped"
        self.is_background = is_background

class JobManager:
    jobs = {}
    next_job_id = 1
    
    @classmethod
    def add_job(cls, pids, cmd_str, is_background):
        job = Job(cls.next_job_id, pids, cmd_str, is_background)
        cls.jobs[cls.next_job_id] = job
        if is_background:
            print(f"{COLOR_YELLOW}[{cls.next_job_id}] {job.pgid}{COLOR_RESET}  {cmd_str}", file=sys.stderr)
        cls.next_job_id += 1
        return job

    @classmethod
    def remove_job(cls, job_id):
        if job_id in cls.jobs:
            del cls.jobs[job_id]
            
    @classmethod
    def get_job_by_pgid(cls, pgid):
        for j in cls.jobs.values():
            if j.pgid == pgid:
                return j
        return None

    @classmethod
    def clean_jobs(cls):
        """Çalışmayı bitiren (Zombi olan) arka plan işlerini temizler"""
        import os, signal
        # Sadece non-blocking bekleme (WNOHANG | WUNTRACED)
        completed_pgids = []
        for job_id, job in list(cls.jobs.items()):
            try:
                # Arkaplandaki gruptan herhangi bir process bittiyse (veya hepsi)
                all_done = True
                for p in job.pids:
                    # check if process still alive:
                    try:
                        pid, status = os.waitpid(p, os.WNOHANG | os.WUNTRACED)
                        if pid == 0:
                            all_done = False # hala çalışıyor
                        elif os.WIFSTOPPED(status):
                            job.status = "Stopped"
                            all_done = False
                        elif os.WIFEXITED(status) or os.WIFSIGNALED(status):
                            pass # bu süreç bitmiş
                    except ChildProcessError:
                        pass # Çoktan ölmüş Wait edilmiş
                if all_done:
                    if job.is_background:
                        print(f"\n{COLOR_GREEN}[{job.job_id}]+  Bitti{COLOR_RESET}           {job.cmd_str}")
                    completed_pgids.append(job_id)
            except Exception:
                pass
                
        for jid in completed_pgids:
            cls.remove_job(jid)


def kishi_jobs(args):
    JobManager.clean_jobs()
    for jid, job in JobManager.jobs.items():
        state = job.status
        if state == "Running" and job.is_background:
            state = "Running &"
        print(f"[{jid}]   {state:12} {job.cmd_str}")
    return 0
    
def kishi_fg(args):
    job_id = -1
    if len(args) > 1:
        try: job_id = int(args[1])
        except: print("Hatalı job ids"); return 1
    else:
        # Son eklenen iş
        if not JobManager.jobs:
            print("Arka planda iş yok")
            return 1
        job_id = max(JobManager.jobs.keys())
        
    job = JobManager.jobs.get(job_id)
    if not job:
        print("İş bulunamadı")
        return 1
        
    print(f"{job.cmd_str}")
    # Terminal kontrolünü o gruba ver
    import termios
    shell_tty = sys.stdin.fileno()
    old_pgrp = os.tcgetpgrp(shell_tty)
    
    try:
        os.tcsetpgrp(shell_tty, job.pgid)
        # Eğer Stopped ise çalıştır
        if job.status == "Stopped":
            os.killpg(job.pgid, signal.SIGCONT)
            
        job.status = "Running"
        job.is_background = False
        
        # Bekle
        last_status = 0
        for p in job.pids:
            pid, status = os.waitpid(p, os.WUNTRACED)
            if os.WIFSTOPPED(status):
                job.status = "Stopped"
                job.is_background = True
                print(f"\n{COLOR_YELLOW}[{job.job_id}]+  Durduruldu{COLOR_RESET}      {job.cmd_str}")
                break
            else:
                last_status = os.waitstatus_to_exitcode(status)
        
        if job.status != "Stopped":
            JobManager.remove_job(job.job_id)
            
    except Exception as e:
        print("fg hatası:", e)
    finally:
        # Terminal kontrolünü geri al
        os.tcsetpgrp(shell_tty, old_pgrp)
    
    return last_status

def kishi_bg(args):
    job_id = -1
    if len(args) > 1:
        try: job_id = int(args[1])
        except: print("Hatalı job ids"); return 1
    else:
        if not JobManager.jobs:
            print("Durdurulmuş iş yok")
            return 1
        # Son durdurulan isleri tarayalim
        for j in sorted(JobManager.jobs.keys(), reverse=True):
            if JobManager.jobs[j].status == "Stopped":
                job_id = j
                break
        if job_id == -1:
            print("Durdurulmuş iş yok")
            return 1
            
    job = JobManager.jobs.get(job_id)
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
    """Ortam değişkeni ayarlar veya global'e taşır. Örn: export VAR=deger"""
    if len(args) < 2:
        for k, v in os.environ.items():
            print(f"export {k}='{v}'")
        return 0
    
    for arg in args[1:]:
        if '=' in arg:
            key, val = arg.split('=', 1)
            os.environ[key] = val
            if key in LOCAL_VARS:
                del LOCAL_VARS[key]
        else:
            if arg in LOCAL_VARS:
                os.environ[arg] = LOCAL_VARS[arg]
                del LOCAL_VARS[arg]
    return 0

def kishi_unset(args):
    """Ortam değişkeni siliyor. Örn: unset VAR"""
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
    """If conditionlari ve manitksal testler icin [ condition ] veya test condition built-in'i"""
    if not args: return 1
    
    # Kosesiz parantez silimi
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
        
        # Sayisal Karsilastirmalar
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
            pass # Not numbers, fallback
            
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

BUILTINS = {
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

# ==================== EXECUTION (SİSTEM ÇAĞRILARI) ====================

# ==================== PROCESS EXECUTION ====================
# ==================== ENGINE 2.0: LEXER, PARSER & EXPANDER ====================

class ASTNode:
    pass

class CommandNode(ASTNode):
    def __init__(self):
        self.args = []
        self.in_file = None
        self.out_file = None
        self.out_append = False
        self.err_file = None
        self.err_append = False
        self.err_to_out = False
        
class PipelineNode(ASTNode):
    def __init__(self):
        self.commands = [] # List of CommandNode
        self.is_background = False

class LogicNode(ASTNode):
    def __init__(self, left, operator, right):
        self.left = left # PipelineNode veya LogicNode
        self.operator = operator # '&&' veya '||'
        self.right = right

class SequenceNode(ASTNode):
    def __init__(self):
        self.statements = [] # List of ASTNodes

class IfNode(ASTNode):
    def __init__(self, condition_ast, then_ast, elifs, else_ast):
        self.condition_ast = condition_ast
        self.then_ast = then_ast
        self.elifs = elifs # List of (cond_ast, then_ast)
        self.else_ast = else_ast

class WhileNode(ASTNode):
    def __init__(self, condition_ast, body_ast):
        self.condition_ast = condition_ast
        self.body_ast = body_ast

class ForNode(ASTNode):
    def __init__(self, var_name, iter_items, body_ast):
        self.var_name = var_name
        self.iter_items = iter_items
        self.body_ast = body_ast

class FunctionDefNode(ASTNode):
    def __init__(self, func_name, body_ast):
        self.func_name = func_name
        self.body_ast = body_ast

class Tokenizer:
    @staticmethod
    def tokenize(cmd_line):
        """Metni tokenlara (argümanlar ve operatörlere) böler. Tırnak işaretlerini korur. argüman içindeki '&' ve '|' operatör sayılmaz."""
        
        tokens = []
        current_token = []
        in_single_quote = False
        in_double_quote = False
        escape_next = False
        
        i = 0
        while i < len(cmd_line):
            char = cmd_line[i]
            
            # 1. Escape (\) karakteri kontrolü
            if escape_next:
                current_token.append(char)
                escape_next = False
                i += 1
                continue
                
            if char == '\\':
                escape_next = True
                i += 1
                continue
                
            # 2. Tırnak işaretleri kontrolü
            if char == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
                i += 1
                continue
            elif char == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
                i += 1
                continue
                
            # Tırnak içindeyse her şeyi normal harf say
            if in_single_quote or in_double_quote:
                current_token.append(char)
                i += 1
                continue
                
            # 3. KORUMA ALANI OLMAYAN (Tırnaksız) YERLER
            
            # Boşluk gördüysek mevcut kelimeyi (token) bitir
            if char.isspace():
                if current_token:
                    tokens.append("".join(current_token))
                    current_token = []
                i += 1
                continue
                
            # Sabit operatörler kontrolü (<, >, >>, 2>, 2>>, 2>&1)
            # Acaba şu anki char '2' ve ondan sonraki '>' mi?
            if char == '2' and i + 1 < len(cmd_line) and cmd_line[i+1] == '>':
                if current_token:
                    tokens.append("".join(current_token))
                    current_token = []
                if i + 3 < len(cmd_line) and cmd_line[i+1:i+4] == '>&1':
                    tokens.append('2>&1')
                    i += 4
                    continue
                elif i + 2 < len(cmd_line) and cmd_line[i+1:i+3] == '>>':
                    tokens.append('2>>')
                    i += 3
                    continue
                else:
                    tokens.append('2>')
                    i += 2
                    continue
            
            if char == '<':
                if current_token:
                    tokens.append("".join(current_token))
                    current_token = []
                tokens.append('<')
                i += 1
                continue
                
            if char == '>':
                if current_token:
                    tokens.append("".join(current_token))
                    current_token = []
                if i + 1 < len(cmd_line) and cmd_line[i+1] == '>':
                    tokens.append('>>')
                    i += 2
                else:
                    tokens.append('>')
                    i += 1
                continue
                
            # '&' ve '|' operatörleri Fish Shell kuralı:
            # SADECE öncesi boşluksa/yoksa VEYA sonrası boşluksa/yoksa veya mantıksal &&/|| ise operatördür.
            # Sistem&Gorsel gibi bitişik bir harfe komşuysa DÜZ YAZI (Harf) sayılır.
            
            if char == '&':
                # && mantıksal operatör mü?
                if i + 1 < len(cmd_line) and cmd_line[i+1] == '&':
                    if current_token:
                        tokens.append("".join(current_token))
                        current_token = []
                    tokens.append('&&')
                    i += 2
                    continue
                else:
                    # Tekli '&' arka plan operatörü
                    # Acaba Sistem&Gorsel içindeki kelimenin bir parçası mı?
                    prev_is_space = (i == 0) or cmd_line[i-1].isspace()
                    next_is_space = (i == len(cmd_line)-1) or cmd_line[i+1].isspace()
                    
                    if prev_is_space or next_is_space: # Gerçek bir operatördür
                        if current_token:
                            tokens.append("".join(current_token))
                            current_token = []
                        tokens.append('&')
                        i += 1
                        continue
                    else:
                        # Bu bir yazının parçası (Sistem&Gorsel)
                        current_token.append(char)
                        i += 1
                        continue

            if char == ';':
                if current_token:
                    tokens.append("".join(current_token))
                    current_token = []
                tokens.append(';')
                i += 1
                continue
                
            if char in ('{', '}'):
                if current_token:
                    tokens.append("".join(current_token))
                    current_token = []
                tokens.append(char)
                i += 1
                continue

            if char == '|':
                # || mantıksal operatör mü?
                if i + 1 < len(cmd_line) and cmd_line[i+1] == '|':
                    if current_token:
                        tokens.append("".join(current_token))
                        current_token = []
                    tokens.append('||')
                    i += 2
                    continue
                else:
                    # Tekli '|' pipe operatörü
                    # Gerçi pipe için de Fish kuralı geçerlidir ama pipe genelde bitişik yazılsın da istenebilir (ls|grep). 
                    # Biz Fish mantığı `|` kelimenin ortasındaysa özel dosya adı olabileğini düşünüp harf sayacağız, 
                    # ama standart shell'lerde ls|grep pipe'tır. Bitişik pipe'ları kabul edelim mi?
                    # Kullanıcı kolaylığı için '|' bitişik de yazılsa Pipe sayılır! 
                    # (Çünkü dosya adı içinde '|' kullanan Arch'cı bile olmaz :D)
                    if current_token:
                        tokens.append("".join(current_token))
                        current_token = []
                    tokens.append('|')
                    i += 1
                    continue
                    
            # Hiçbiri değilse normal harftir
            current_token.append(char)
            i += 1

        # Döngü bitti, hala tırnak açıksa kullanıcı unuttu demektir (Multi-Line Tetiği)
        if in_single_quote or in_double_quote:
            raise ValueError("Kapanmamış tırnak işareti (Missing quotation)")
            
        # Kalan son kelime
        if current_token:
            tokens.append("".join(current_token))
            
        return tokens

    @staticmethod
    def wrap_tokenize(cmd_line):
        while True:
            try:
                return Tokenizer.tokenize(cmd_line)
            except ValueError as e:
                # Multi-line input
                try:
                    if KISHI_SESSION:
                        extra_line = KISHI_SESSION.prompt(ANSI(f"{COLOR_AMBER}> {COLOR_RESET}"))
                    else:
                        extra_line = input("> ")
                    cmd_line += "\n" + extra_line
                except EOFError:
                    print(f"\n{COLOR_RED}Sözdizimi Hatası:{COLOR_RESET} Eksik tırnak işareti ({e})")
                    return []
                except KeyboardInterrupt:
                    print()
                    return []

class Expander:
    @staticmethod
    def expand(arg_list):
        """Globs (*, ?), değişkenleri ($VAR) ve komut çıktılarını ($(cmd) / `cmd`) genişletir"""
        import re
        import subprocess

        expanded_args = []
        for arg in arg_list:
            # 1. Command Substitution
            # Tırnak içi veya dışı $(...) veya `...` formatlarını tespit edip çalıştırır
            def cmd_replacer(match):
                cmd_to_run = match.group(1) or match.group(2)
                try:
                    # Gerçek bir subshell hissiyatı için bash/fish yerine kendi shell'imizi de verebiliriz, 
                    # ama standart komutlar için bash/sh yeterlidir.
                    output = subprocess.check_output(cmd_to_run, shell=True, text=True, stderr=subprocess.DEVNULL)
                    return output.rstrip('\n')
                except subprocess.CalledProcessError:
                    return "" # Komut hata verdiyse boş string dön
            
            # $(...) eşleşmesi veya `...` eşleşmesi
            # Regex: \$\(([^)]+)\)  -> $(komut)
            # Regex: `([^`]+)`      -> `komut`
            arg = re.sub(r'\$\(([^)]+)\)|`([^`]+)`', cmd_replacer, arg)

            # 2. Variable Expansion
            if arg.startswith('$'):
                var_name = arg[1:]
                val = LOCAL_VARS.get(var_name, os.environ.get(var_name, ALIASES.get(var_name, "")))
                if val: expanded_args.append(val)
                continue
            elif '$' in arg: # string içi değişken (örn: "Hello $USER")
                def var_replacer(match):
                    v = match.group(1)
                    return LOCAL_VARS.get(v, os.environ.get(v, ""))
                arg = re.sub(r'\$([A-Za-z0-9_]+)', var_replacer, arg)

            # 3. Tilde Expansion
            if arg.startswith('~/') or arg == '~':
                arg = os.path.expanduser(arg)

            # 4. Globbing
            if '*' in arg or '?' in arg:
                matches = glob.glob(arg)
                if matches:
                    expanded_args.extend(matches)
                else:
                    expanded_args.append(arg)
            else:
                expanded_args.append(arg)
                
        return expanded_args

class Parser:
    @staticmethod
    def parse(tokens):
        """Token listesinden Recursive Inis ile Sequence/Logic/Pipeline AST'si çıkarır"""
        if not tokens: return None
        
        class TokenStream:
            def __init__(self, toks):
                self.toks = toks
                self.pos = 0
            
            def peek(self):
                if self.pos < len(self.toks): return self.toks[self.pos]
                return None
            
            def consume(self):
                t = self.peek()
                self.pos += 1
                return t

        stream = TokenStream(tokens)
        
        def parse_sequence(end_tokens=None):
            if end_tokens is None: end_tokens = []
            seq = SequenceNode()
            current_statement_tokens = []
            
            def push_statement():
                if current_statement_tokens:
                    ast = split_by_logic(current_statement_tokens)
                    if ast: seq.statements.append(ast)
                    current_statement_tokens.clear()

            while stream.peek() is not None:
                token = stream.peek()
                
                if token in end_tokens:
                    break
                    
                if token == ';':
                    stream.consume()
                    push_statement()
                    continue
                    
                if token == 'if':
                    push_statement()
                    stream.consume() # consume 'if'
                    
                    cond_toks = []
                    while stream.peek() not in ('then', ';', None):
                        cond_toks.append(stream.consume())
                    if stream.peek() == ';': stream.consume() # ignore optional ;
                    cond_ast = split_by_logic(cond_toks)
                    
                    if stream.peek() == 'then': stream.consume()
                    
                    then_ast = parse_sequence(end_tokens=['elif', 'else', 'fi'])
                    
                    elif_asts = []
                    while stream.peek() == 'elif':
                        stream.consume()
                        e_cond_toks = []
                        while stream.peek() not in ('then', ';', None):
                            e_cond_toks.append(stream.consume())
                        if stream.peek() == ';': stream.consume()
                        e_cond_ast = split_by_logic(e_cond_toks)
                        if stream.peek() == 'then': stream.consume()
                        e_then_ast = parse_sequence(end_tokens=['elif', 'else', 'fi'])
                        elif_asts.append((e_cond_ast, e_then_ast))
                        
                    else_ast = None
                    if stream.peek() == 'else':
                        stream.consume()
                        else_ast = parse_sequence(end_tokens=['fi'])
                        
                    if stream.peek() == 'fi':
                        stream.consume()
                        
                    seq.statements.append(IfNode(cond_ast, then_ast, elif_asts, else_ast))
                    continue

                if token == 'while':
                    push_statement()
                    stream.consume()
                    
                    cond_toks = []
                    while stream.peek() not in ('do', ';', None):
                        cond_toks.append(stream.consume())
                    if stream.peek() == ';': stream.consume()
                    cond_ast = split_by_logic(cond_toks)
                    
                    if stream.peek() == 'do': stream.consume()
                    
                    body_ast = parse_sequence(end_tokens=['done'])
                    
                    if stream.peek() == 'done': stream.consume()
                    
                    seq.statements.append(WhileNode(cond_ast, body_ast))
                    continue

                if token == 'for':
                    push_statement()
                    stream.consume()
                    
                    var_name = stream.consume() if stream.peek() else "i"
                    if stream.peek() == 'in': stream.consume()
                    
                    iter_items = []
                    while stream.peek() not in (';', 'do', None):
                        iter_items.append(stream.consume())
                        
                    if stream.peek() == ';': stream.consume()
                    if stream.peek() == 'do': stream.consume()
                    
                    body_ast = parse_sequence(end_tokens=['done'])
                    
                    if stream.peek() == 'done': stream.consume()
                    
                    seq.statements.append(ForNode(var_name, iter_items, body_ast))
                    continue
                    
                if stream.peek() and stream.peek() == '()':
                    # Sometimes tokenizer might separate myfunc and ()
                    # Or it's a single token myfunc()
                    pass # Handled below
                    
                if token.endswith('()'):
                    push_statement()
                    func_name = token[:-2]
                    stream.consume() # myfunc()
                    
                    if stream.peek() == '{': stream.consume()
                    body_ast = parse_sequence(end_tokens=['}'])
                    if stream.peek() == '}': stream.consume()
                    
                    seq.statements.append(FunctionDefNode(func_name, body_ast))
                    continue
                    
                if stream.pos + 1 <= len(stream.toks) and stream.peek() == '()':
                    push_statement()
                    func_name = token
                    stream.consume() # myfunc
                    stream.consume() # ()
                    
                    if stream.peek() == '{': stream.consume()
                    body_ast = parse_sequence(end_tokens=['}'])
                    if stream.peek() == '}': stream.consume()
                    
                    seq.statements.append(FunctionDefNode(func_name, body_ast))
                    continue

                current_statement_tokens.append(stream.consume())
                
            push_statement()
            return seq

        def split_by_logic(toks, force_bg=False):
            # En son işlenen mantık en üsttedir.
            # Öncelik sırası: önce & (background), sonra || ve && (logic)
            
            # Önce arka plan (background) işareti var mı bakalım. (&)
            # Bash mantığında cmd1 & cmd2 demek, cmd1'i arkaya at, cmd2'ye devam et demektir.
            out_bg = False
            if toks and toks[-1] == '&':
                out_bg = True
                toks = toks[:-1]

            for i in range(len(toks)-1, -1, -1):
                if toks[i] == '&': # Arada arka plan
                    left = split_by_logic(toks[:i], force_bg=True)
                    right = split_by_logic(toks[i+1:])
                    # '&' operatörü özeldir, sol tarafı arka planda başlatıp sağ tarafa "ve" gibi devam ederiz.
                    # Ama LogicNode beklemek yerine sıralı execution lazımdır.
                    # Basitlik için '&' operatörünü de LogicNode gibi isleyebiliriz fakat mantıksal bekleme yapmamalıyız.
                    return LogicNode(left, '&', right)
                    
                if toks[i] in ('&&', '||'):
                    left = split_by_logic(toks[:i])
                    right = split_by_logic(toks[i+1:])
                    return LogicNode(left, toks[i], right)
                    
            return parse_pipeline(toks, out_bg or force_bg)

        def parse_pipeline(toks, is_bg):
            pipe_node = PipelineNode()
            pipe_node.is_background = is_bg
            
            # Pipe ile böl
            cmd_toks_list = []
            curr = []
            for t in toks:
                if t == '|':
                    cmd_toks_list.append(curr)
                    curr = []
                else:
                    curr.append(t)
            cmd_toks_list.append(curr)
            
            for c_toks in cmd_toks_list:
                cmd_node = CommandNode()
                i = 0
                while i < len(c_toks):
                    if c_toks[i] == '<' and i+1 < len(c_toks):
                        cmd_node.in_file = c_toks[i+1]
                        i += 2
                    elif c_toks[i] == '>' and i+1 < len(c_toks):
                        cmd_node.out_file = c_toks[i+1]
                        i += 2
                    elif c_toks[i] == '>>' and i+1 < len(c_toks):
                        cmd_node.out_file = c_toks[i+1]
                        cmd_node.out_append = True
                        i += 2
                    elif c_toks[i] == '2>' and i+1 < len(c_toks):
                        cmd_node.err_file = c_toks[i+1]
                        i += 2
                    elif c_toks[i] == '2>>' and i+1 < len(c_toks):
                        cmd_node.err_file = c_toks[i+1]
                        cmd_node.err_append = True
                        i += 2
                    elif c_toks[i] == '2>&1':
                        cmd_node.err_to_out = True
                        i += 1
                    else:
                        cmd_node.args.append(c_toks[i])
                        i += 1
                        
                if cmd_node.args:
                    pipe_node.commands.append(cmd_node)
            return pipe_node

        return parse_sequence()

# ==================== AST EXECUTION ====================

def execute_pipeline(pipe_node):
    if not pipe_node.commands:
        return 0
        
    import copy
    commands = copy.deepcopy(pipe_node.commands)
    
    valid_commands = []
    for cmd in commands:
        if cmd.args and cmd.args[0] in ALIASES:
            aliased_parts = shlex.split(ALIASES[cmd.args[0]])
            cmd.args = aliased_parts + cmd.args[1:]
        cmd.args = Expander.expand(cmd.args)
        if cmd.args:
            valid_commands.append(cmd)
            
    num_cmds = len(valid_commands)
    if num_cmds == 0:
        return 0
    
    # Tek Komut ve Built-in ise doğrudan çalıştır (Parent Process'te çalışmalı, örn 'cd' fork edilmez)
    if num_cmds == 1:
        cmd = valid_commands[0]
        
        # Eğer A=1 şeklinde environment ataması varsa ama arkasında komut yoksa kalıcı etkilesin
        # (Örn kullanıcı export kullanmadan A=1 yazarsa)
        env_only = True
        for a in cmd.args:
            if '=' not in a or a.startswith('-'):
                env_only = False
                break
                
        if env_only and cmd.args:
            for a in cmd.args:
                k, v = a.split('=', 1)
                LOCAL_VARS[k] = v
            return 0
            
        # Geçici local atamaları atla, asıl program built-in mi bul
        actual_cmd_idx = 0
        for i, a in enumerate(cmd.args):
            if '=' not in a or a.startswith('-'):
                actual_cmd_idx = i
                break
                
        if actual_cmd_idx < len(cmd.args):
            cmd_name = cmd.args[actual_cmd_idx]
            if cmd_name in BUILTINS:
                # Sadece built-in argümanlarını gönder
                return BUILTINS[cmd_name](cmd.args[actual_cmd_idx:])
            elif cmd_name in FUNCTIONS:
                # Argümanları $1, $2 olarak aktar (Önce eski değerleri sakla)
                args_passed = cmd.args[actual_cmd_idx:]
                old_args = {str(i): LOCAL_VARS.get(str(i), None) for i in range(1, len(args_passed))}
                for i in range(1, len(args_passed)):
                    LOCAL_VARS[str(i)] = args_passed[i]
                    
                status = execute_ast(FUNCTIONS[cmd_name])
                
                # Temizle ve Eskileri dondur
                for k, v in old_args.items():
                    if v is None:
                        if k in LOCAL_VARS: del LOCAL_VARS[k]
                    else:
                        LOCAL_VARS[k] = v
                return status

    # Çoklu Pipe veya Tekli Harici (External) Komutlar (Process Group ve Job Control uygulanır)
    pipes = [os.pipe() for _ in range(num_cmds - 1)]
    pids = []
    
    # Process Group ID (Tüm pipeline elemanları ilk process'in ID'si etrafında toplanır)
    pgid = None
    shell_tty = -1
    old_pgrp = -1
    try:
        shell_tty = sys.stdin.fileno()
        old_pgrp = os.tcgetpgrp(shell_tty)
    except Exception:
        pass # Eğer IDE terminali gibiyse tty yoktur.

    import signal
    
    for i in range(num_cmds):
        cmd = valid_commands[i]
        in_fd = pipes[i-1][0] if i > 0 else 0
        out_fd = pipes[i][1] if i < num_cmds - 1 else 1
        
        err_fd = 2
        user_in_fd, user_out_fd, user_err_fd = None, None, None
        
        if cmd.in_file:
            try: user_in_fd = os.open(cmd.in_file, os.O_RDONLY)
            except: print(f"{COLOR_RED}Hata:{COLOR_RESET} {cmd.in_file} okunamıyor."); return 1
            
        if cmd.out_file:
            flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if cmd.out_append else os.O_TRUNC)
            try: user_out_fd = os.open(cmd.out_file, flags, 0o644)
            except: print(f"{COLOR_RED}Hata:{COLOR_RESET} {cmd.out_file} yazılamıyor."); return 1
            
        if cmd.err_to_out:
            pass # Dup2 in child
        elif cmd.err_file:
            flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if cmd.err_append else os.O_TRUNC)
            try: user_err_fd = os.open(cmd.err_file, flags, 0o644)
            except: print(f"{COLOR_RED}Hata:{COLOR_RESET} {cmd.err_file} yazılamıyor."); return 1

        final_in_fd = user_in_fd if user_in_fd is not None else in_fd
        final_out_fd = user_out_fd if user_out_fd is not None else out_fd
        final_err_fd = user_err_fd if user_err_fd is not None else err_fd

        pid = os.fork()
        if pid == 0:
            # CHILD PROCESS
            
            # Sinyal handler'ları resetle (Python arka planda SIGINT yoksayar, bunu eski haline çevirmeliyiz)
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            signal.signal(signal.SIGTSTP, signal.SIG_DFL)
            signal.signal(signal.SIGQUIT, signal.SIG_DFL)
            signal.signal(signal.SIGTTOU, signal.SIG_DFL)
            
            # process grubu kur
            child_pid = os.getpid()
            if i == 0:
                os.setpgid(child_pid, child_pid)
            else:
                os.setpgid(child_pid, pgid)
                
            if final_in_fd != 0: os.dup2(final_in_fd, 0)
            if final_out_fd != 1: os.dup2(final_out_fd, 1)
            
            if cmd.err_to_out:
                os.dup2(1, 2)
            elif final_err_fd != 2:
                os.dup2(final_err_fd, 2)
            
            for r, w in pipes:
                os.close(r)
                os.close(w)
            if user_in_fd: os.close(user_in_fd)
            if user_out_fd: os.close(user_out_fd)
            if user_err_fd: os.close(user_err_fd)

            # Geçici ortam değişkenlerini tespit et (Örn: A=1 B=2 python script.py)
            env_updates = {}
            cmd_args_to_run = []
            parsing_env = True
            for a in cmd.args:
                if parsing_env and '=' in a and not a.startswith('-'):
                    k, v = a.split('=', 1)
                    env_updates[k] = v
                else:
                    parsing_env = False
                    cmd_args_to_run.append(a)
            
            # Eğer sadece A=1 yazıldı ve başka komut yoksa (kalıcı environment ataması yap, child olarak çık)
            # Bash davranışı: yalın "A=1", session'a değil o subshell'e işler, lakin biz Engine 2.5'te
            # Ana session'a etki etmesini tercih edebiliriz veya Built-in olarak süzebiliriz.
            # Şimdilik sadece alt komuta atama yapıyoruz.
            if not cmd_args_to_run:
                sys.exit(0)
                
            for k, v in env_updates.items():
                os.environ[k] = v

            cmd_name = cmd_args_to_run[0]
            if cmd_name in BUILTINS:
                BUILTINS[cmd_name](cmd_args_to_run)
                sys.exit(0)
            if cmd_name in FUNCTIONS:
                for i in range(1, len(cmd_args_to_run)):
                    LOCAL_VARS[str(i)] = cmd_args_to_run[i]
                status = execute_ast(FUNCTIONS[cmd_name])
                sys.exit(status)
                
            try:
                os.execvp(cmd_name, cmd_args_to_run)
            except FileNotFoundError:
                sugg = get_close_match_suggestion(cmd_name)
                print(f"{COLOR_RED}Hata:{COLOR_RESET} '{cmd_name}' bulunamadı.{sugg}", file=sys.stderr)
                sys.exit(127)
        else:
            # PARENT PROCESS
            if i == 0:
                pgid = pid
            os.setpgid(pid, pgid)
            pids.append(pid)
            if user_in_fd: os.close(user_in_fd)
            if user_out_fd: os.close(user_out_fd)
            if user_err_fd: os.close(user_err_fd)

    for r, w in pipes:
        os.close(r)
        os.close(w)

    cmd_str = " ".join([" ".join(c.args) for c in valid_commands])
    job = JobManager.add_job(pids, cmd_str, pipe_node.is_background)

    last_status = 0
    if not pipe_node.is_background:
        # Foreground iş: Terminal kontrolünü bu process grubuna veriyoruz ki Ctr+C, Ctr+Z buna gitsin
        if old_pgrp != -1:
            try: os.tcsetpgrp(shell_tty, pgid)
            except Exception: pass
            
        for p in pids:
            # WUNTRACED ile durdurulma (SIGTSTP) sinyalini de bekle
            try:
                wpid, status = os.waitpid(p, os.WUNTRACED)
                if os.WIFSTOPPED(status):
                    job.status = "Stopped"
                    job.is_background = True
                    print(f"\n{COLOR_YELLOW}[{job.job_id}]+  Durduruldu{COLOR_RESET}      {job.cmd_str}")
                    break # Diğer process'leri beklemeye gerek yok
                else:
                    last_status = os.waitstatus_to_exitcode(status)
            except ChildProcessError:
                pass
                
        # Eğer durdurulmadıysa (bitti veya crash ettiyse), job'u listeden sil
        if job.status != "Stopped":
            JobManager.remove_job(job.job_id)
            
        # Terminal kontrolünü Shell ana döngü grubuna geri al
        if old_pgrp != -1:
            try: os.tcsetpgrp(shell_tty, old_pgrp)
            except Exception: pass
    else:
        pass # Arkaplan ise JobManager eklendi, baska bir sey bekleme

    return last_status

def execute_ast(node):
    if node is None:
        return 0
        
    if isinstance(node, SequenceNode):
        last_status = 0
        for stmt in node.statements:
            last_status = execute_ast(stmt)
        return last_status
        
    elif isinstance(node, IfNode):
        if execute_ast(node.condition_ast) == 0:
            return execute_ast(node.then_ast)
        else:
            for c_ast, t_ast in node.elifs:
                if execute_ast(c_ast) == 0:
                    return execute_ast(t_ast)
            if node.else_ast:
                return execute_ast(node.else_ast)
        return 0
        
    elif isinstance(node, WhileNode):
        last_status = 0
        while execute_ast(node.condition_ast) == 0:
            last_status = execute_ast(node.body_ast)
        return last_status
        
    elif isinstance(node, ForNode):
        items = Expander.expand(node.iter_items)
        last_status = 0
        for item in items:
            LOCAL_VARS[node.var_name] = item
            last_status = execute_ast(node.body_ast)
        return last_status
        
    elif isinstance(node, FunctionDefNode):
        FUNCTIONS[node.func_name] = node.body_ast
        return 0
        
    elif isinstance(node, LogicNode):
        if node.operator == '&':
            # Sol tarafı (is_background = True olarak ayarlanmış pipe) çalıştır, bekleme.
            execute_ast(node.left)
            # Sağ tarafa hemen geç (Örn: cmd1 & cmd2)
            return execute_ast(node.right)
            
        left_status = execute_ast(node.left)
        if node.operator == '&&':
            if left_status == 0:
                return execute_ast(node.right)
            return left_status
        elif node.operator == '||':
            if left_status != 0:
                return execute_ast(node.right)
            return left_status
    elif isinstance(node, PipelineNode):
        return execute_pipeline(node)
    return 0

def process_command_line(cmd_line):
    """Ana komut işleyici"""
    
    # History Expansion (!!, !$)
    try:
        if ('!!' in cmd_line or '!$' in cmd_line) and KISHI_SESSION:
            # prompt_toolkit history listesini alır
            strings = KISHI_SESSION.history.get_strings()
            if strings:
                last_idx = len(strings) - 1
                last_cmd = strings[last_idx]
                
                # input() otomatik history'ye eklediği için kendisiyle aynı olmayan ilk komutu bul
                while last_cmd == cmd_line and last_idx > 0:
                    last_idx -= 1
                    last_cmd = strings[last_idx]
                
                expanded = False
                
                if '!!' in cmd_line and last_cmd:
                    cmd_line = cmd_line.replace('!!', last_cmd)
                    expanded = True
                if '!$' in cmd_line and last_cmd:
                    try:
                        last_arg = Tokenizer.tokenize(last_cmd)[-1]
                        cmd_line = cmd_line.replace('!$', last_arg)
                        expanded = True
                    except: pass
                
                if expanded:
                    print(cmd_line) # Bash gibi
                    # NOT: prompt_toolkit FileHistory'i direk editlemek (replace) read-only tarzıdır, 
                    # bu nedenle sadece genişletilmiş halini execute'a paslıyoruz. Eski komut aynı yerinde kalır.
    except Exception:
        pass
    tokens = Tokenizer.wrap_tokenize(cmd_line)
    if not tokens:
        return
    ast = Parser.parse(tokens)
    if ast:
        execute_ast(ast)

# ==================== UI & PROMPT ALTYAPISI ====================
def get_prompts():
    """Artık sol ve sağ prompt'ları prompt_toolkit formatında ayırıyoruz"""
    import subprocess
    cwd = os.getcwd()
    home = os.environ.get("HOME", "")
    
    if home and cwd.startswith(home):
        display_cwd = cwd.replace(home, "~", 1)
    else:
        display_cwd = cwd

    # Sığdırma işlemi prompt_toolkit de kendi halledebilir ama biz ekleyelim
    try:
        term_width = os.get_terminal_size().columns
        if len(display_cwd) > term_width - 15:
            display_cwd = "..." + display_cwd[-(term_width - 20):]
    except:
        pass
        
    left_prompt = ANSI(f"{COLOR_AMBER}Kishi$ ->{COLOR_RESET} ")
    
    # Git Kontrolü (Engine 4.0)
    git_branch = ""
    try:
        git_out = subprocess.check_output(
            ["git", "branch", "--show-current"],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
        if git_out:
            git_branch = f"{COLOR_YELLOW}git:({COLOR_RED}{git_out}{COLOR_YELLOW}) {COLOR_RESET}"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
        
    right_prompt = ANSI(f"{git_branch}{COLOR_CYAN}[{display_cwd}]{COLOR_RESET}")
    
    return left_prompt, right_prompt


# ==================== ANA DONGU ====================
if __name__ == "__main__":
    import signal

    # Shell'in kendi Ctrl+C'de kapanmaması için Interrupt'ı yakalıyoruz
    def sigint_handler(sig, frame):
        pass # prompt_toolkit will handle this internally with KeyboardInterrupt exception
    signal.signal(signal.SIGINT, sigint_handler)
    
    # Arka plan işlerini (Ctrl+Z) yoksay ve Terminal Çıkış/Giriş sinyallerini devral (Kishi shellin durmasını engeller)
    try:
        signal.signal(signal.SIGTSTP, signal.SIG_IGN)
        signal.signal(signal.SIGTTOU, signal.SIG_IGN)
        signal.signal(signal.SIGTTIN, signal.SIG_IGN)
    except AttributeError:
        pass # Windows vs

    load_system_commands()
    init_prompt_toolkit()
    load_rc_file()
    
    print(f"{COLOR_AMBER}Kishi Shell Gelişmiş Sürüm (v1.5) başlatıldı.{COLOR_RESET}")
    print("Yardım için 'help' yazabilirsiniz.")

    while True:
        try:
            # Ekranda biten job'ları prompt basılmadan evvel bas
            JobManager.clean_jobs()
            
            l_prompt, r_prompt = get_prompts()
            if KISHI_SESSION:
                cmd_line = KISHI_SESSION.prompt(l_prompt, rprompt=r_prompt)
            else:
                cmd_line = input("Kishi$ -> ")
            
            if not cmd_line.strip():
                continue
            
            # Ana işleme başlatılıyor (Engine 2.0)
            process_command_line(cmd_line)
            
        except EOFError:
            print(f"\n{COLOR_AMBER}Kishi:{COLOR_RESET} Çıkış sinyali alındı. Hoşça kal!")
            break
        except Exception as e:
            # Shell çökmelerini engellemek için
            print(f"{COLOR_RED}Kishi Panic:{COLOR_RESET} Shell döngüsünde hata yakalandı: {e}", file=sys.stderr)
