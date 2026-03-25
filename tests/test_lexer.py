import pytest
from kishi.lexer import Tokenizer, QUOTE_SINGLE, QUOTE_DOUBLE, QUOTE_DOLLAR_SINGLE


class TestBasicTokenization:
    def test_simple_command(self):
        assert Tokenizer.tokenize("ls -la") == ["ls", "-la"]

    def test_multiple_args(self):
        assert Tokenizer.tokenize("echo hello world") == ["echo", "hello", "world"]

    def test_empty_string(self):
        assert Tokenizer.tokenize("") == []

    def test_whitespace_only(self):
        assert Tokenizer.tokenize("   ") == []


class TestQuoteHandling:
    def test_single_quotes(self):
        assert Tokenizer.tokenize("echo 'hello world'") == ["echo", QUOTE_SINGLE + "hello world"]

    def test_double_quotes(self):
        assert Tokenizer.tokenize('echo "hello world"') == ["echo", QUOTE_DOUBLE + "hello world"]

    def test_nested_quotes(self):
        assert Tokenizer.tokenize("""echo "it's fine" """) == ["echo", QUOTE_DOUBLE + "it's fine"]

    def test_unclosed_quote_raises(self):
        with pytest.raises(ValueError):
            Tokenizer.tokenize("echo 'unclosed")

    def test_empty_quotes(self):
        assert Tokenizer.tokenize("echo ''") == ["echo"]

    def test_adjacent_quoted_sections(self):
        assert Tokenizer.tokenize("echo 'hello'' world'") == ["echo", QUOTE_SINGLE + "hello world"]


class TestEscapeHandling:
    def test_escaped_space(self):
        assert Tokenizer.tokenize(r"echo hello\ world") == ["echo", "hello world"]

    def test_escaped_quote(self):
        assert Tokenizer.tokenize(r"echo \"hello\"") == ["echo", '"hello"']


class TestOperators:
    def test_pipe(self):
        assert Tokenizer.tokenize("ls | grep foo") == ["ls", "|", "grep", "foo"]

    def test_double_pipe(self):
        assert Tokenizer.tokenize("cmd1 || cmd2") == ["cmd1", "||", "cmd2"]

    def test_and(self):
        assert Tokenizer.tokenize("cmd1 && cmd2") == ["cmd1", "&&", "cmd2"]

    def test_semicolon(self):
        assert Tokenizer.tokenize("cmd1 ; cmd2") == ["cmd1", ";", "cmd2"]

    def test_background(self):
        assert Tokenizer.tokenize("sleep 10 &") == ["sleep", "10", "&"]

    def test_ampersand_in_url(self):
        result = Tokenizer.tokenize("curl http://example.com?a=1&b=2")
        assert result == ["curl", "http://example.com?a=1&b=2"]


class TestRedirection:
    def test_stdout_redirect(self):
        assert Tokenizer.tokenize("echo hi > out.txt") == ["echo", "hi", ">", "out.txt"]

    def test_stdout_append(self):
        assert Tokenizer.tokenize("echo hi >> out.txt") == ["echo", "hi", ">>", "out.txt"]

    def test_stdin_redirect(self):
        assert Tokenizer.tokenize("sort < input.txt") == ["sort", "<", "input.txt"]

    def test_stderr_redirect(self):
        assert Tokenizer.tokenize("cmd 2> err.txt") == ["cmd", "2>", "err.txt"]

    def test_stderr_append(self):
        assert Tokenizer.tokenize("cmd 2>> err.txt") == ["cmd", "2>>", "err.txt"]

    def test_stderr_to_stdout(self):
        assert Tokenizer.tokenize("cmd 2>&1") == ["cmd", "2>&1"]


class TestBraces:
    def test_function_body(self):
        assert Tokenizer.tokenize("{ echo hi ; }") == ["{", "echo", "hi", ";", "}"]


