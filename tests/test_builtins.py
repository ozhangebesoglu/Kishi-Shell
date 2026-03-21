"""
Strict tests for kishi/builtins.py
Tests validate real behaviors: correct return codes, side effects on state, error handling.
"""
import os
import sys
import pytest
from io import StringIO
from unittest.mock import patch

from kishi import state
from kishi.builtins import (
    kishi_cd, kishi_pwd, kishi_export, kishi_unset, kishi_test,
    kishi_help, kishi_deactivate, kishi_plugin, kishi_neofetch,
    BUILTINS_DICT,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_state():
    """Reset mutable global state after each test."""
    old_local = state.LOCAL_VARS.copy()
    old_aliases = state.ALIASES.copy()
    old_env_snapshot = {}

    # Save env vars we might touch
    for key in ("KISHI_TEST_EXPORT", "KISHI_UNSET_TEST", "VIRTUAL_ENV",
                "_OLD_VIRTUAL_PATH", "KISHI_PROMO"):
        if key in os.environ:
            old_env_snapshot[key] = os.environ[key]

    yield

    state.LOCAL_VARS.clear()
    state.LOCAL_VARS.update(old_local)
    state.ALIASES.clear()
    state.ALIASES.update(old_aliases)

    # Restore env
    for key in ("KISHI_TEST_EXPORT", "KISHI_UNSET_TEST", "VIRTUAL_ENV",
                "_OLD_VIRTUAL_PATH", "KISHI_PROMO"):
        if key in old_env_snapshot:
            os.environ[key] = old_env_snapshot[key]
        elif key in os.environ:
            del os.environ[key]


@pytest.fixture
def saved_cwd():
    """Save and restore CWD around cd tests."""
    original = os.getcwd()
    yield original
    os.chdir(original)


# ---------------------------------------------------------------------------
# cd
# ---------------------------------------------------------------------------

class TestCd:
    def test_cd_to_valid_directory(self, saved_cwd, tmp_path):
        """cd should change to a valid directory and return 0."""
        result = kishi_cd(["cd", str(tmp_path)])
        assert result == 0
        assert os.getcwd() == str(tmp_path)

    def test_cd_nonexistent_directory(self, saved_cwd):
        """cd to a nonexistent directory should return 1."""
        result = kishi_cd(["cd", "/nonexistent_dir_xyz_12345"])
        assert result == 1

    def test_cd_no_args_goes_home(self, saved_cwd):
        """cd without arguments should go to $HOME."""
        home = os.environ.get("HOME", "/")
        result = kishi_cd(["cd"])
        assert result == 0
        assert os.getcwd() == os.path.realpath(home)

    def test_cd_to_file(self, saved_cwd, tmp_path):
        """cd to a file (not directory) should return 1."""
        f = tmp_path / "somefile.txt"
        f.touch()
        result = kishi_cd(["cd", str(f)])
        assert result == 1


# ---------------------------------------------------------------------------
# pwd
# ---------------------------------------------------------------------------

class TestPwd:
    def test_pwd_outputs_cwd(self, capsys):
        """pwd should print the current working directory."""
        result = kishi_pwd(["pwd"])
        captured = capsys.readouterr()
        assert result == 0
        assert captured.out.strip() == os.getcwd()


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------

class TestExport:
    def test_export_sets_env(self):
        """export KEY=VALUE should set os.environ."""
        result = kishi_export(["export", "KISHI_TEST_EXPORT=hello"])
        assert result == 0
        assert os.environ["KISHI_TEST_EXPORT"] == "hello"

    def test_export_expands_vars(self):
        """export should expand $VAR references in values."""
        os.environ["KISHI_TEST_EXPORT"] = "base"
        result = kishi_export(["export", "KISHI_TEST_EXPORT=$KISHI_TEST_EXPORT/appended"])
        assert result == 0
        assert os.environ["KISHI_TEST_EXPORT"] == "base/appended"

    def test_export_removes_from_local_vars(self):
        """After export, the key should be removed from LOCAL_VARS."""
        state.LOCAL_VARS["KISHI_PROMO"] = "promoted"
        result = kishi_export(["export", "KISHI_PROMO=newval"])
        assert result == 0
        assert "KISHI_PROMO" not in state.LOCAL_VARS
        assert os.environ["KISHI_PROMO"] == "newval"

    def test_export_promotes_local_var(self):
        """export VARNAME (no =) should promote LOCAL_VARS to env."""
        state.LOCAL_VARS["KISHI_PROMO"] = "from_local"
        result = kishi_export(["export", "KISHI_PROMO"])
        assert result == 0
        assert os.environ["KISHI_PROMO"] == "from_local"
        assert "KISHI_PROMO" not in state.LOCAL_VARS

    def test_export_no_args_lists_env(self, capsys):
        """export with no arguments should list all env vars."""
        result = kishi_export(["export"])
        captured = capsys.readouterr()
        assert result == 0
        assert "export " in captured.out


# ---------------------------------------------------------------------------
# unset
# ---------------------------------------------------------------------------

class TestUnset:
    def test_unset_env_variable(self):
        """unset should remove a variable from os.environ."""
        os.environ["KISHI_UNSET_TEST"] = "val"
        result = kishi_unset(["unset", "KISHI_UNSET_TEST"])
        assert result == 0
        assert "KISHI_UNSET_TEST" not in os.environ

    def test_unset_local_variable(self):
        """unset should remove from LOCAL_VARS."""
        state.LOCAL_VARS["KISHI_UNSET_TEST"] = "local"
        result = kishi_unset(["unset", "KISHI_UNSET_TEST"])
        assert result == 0
        assert "KISHI_UNSET_TEST" not in state.LOCAL_VARS

    def test_unset_both(self):
        """unset should remove from both env and LOCAL_VARS."""
        os.environ["KISHI_UNSET_TEST"] = "env"
        state.LOCAL_VARS["KISHI_UNSET_TEST"] = "local"
        kishi_unset(["unset", "KISHI_UNSET_TEST"])
        assert "KISHI_UNSET_TEST" not in os.environ
        assert "KISHI_UNSET_TEST" not in state.LOCAL_VARS

    def test_unset_no_args(self, capsys):
        """unset without variable name should return 1."""
        result = kishi_unset(["unset"])
        assert result == 1

    def test_unset_nonexistent_is_silent(self):
        """unset of a nonexistent variable should not crash."""
        result = kishi_unset(["unset", "DEFINITELY_NOT_SET_XYZ"])
        assert result == 0


# ---------------------------------------------------------------------------
# test / [ (POSIX test builtin)
# ---------------------------------------------------------------------------

class TestTestBuiltin:
    # --- File tests ---
    def test_file_exists(self, tmp_path):
        """test -f should return 0 for existing file."""
        f = tmp_path / "afile"
        f.touch()
        assert kishi_test(["test", "-f", str(f)]) == 0

    def test_file_not_exists(self):
        """test -f should return 1 for non-existing file."""
        assert kishi_test(["test", "-f", "/no/such/file/xyz"]) == 1

    def test_dir_exists(self, tmp_path):
        """test -d should return 0 for existing directory."""
        assert kishi_test(["test", "-d", str(tmp_path)]) == 0

    def test_dir_not_exists(self):
        """test -d should return 1 for non-existing directory."""
        assert kishi_test(["test", "-d", "/no/such/dir/xyz"]) == 1

    # --- String tests ---
    def test_z_empty_string(self):
        """test -z '' should return 0."""
        assert kishi_test(["test", "-z", ""]) == 0

    def test_z_nonempty_string(self):
        """test -z 'hello' should return 1."""
        assert kishi_test(["test", "-z", "hello"]) == 1

    def test_n_nonempty_string(self):
        """test -n 'hello' should return 0."""
        assert kishi_test(["test", "-n", "hello"]) == 0

    def test_n_empty_string(self):
        """test -n '' should return 1."""
        assert kishi_test(["test", "-n", ""]) == 1

    # --- String comparison ---
    def test_string_equal(self):
        """test a = a should return 0."""
        assert kishi_test(["test", "hello", "=", "hello"]) == 0

    def test_string_not_equal(self):
        """test a = b should return 1."""
        assert kishi_test(["test", "hello", "=", "world"]) == 1

    def test_string_inequality(self):
        """test a != b should return 0."""
        assert kishi_test(["test", "hello", "!=", "world"]) == 0

    def test_string_inequality_same(self):
        """test a != a should return 1."""
        assert kishi_test(["test", "hello", "!=", "hello"]) == 1

    # --- Numeric comparison ---
    def test_eq(self):
        assert kishi_test(["test", "5", "-eq", "5"]) == 0

    def test_ne(self):
        assert kishi_test(["test", "5", "-ne", "3"]) == 0

    def test_gt(self):
        assert kishi_test(["test", "10", "-gt", "5"]) == 0

    def test_gt_fail(self):
        assert kishi_test(["test", "3", "-gt", "5"]) == 1

    def test_lt(self):
        assert kishi_test(["test", "3", "-lt", "5"]) == 0

    def test_ge(self):
        assert kishi_test(["test", "5", "-ge", "5"]) == 0

    def test_le(self):
        assert kishi_test(["test", "5", "-le", "5"]) == 0

    # --- Bracket form ---
    def test_bracket_form(self):
        """[ ... ] form should work identically."""
        assert kishi_test(["[", "hello", "=", "hello", "]"]) == 0

    def test_bracket_missing_closing(self, capsys):
        """[ without ] should print error and return 1."""
        result = kishi_test(["[", "hello", "=", "hello"])
        assert result == 1
        captured = capsys.readouterr()
        assert "missing closing bracket" in captured.out

    # --- Edge cases ---
    def test_empty_args(self):
        """test with no args should return 1."""
        assert kishi_test([]) == 1

    def test_single_nonempty_arg(self):
        """test 'nonempty' should return 0."""
        assert kishi_test(["test", "nonempty"]) == 0


# ---------------------------------------------------------------------------
# deactivate
# ---------------------------------------------------------------------------

class TestDeactivate:
    def test_no_venv_active(self, capsys):
        """deactivate when no venv is active should print message."""
        if "VIRTUAL_ENV" in os.environ:
            del os.environ["VIRTUAL_ENV"]
        result = kishi_deactivate(["deactivate"])
        assert result == 0
        captured = capsys.readouterr()
        assert "No virtual environment" in captured.out

    def test_venv_deactivation(self, capsys, tmp_path):
        """deactivate should remove VIRTUAL_ENV and clean PATH."""
        venv_dir = str(tmp_path / "myvenv")
        bin_dir = os.path.join(venv_dir, "bin")
        os.environ["VIRTUAL_ENV"] = venv_dir
        os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")

        result = kishi_deactivate(["deactivate"])
        assert result == 0
        assert "VIRTUAL_ENV" not in os.environ
        assert bin_dir not in os.environ.get("PATH", "")

    def test_venv_with_old_virtual_path(self, tmp_path):
        """deactivate should restore _OLD_VIRTUAL_PATH if present."""
        venv_dir = str(tmp_path / "venv2")
        os.environ["VIRTUAL_ENV"] = venv_dir
        original_path = "/usr/bin:/bin"
        os.environ["_OLD_VIRTUAL_PATH"] = original_path
        os.environ["PATH"] = os.path.join(venv_dir, "bin") + ":" + original_path

        kishi_deactivate(["deactivate"])
        assert os.environ["PATH"] == original_path
        assert "_OLD_VIRTUAL_PATH" not in os.environ


# ---------------------------------------------------------------------------
# plugin
# ---------------------------------------------------------------------------

class TestPlugin:
    def test_no_args_returns_usage(self, capsys):
        """plugin with no subcommand should show usage and return 1."""
        result = kishi_plugin(["plugin"])
        assert result == 1
        captured = capsys.readouterr()
        assert "Usage" in captured.out

    def test_list_empty(self, capsys, tmp_path):
        """plugin list with empty plugin dir should say no plugins."""
        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            result = kishi_plugin(["plugin", "list"])
        assert result == 0
        captured = capsys.readouterr()
        assert "No plugins" in captured.out

    def test_list_shows_installed(self, capsys, tmp_path):
        """plugin list should show names of .py files in plugin dir."""
        plugin_dir = tmp_path / ".kishi" / "plugins"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "weather.py").write_text("# test plugin")
        (plugin_dir / "hello.py").write_text("# test plugin")

        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            result = kishi_plugin(["plugin", "list"])
        assert result == 0
        captured = capsys.readouterr()
        assert "weather" in captured.out
        assert "hello" in captured.out

    def test_remove_nonexistent(self, capsys, tmp_path):
        """plugin remove of non-installed plugin should return 1."""
        plugin_dir = tmp_path / ".kishi" / "plugins"
        plugin_dir.mkdir(parents=True)

        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            result = kishi_plugin(["plugin", "remove", "nonexistent"])
        assert result == 1

    def test_remove_existing(self, tmp_path):
        """plugin remove should delete the .py file."""
        plugin_dir = tmp_path / ".kishi" / "plugins"
        plugin_dir.mkdir(parents=True)
        pf = plugin_dir / "deleteme.py"
        pf.write_text("# delete me")

        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            result = kishi_plugin(["plugin", "remove", "deleteme"])
        assert result == 0
        assert not pf.exists()

    def test_unknown_action(self, capsys, tmp_path):
        """plugin <unknown> should return 1."""
        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            result = kishi_plugin(["plugin", "badaction"])
        assert result == 1


