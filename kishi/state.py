import os

# ==================== GLOBAL STATE & CONSTANTS ====================
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
BUILTINS = {} # Will be populated by builtins.py

KISHI_SESSION = None
IS_LOGIN_SHELL = False
IS_INTERACTIVE = False

def load_system_commands():
    """Loads executable system commands into memory"""
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
