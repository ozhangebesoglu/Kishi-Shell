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
class CommandList(list):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._set = set(self)

    def __contains__(self, item):
        return item in self._set

    def append(self, item):
        super().append(item)
        self._set.add(item)

    def extend(self, items):
        super().extend(items)
        self._set.update(items)

    def remove(self, item):
        super().remove(item)
        self._set.discard(item)

    def clear(self):
        super().clear()
        self._set.clear()

SYSTEM_COMMANDS = CommandList()
BUILTINS = {} # Will be populated by builtins.py

KISHI_SESSION = None
# Re-align line breaks
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
    SYSTEM_COMMANDS = CommandList(cmds)

def get_cursor_shape():
    """Returns the prompt_toolkit CursorShape based on CURSOR_SHAPE env variable."""
    try:
        from prompt_toolkit.cursor_shapes import CursorShape
    except ImportError:
        return None
    shape_str = os.environ.get("CURSOR_SHAPE", "BLINKING_BLOCK").upper()
    mapping = {
        "BLOCK": CursorShape.BLOCK,
        "BLINKING_BLOCK": CursorShape.BLINKING_BLOCK,
        "UNDERLINE": CursorShape.UNDERLINE,
        "BLINKING_UNDERLINE": CursorShape.BLINKING_UNDERLINE,
        "BEAM": CursorShape.BEAM,
        "BLINKING_BEAM": CursorShape.BLINKING_BEAM,
    }
    return mapping.get(shape_str, CursorShape.BLINKING_BLOCK)
