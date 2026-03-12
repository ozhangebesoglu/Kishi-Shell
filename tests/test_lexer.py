import pytest
from kishi.lexer import Tokenizer


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
        assert Tokenizer.tokenize("echo 'hello world'") == ["echo", "hello world"]

    def test_double_quotes(self):
        assert Tokenizer.tokenize('echo "hello world"') == ["echo", "hello world"]

    def test_nested_quotes(self):
        assert Tokenizer.tokenize("""echo "it's fine" """) == ["echo", "it's fine"]

    def test_unclosed_quote_raises(self):
        with pytest.raises(ValueError):
            Tokenizer.tokenize("echo 'unclosed")

    def test_empty_quotes(self):
        assert Tokenizer.tokenize("echo ''") == ["echo"]

    def test_adjacent_quoted_sections(self):
        assert Tokenizer.tokenize("echo 'hello'' world'") == ["echo", "hello world"]


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
