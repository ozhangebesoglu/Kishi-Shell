"""
Strict tests for kishi/main.py
Tests focus on RC file loading, plugin loading, and profile sourcing logic.
"""
import os
import re
import sys
import pytest
from unittest.mock import patch

from kishi import state
from kishi.main import load_rc_file, load_plugins, _source_profile


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_state():
    """Reset global state after each test."""
    old_aliases = state.ALIASES.copy()
    old_builtins = state.BUILTINS.copy()
    old_local = state.LOCAL_VARS.copy()
    old_interactive = state.IS_INTERACTIVE

    yield

    state.ALIASES.clear()
    state.ALIASES.update(old_aliases)
    state.BUILTINS.clear()
    state.BUILTINS.update(old_builtins)
    state.LOCAL_VARS.clear()
    state.LOCAL_VARS.update(old_local)
    state.IS_INTERACTIVE = old_interactive


@pytest.fixture
def clean_env():
    """Save and restore env vars that tests may modify."""
    saved = {}
    test_keys = ["KISHI_RC_TEST", "KISHI_PROFILE_VAR", "KISHI_EXPAND_VAR",
                 "KISHI_SRC_A", "KISHI_SRC_B"]
    for k in test_keys:
        if k in os.environ:
            saved[k] = os.environ[k]

    yield

    for k in test_keys:
        if k in saved:
            os.environ[k] = saved[k]
        elif k in os.environ:
            del os.environ[k]


# ---------------------------------------------------------------------------
# load_rc_file
# ---------------------------------------------------------------------------

class TestLoadRcFile:
    def test_alias_definition(self, tmp_path):
        """alias ll='ls -la' in RC should register in state.ALIASES."""
        rc = tmp_path / ".kishirc"
        rc.write_text("alias ll='ls -la'\nalias gs='git status'\n")

        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            load_rc_file()

        assert state.ALIASES["ll"] == "ls -la"
        assert state.ALIASES["gs"] == "git status"

    def test_export_definition(self, tmp_path, clean_env):
        """export VAR=value in RC should set os.environ."""
        rc = tmp_path / ".kishirc"
        rc.write_text("export KISHI_RC_TEST=from_rc\n")

        with patch.dict(os.environ, {"HOME": str(tmp_path)}, clear=False):
            load_rc_file()
            assert os.environ["KISHI_RC_TEST"] == "from_rc"

    def test_export_var_expansion(self, tmp_path, clean_env):
        """export should expand $VAR references."""
        os.environ["KISHI_EXPAND_VAR"] = "base"
        rc = tmp_path / ".kishirc"
        rc.write_text("export KISHI_RC_TEST=$KISHI_EXPAND_VAR/extra\n")

        with patch.dict(os.environ, {"HOME": str(tmp_path)}, clear=False):
            load_rc_file()
            assert os.environ["KISHI_RC_TEST"] == "base/extra"

    def test_comments_and_blank_lines_ignored(self, tmp_path):
        """Comments and blank lines should not produce errors or side effects."""
        rc = tmp_path / ".kishirc"
        rc.write_text("# This is a comment\n\n# Another comment\nalias x='y'\n")

        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            result = load_rc_file()

        assert state.ALIASES["x"] == "y"
        assert len([a for a in state.ALIASES if a.startswith("#")]) == 0

    def test_creates_default_rc_if_missing(self, tmp_path):
        """If .kishirc doesn't exist, it should be created with defaults."""
        rc_path = tmp_path / ".kishirc"
        assert not rc_path.exists()

        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            load_rc_file()

        assert rc_path.exists()
        content = rc_path.read_text()
        assert "alias ll=" in content

    def test_startup_commands_returned(self, tmp_path):
        """Non-alias, non-export lines should be returned as startup commands."""
        rc = tmp_path / ".kishirc"
        rc.write_text("alias a='b'\necho hello\nls -la\n")

        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            cmds = load_rc_file()

        assert "echo hello" in cmds
        assert "ls -la" in cmds
        # Aliases should NOT appear in startup commands
        assert not any("alias" in c for c in cmds)


# ---------------------------------------------------------------------------
# load_plugins
# ---------------------------------------------------------------------------