# ---------------------------------------------------------------------------
# neofetch
# ---------------------------------------------------------------------------

class TestNeofetch:
    def test_returns_zero(self):
        """neofetch should always return 0."""
        assert kishi_neofetch(["neofetch"]) == 0

    def test_output_contains_system_info(self, capsys):
        """neofetch should output OS and Kishi version info."""
        kishi_neofetch(["neofetch"])
        captured = capsys.readouterr()
        assert "Kishi" in captured.out
        assert "OS:" in captured.out


# ---------------------------------------------------------------------------
# help
# ---------------------------------------------------------------------------

class TestHelp:
    def test_returns_zero(self):
        assert kishi_help(["help"]) == 0

    def test_output_contains_commands(self, capsys):
        """help should mention basic commands."""
        kishi_help(["help"])
        captured = capsys.readouterr()
        assert "cd" in captured.out
        assert "exit" in captured.out
        assert "export" in captured.out

    def test_help_less_mode(self, capsys):
        """help less should output a short summary."""
        result = kishi_help(["help", "less"])
        assert result == 0
        captured = capsys.readouterr()
        assert "SHORTCUTS" in captured.out


# ---------------------------------------------------------------------------
# BUILTINS_DICT completeness
# ---------------------------------------------------------------------------

class TestBuiltinsDict:
    EXPECTED_COMMANDS = [
        "cd", "pwd", "exit", "q", "clear", "history", "h", "help",
        "jobs", "fg", "bg", "export", "unset", "source", ".",
        "test", "[", "setup", "plugin", "neofetch", "fetch",
        "deactivate",
    ]

    def test_all_expected_commands_registered(self):
        """BUILTINS_DICT should contain all expected command names."""
        for cmd in self.EXPECTED_COMMANDS:
            assert cmd in BUILTINS_DICT, f"Missing builtin: '{cmd}'"

    def test_all_values_are_callable(self):
        """Every entry in BUILTINS_DICT should be callable."""
        for name, fn in BUILTINS_DICT.items():
            if fn is None:
                continue  # dashboard/explore may be None if import fails
            assert callable(fn), f"'{name}' is not callable"