class TestComplexCommands:
    def test_pipeline_with_redirect(self):
        result = Tokenizer.tokenize("cat file.txt | grep error > out.log")
        assert result == ["cat", "file.txt", "|", "grep", "error", ">", "out.log"]

    def test_logic_chain(self):
        result = Tokenizer.tokenize("make && make install || echo failed")
        assert result == ["make", "&&", "make", "install", "||", "echo", "failed"]


class TestQuoteMetadata:
    """Tests for the quote-type sentinel prefix feature (Bug Fix: single-quote expansion)."""

    def test_single_quote_prefix_on_variable(self):
        """echo '$USER' should NOT expand — token must have QUOTE_SINGLE prefix."""
        result = Tokenizer.tokenize("echo '$USER'")
        assert result == ["echo", QUOTE_SINGLE + "$USER"]

    def test_double_quote_prefix_on_variable(self):
        """echo "$USER" should expand variable — token must have QUOTE_DOUBLE prefix."""
        result = Tokenizer.tokenize('echo "$USER"')
        assert result == ["echo", QUOTE_DOUBLE + "$USER"]

    def test_unquoted_no_prefix(self):
        """echo $USER should have no prefix — full expansion."""
        result = Tokenizer.tokenize("echo $USER")
        assert result == ["echo", "$USER"]

    def test_single_quote_preserves_special_chars(self):
        """Single quotes should preserve all special characters with prefix."""
        result = Tokenizer.tokenize("echo '*.txt $HOME ~/'")
        assert result == ["echo", QUOTE_SINGLE + "*.txt $HOME ~/"]

    def test_double_quote_preserves_glob(self):
        """Double quotes should preserve glob characters with prefix."""
        result = Tokenizer.tokenize('echo "*.txt"')
        assert result == ["echo", QUOTE_DOUBLE + "*.txt"]


class TestDollarSingleQuote:
    """Tests for $'...' ANSI-C quoting (POSIX 2024)."""

    def test_newline_escape(self):
        result = Tokenizer.tokenize("echo $'hello\\nworld'")
        assert result == ["echo", QUOTE_DOLLAR_SINGLE + "hello\nworld"]

    def test_tab_escape(self):
        result = Tokenizer.tokenize("echo $'col1\\tcol2'")
        assert result == ["echo", QUOTE_DOLLAR_SINGLE + "col1\tcol2"]

    def test_backslash_escape(self):
        result = Tokenizer.tokenize("echo $'back\\\\slash'")
        assert result == ["echo", QUOTE_DOLLAR_SINGLE + "back\\slash"]

    def test_apostrophe_escape(self):
        result = Tokenizer.tokenize("echo $'it\\'s'")
        assert result == ["echo", QUOTE_DOLLAR_SINGLE + "it's"]

    def test_hex_escape(self):
        result = Tokenizer.tokenize("echo $'\\x41\\x42'")
        assert result == ["echo", QUOTE_DOLLAR_SINGLE + "AB"]

    def test_unicode_escape(self):
        result = Tokenizer.tokenize("echo $'\\u00e9'")
        assert result == ["echo", QUOTE_DOLLAR_SINGLE + "é"]

    def test_octal_escape(self):
        result = Tokenizer.tokenize("echo $'\\0101'")
        assert result == ["echo", QUOTE_DOLLAR_SINGLE + "A"]

    def test_sentinel_prefix(self):
        """$'...' tokens must carry QUOTE_DOLLAR_SINGLE prefix."""
        result = Tokenizer.tokenize("echo $'test'")
        assert result[1].startswith(QUOTE_DOLLAR_SINGLE)

    def test_unclosed_raises(self):
        with pytest.raises(ValueError):
            Tokenizer.tokenize("echo $'unclosed")

    def test_variable_not_expanded(self):
        """$'...' should not expand variables — the $ inside is literal."""
        result = Tokenizer.tokenize("echo $'$USER'")
        # The $USER stays literal in the token (escape processing doesn't touch $)
        assert result == ["echo", QUOTE_DOLLAR_SINGLE + "$USER"]