class TestLoadPlugins:
    def test_valid_plugin_loaded(self, tmp_path):
        """A plugin with correct PLUGIN_COMMANDS should register its command."""
        plugin_dir = tmp_path / ".kishi" / "plugins"
        plugin_dir.mkdir(parents=True)

        plugin_code = '''
def hello_cmd(args):
    print("hello from plugin")
    return 0

PLUGIN_COMMANDS = {
    "testplugin": hello_cmd
}
'''
        (plugin_dir / "testplugin.py").write_text(plugin_code)

        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            load_plugins()

        assert "testplugin" in state.BUILTINS
        assert callable(state.BUILTINS["testplugin"])

    def test_plugin_without_dict_ignored(self, tmp_path, capsys):
        """A plugin without PLUGIN_COMMANDS dict should be silently skipped."""
        plugin_dir = tmp_path / ".kishi" / "plugins"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "badplugin.py").write_text("x = 1\n")

        state.IS_INTERACTIVE = False
        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            load_plugins()

        assert "badplugin" not in state.BUILTINS

    def test_plugin_wrong_key_warned(self, tmp_path, capsys):
        """Plugin with PLUGIN_COMMANDS but wrong key should warn in interactive."""
        plugin_dir = tmp_path / ".kishi" / "plugins"
        plugin_dir.mkdir(parents=True)

        plugin_code = '''
def wrong_cmd(args):
    return 0

PLUGIN_COMMANDS = {
    "wrongname": wrong_cmd
}
'''
        (plugin_dir / "myplugin.py").write_text(plugin_code)

        state.IS_INTERACTIVE = True
        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            load_plugins()

        captured = capsys.readouterr()
        assert "myplugin" not in state.BUILTINS
        assert "ignored" in captured.out.lower() or "Plugin Warning" in captured.out

    def test_missing_plugin_dir_silent(self, tmp_path):
        """If plugin directory doesn't exist, should not crash."""
        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            load_plugins()  # should not raise

    def test_syntax_error_plugin(self, tmp_path, capsys):
        """A plugin with a syntax error should not crash the shell."""
        plugin_dir = tmp_path / ".kishi" / "plugins"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "broken.py").write_text("def oops(:\n  pass\n")

        state.IS_INTERACTIVE = True
        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            load_plugins()

        captured = capsys.readouterr()
        assert "broken" not in state.BUILTINS
        assert "Plugin Error" in captured.out or "Failed" in captured.out


# ---------------------------------------------------------------------------
# _source_profile
# ---------------------------------------------------------------------------

class TestSourceProfile:
    def test_export_sets_env(self, tmp_path, clean_env):
        """export VAR=value in profile should set os.environ."""
        profile = tmp_path / "profile"
        profile.write_text("export KISHI_PROFILE_VAR=hello\n")

        _source_profile(str(profile))
        assert os.environ["KISHI_PROFILE_VAR"] == "hello"

    def test_plain_assignment_sets_env(self, tmp_path, clean_env):
        """VAR=value (without export) should also set os.environ."""
        profile = tmp_path / "profile"
        profile.write_text("KISHI_PROFILE_VAR=world\n")

        _source_profile(str(profile))
        assert os.environ["KISHI_PROFILE_VAR"] == "world"

    def test_var_expansion_in_profile(self, tmp_path, clean_env):
        """$VAR references in profile values should expand."""
        os.environ["KISHI_SRC_A"] = "alpha"
        profile = tmp_path / "profile"
        profile.write_text("KISHI_SRC_B=$KISHI_SRC_A/beta\n")

        _source_profile(str(profile))
        assert os.environ["KISHI_SRC_B"] == "alpha/beta"

    def test_comments_skipped(self, tmp_path, clean_env):
        """Lines starting with # should be ignored."""
        profile = tmp_path / "profile"
        profile.write_text("# comment\nKISHI_PROFILE_VAR=ok\n")

        _source_profile(str(profile))
        assert os.environ["KISHI_PROFILE_VAR"] == "ok"

    def test_blank_lines_skipped(self, tmp_path, clean_env):
        """Empty lines should not cause issues."""
        profile = tmp_path / "profile"
        profile.write_text("\n\nKISHI_PROFILE_VAR=fine\n\n")

        _source_profile(str(profile))
        assert os.environ["KISHI_PROFILE_VAR"] == "fine"

    def test_nonexistent_file_silent(self):
        """Sourcing a non-existent file should not crash."""
        _source_profile("/nonexistent/path/to/profile/xyz")

    def test_quoted_values_stripped(self, tmp_path, clean_env):
        """Quotes around values should be stripped."""
        profile = tmp_path / "profile"
        profile.write_text('KISHI_PROFILE_VAR="quoted"\n')

        _source_profile(str(profile))
        assert os.environ["KISHI_PROFILE_VAR"] == "quoted"

    def test_single_quoted_values_stripped(self, tmp_path, clean_env):
        """Single quotes around values should be stripped."""
        profile = tmp_path / "profile"
        profile.write_text("KISHI_PROFILE_VAR='single'\n")

        _source_profile(str(profile))
        assert os.environ["KISHI_PROFILE_VAR"] == "single"
