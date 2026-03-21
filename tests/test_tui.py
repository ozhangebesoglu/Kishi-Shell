import pytest
import os
from unittest.mock import patch, MagicMock

# Attempt to import Pygments lexer checks, depending on whether Pygments is installed
try:
    from pygments.lexers.python import PythonLexer
    from pygments.lexers.javascript import JavascriptLexer
    HAS_PYGMENTS = True
except ImportError:
    HAS_PYGMENTS = False

from prompt_toolkit.lexers import PygmentsLexer

# Import the UI modules to test
from kishi.tui_explorer import ExplorerUI, FileSystemProvider, ExplorerState
from kishi.tui_dashboard import DashboardState


@pytest.fixture
def tmp_dir(tmp_path):
    # Create some dummy files in a temporary directory
    (tmp_path / "script.py").write_text("print('hello')")
    (tmp_path / "app.js").write_text("console.log('hi');")
    (tmp_path / "notes.txt").write_text("some notes")
    return tmp_path


def test_explorer_resolve_lexer(tmp_dir):
    """Test that the ExplorerUI correctly resolves PygmentsLexers based on file extensions."""
    if not HAS_PYGMENTS:
        pytest.skip("Pygments is not installed")
        
    explorer = ExplorerUI(str(tmp_dir), standalone=False)
    
    # 1. Test Python file
    explorer._resolve_lexer("script.py")
    assert explorer._current_lexer is not None
    assert isinstance(explorer._current_lexer, PygmentsLexer)
    assert explorer._current_lexer.pygments_lexer_cls == PythonLexer

    # 2. Test Javascript file
    explorer._resolve_lexer("app.js")
    assert explorer._current_lexer is not None
    assert explorer._current_lexer.pygments_lexer_cls == JavascriptLexer

    # 3. Test Text file (might resolve to TextLexer or None depending on Pygments)
    explorer._resolve_lexer("notes.txt")
    # Actually just make sure it doesn't crash
    lexer = explorer._get_lexer()
    
    # 4. Test None
    explorer._resolve_lexer(None)
    assert explorer._current_lexer is None


def test_filesystem_provider(tmp_dir):
    """Test the FileSystemProvider logic which is decoupled from the UI."""
    files = FileSystemProvider.list_directory(str(tmp_dir))
    
    assert ".." in files
    assert "script.py" in files
    assert "app.js" in files
    assert "notes.txt" in files
    
    # Test reading
    content, is_valid = FileSystemProvider.read_file(str(tmp_dir / "script.py"))
    assert is_valid is True
    assert content == "print('hello')"


def test_explorer_state_navigation(tmp_dir):
    """Test ExplorerState headless navigation logic."""
    state = ExplorerState(str(tmp_dir))
    assert state.current_dir == str(tmp_dir)
    assert ".." in state.files
    
    initial_idx = state.selected_index
    assert initial_idx == 0
    
    # Move down
    moved = state.select_next()
    assert moved is True
    assert state.selected_index == 1
    
    # Move up
    moved = state.select_previous()
    assert moved is True
    assert state.selected_index == 0


def test_dashboard_state_toggle():
    """Test the pure state logic of the Dashboard."""
    state = DashboardState()
    # By default, show_explorer is False
    assert state.show_explorer is False
    
    # Toggle it like the keybinding does
    state.show_explorer = not state.show_explorer
    assert state.show_explorer is True
