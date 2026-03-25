from prompt_toolkit import Application
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.cursor_shapes import CursorShape

def my_cursor():
    return CursorShape.BLINKING_BEAM

try:
    app = Application(
        layout=Layout(Window(FormattedTextControl("Test"))),
        cursor=my_cursor,
    )
    # We won't run it fully, just check if it crashes parsing cursor somehow.
    # Actually wait, let's look at prompt_toolkit source for 'get_cursor_shape'
    print("App created")
except Exception as e:
    print(f"Error: {e}")
