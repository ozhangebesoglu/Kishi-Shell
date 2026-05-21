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

    def test_variable_with_path_suffix(self):
        """$VAR/sub/file should expand the $VAR portion, keep the suffix."""
        os.environ["KISHI_DIR"] = "/tmp"
        result = Expander.expand(["$KISHI_DIR/sub/file.txt"])
        assert result == ["/tmp/sub/file.txt"]
        del os.environ["KISHI_DIR"]

    def test_variable_with_extension_suffix(self):
        """$VAR.txt should expand $VAR and keep '.txt'."""
        os.environ["KISHI_BASE"] = "report"
        result = Expander.expand(["$KISHI_BASE.txt"])
        assert result == ["report.txt"]
        del os.environ["KISHI_BASE"]

    def test_bare_undefined_variable_still_dropped(self):
        """Regression: a bare undefined $VAR is still dropped (word removal)."""
        result = Expander.expand(["$NOPE_UNDEFINED_XYZ"])
        assert result == []


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


class TestQuoteExpansion:
    """Tests for the quote-aware expansion (Bug Fix: single-quote variable expansion)."""

    def test_single_quoted_variable_not_expanded(self):
        """Single-quoted $USER should NOT be expanded."""
        from kishi.lexer import QUOTE_SINGLE
        os.environ["KISHI_TEST_Q"] = "expanded"
        result = Expander.expand([QUOTE_SINGLE + "$KISHI_TEST_Q"])
        assert result == ["$KISHI_TEST_Q"]
        del os.environ["KISHI_TEST_Q"]

    def test_double_quoted_variable_expanded(self):
        """Double-quoted $VAR should be expanded."""
        from kishi.lexer import QUOTE_DOUBLE
        os.environ["KISHI_TEST_Q2"] = "hello"
        result = Expander.expand([QUOTE_DOUBLE + "$KISHI_TEST_Q2"])
        assert result == ["hello"]
        del os.environ["KISHI_TEST_Q2"]

    def test_double_quoted_glob_not_expanded(self):
        """Double-quoted *.txt should NOT be glob-expanded."""
        from kishi.lexer import QUOTE_DOUBLE
        result = Expander.expand([QUOTE_DOUBLE + "*.txt"])
        assert result == ["*.txt"]

    def test_single_quoted_glob_not_expanded(self):
        """Single-quoted *.txt should NOT be glob-expanded."""
        from kishi.lexer import QUOTE_SINGLE
        result = Expander.expand([QUOTE_SINGLE + "*.txt"])
        assert result == ["*.txt"]

    def test_unquoted_variable_still_expanded(self):
        """Unquoted $VAR (no prefix) should still be expanded normally."""
        os.environ["KISHI_TEST_Q3"] = "world"
        result = Expander.expand(["$KISHI_TEST_Q3"])
        assert result == ["world"]
        del os.environ["KISHI_TEST_Q3"]


class TestDollarSingleQuoteExpansion:
    """Tests for $'...' tokens in the expander."""

    def test_dollar_single_quoted_not_expanded(self):
        """$'...' tokens should NOT be expanded — escape processing is done by lexer."""
        from kishi.lexer import QUOTE_DOLLAR_SINGLE
        os.environ["KISHI_TEST_DS"] = "expanded"
        result = Expander.expand([QUOTE_DOLLAR_SINGLE + "$KISHI_TEST_DS"])
        assert result == ["$KISHI_TEST_DS"]
        del os.environ["KISHI_TEST_DS"]

    def test_dollar_single_glob_not_expanded(self):
        """$'...' tokens should NOT glob-expand."""
        from kishi.lexer import QUOTE_DOLLAR_SINGLE
        result = Expander.expand([QUOTE_DOLLAR_SINGLE + "*.txt"])
        assert result == ["*.txt"]


class TestBraceExpansion:
    """Bug #6: ${VAR} brace-style variable expansion."""

    def test_brace_variable(self):
        os.environ["KISHI_BR"] = "braced"
        assert Expander.expand(["${KISHI_BR}"]) == ["braced"]
        del os.environ["KISHI_BR"]

    def test_brace_variable_inline(self):
        os.environ["KISHI_BR2"] = "X"
        assert Expander.expand(["a${KISHI_BR2}b"]) == ["aXb"]
        del os.environ["KISHI_BR2"]

    def test_brace_variable_with_suffix(self):
        os.environ["KISHI_BR3"] = "/tmp"
        assert Expander.expand(["${KISHI_BR3}/file"]) == ["/tmp/file"]
        del os.environ["KISHI_BR3"]

    def test_brace_undefined_dropped_when_unquoted(self):
        assert Expander.expand(["${NOPE_BRACE_XYZ}"]) == []


class TestNestedCommandSubstitution:
    """Bug #7: $(...) with balanced/nested parentheses."""

    def test_nested_command_substitution(self):
        assert Expander.expand(["$(echo $(echo deep))"]) == ["deep"]

    def test_command_substitution_with_inner_parens(self):
        # The whole balanced group is handed to the shell intact.
        assert Expander.expand(["$(echo hi)"]) == ["hi"]


class TestDoubleQuotedEmptyVar:
    """Bug #9: double-quoted undefined var yields '' (not dropped)."""

    def test_double_quoted_undefined_yields_empty_string(self):
        from kishi.lexer import QUOTE_DOUBLE
        assert Expander.expand([QUOTE_DOUBLE + "$UNDEFINED_DQ_XYZ"]) == [""]

    def test_double_quoted_brace_undefined_yields_empty_string(self):
        from kishi.lexer import QUOTE_DOUBLE
        assert Expander.expand([QUOTE_DOUBLE + "${UNDEFINED_DQ_XYZ}"]) == [""]

    def test_unquoted_undefined_still_dropped(self):
        # Regression: unquoted undefined var is still removed (word removal).
        assert Expander.expand(["$UNDEFINED_DQ_XYZ"]) == []


