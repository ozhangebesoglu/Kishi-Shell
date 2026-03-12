import os
import pytest
from kishi.expander import Expander
from kishi import state


class TestVariableExpansion:
    def test_env_variable(self):
        os.environ["KISHI_TEST_VAR"] = "hello"
        result = Expander.expand(["$KISHI_TEST_VAR"])
        assert result == ["hello"]
        del os.environ["KISHI_TEST_VAR"]

    def test_local_variable(self):
        state.LOCAL_VARS["myvar"] = "world"
        result = Expander.expand(["$myvar"])
        assert result == ["world"]
        del state.LOCAL_VARS["myvar"]

    def test_inline_variable(self):
        os.environ["KISHI_NAME"] = "kishi"
        result = Expander.expand(["hello_$KISHI_NAME"])
        assert result == ["hello_kishi"]
        del os.environ["KISHI_NAME"]

    def test_undefined_variable(self):
        result = Expander.expand(["$NONEXISTENT_VAR_XYZ"])
        assert result == []

    def test_alias_in_inline_expansion(self):
        state.ALIASES["myalias"] = "expanded"
        result = Expander.expand(["prefix_$myalias"])
        assert result == ["prefix_expanded"]
        del state.ALIASES["myalias"]

    def test_local_takes_precedence(self):
        state.LOCAL_VARS["pvar"] = "local"
        os.environ["pvar"] = "env"
        result = Expander.expand(["$pvar"])
        assert result == ["local"]
        del state.LOCAL_VARS["pvar"]
        del os.environ["pvar"]


class TestTildeExpansion:
    def test_tilde(self):
        result = Expander.expand(["~"])
        assert result == [os.path.expanduser("~")]

    def test_tilde_slash(self):
        result = Expander.expand(["~/Documents"])
        assert result == [os.path.expanduser("~/Documents")]

    def test_no_tilde_midword(self):
        result = Expander.expand(["foo~bar"])
        assert result == ["foo~bar"]


class TestGlobExpansion:
    def test_glob_star(self, tmp_path):
        (tmp_path / "a.txt").touch()
        (tmp_path / "b.txt").touch()
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        result = Expander.expand(["*.txt"])
        os.chdir(old_cwd)
        assert "a.txt" in result
        assert "b.txt" in result

    def test_no_match_keeps_literal(self):
        result = Expander.expand(["*.nonexistent_extension_xyz"])
        assert result == ["*.nonexistent_extension_xyz"]


class TestCommandSubstitution:
    def test_dollar_paren(self):
        result = Expander.expand(["$(echo hello)"])
        assert result == ["hello"]

    def test_backtick(self):
        result = Expander.expand(["`echo world`"])
        assert result == ["world"]

    def test_failed_command(self):
        result = Expander.expand(["$(false)"])
        assert result == [""]


class TestPassthrough:
    def test_plain_args(self):
        result = Expander.expand(["ls", "-la", "/tmp"])
        assert result == ["ls", "-la", "/tmp"]
