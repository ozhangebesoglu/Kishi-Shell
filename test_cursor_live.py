import os
import threading
import time
from prompt_toolkit import PromptSession
from prompt_toolkit.cursor_shapes import CursorShape, DynamicCursorShapeConfig

def get_cursor():
    shape_str = os.environ.get("CURSOR_SHAPE", "BLOCK").upper()
    mapping = {
        "BLOCK": CursorShape.BLOCK,
        "BEAM": CursorShape.BEAM,
        "UNDERLINE": CursorShape.UNDERLINE
    }
    return mapping.get(shape_str, CursorShape.BLOCK)

def change_env_later(session):
    time.sleep(2)
    os.environ["CURSOR_SHAPE"] = "BEAM"
    print("\n[Background] Changed CURSOR_SHAPE to BEAM! Press Enter.")
    # Force redraw
    session.app.invalidate()

session = PromptSession(cursor=DynamicCursorShapeConfig(get_cursor))
threading.Thread(target=change_env_later, args=(session,), daemon=True).start()

print("Type something (cursor should change to BEAM in 2 seconds)...")
try:
    text = session.prompt("> ")
    print("You said:", text)
except EOFError:
    pass
