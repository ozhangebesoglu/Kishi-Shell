import pytest
from kishi.lexer import Tokenizer
from kishi.parser import (
    Parser, CommandNode, PipelineNode, LogicNode,
    SequenceNode, IfNode, WhileNode, ForNode, FunctionDefNode,
)


def parse(cmd):
    tokens = Tokenizer.tokenize(cmd)
    return Parser.parse(tokens)


class TestSimpleCommands:
    def test_single_command(self):
        ast = parse("ls -la")
        assert isinstance(ast, SequenceNode)
        assert len(ast.statements) == 1
        pipe = ast.statements[0]
        assert isinstance(pipe, PipelineNode)
        assert len(pipe.commands) == 1
        assert pipe.commands[0].args == ["ls", "-la"]

    def test_empty_returns_none(self):
        assert Parser.parse([]) is None


class TestPipeline:
    def test_two_commands(self):
        ast = parse("ls | grep foo")
        pipe = ast.statements[0]
        assert isinstance(pipe, PipelineNode)
        assert len(pipe.commands) == 2
        assert pipe.commands[0].args == ["ls"]
        assert pipe.commands[1].args == ["grep", "foo"]

    def test_three_commands(self):
        ast = parse("cat file | grep error | wc -l")
        pipe = ast.statements[0]
        assert len(pipe.commands) == 3

    def test_background(self):
        ast = parse("sleep 10 &")
        pipe = ast.statements[0]
        assert isinstance(pipe, PipelineNode)
        assert pipe.is_background is True


class TestRedirection:
    def test_stdout(self):
        ast = parse("echo hi > out.txt")
        cmd = ast.statements[0].commands[0]
        assert cmd.out_file == "out.txt"
        assert cmd.out_append is False

    def test_stdout_append(self):
        ast = parse("echo hi >> out.txt")
        cmd = ast.statements[0].commands[0]
        assert cmd.out_file == "out.txt"
        assert cmd.out_append is True

    def test_stdin(self):
        ast = parse("sort < input.txt")
        cmd = ast.statements[0].commands[0]
        assert cmd.in_file == "input.txt"

    def test_stderr(self):
        ast = parse("cmd 2> err.txt")
        cmd = ast.statements[0].commands[0]
        assert cmd.err_file == "err.txt"

    def test_stderr_to_stdout(self):
        ast = parse("cmd 2>&1")
        cmd = ast.statements[0].commands[0]
        assert cmd.err_to_out is True


class TestLogicOperators:
    def test_and(self):
        ast = parse("cmd1 && cmd2")
        node = ast.statements[0]
        assert isinstance(node, LogicNode)
        assert node.operator == "&&"

    def test_or(self):
        ast = parse("cmd1 || cmd2")
        node = ast.statements[0]
        assert isinstance(node, LogicNode)
        assert node.operator == "||"

    def test_chained(self):
        ast = parse("a && b || c")
        node = ast.statements[0]
        assert isinstance(node, LogicNode)
        assert node.operator == "||"
        assert isinstance(node.left, LogicNode)
        assert node.left.operator == "&&"


class TestSequence:
    def test_semicolons(self):
        ast = parse("cmd1 ; cmd2 ; cmd3")
        assert isinstance(ast, SequenceNode)
        assert len(ast.statements) == 3


class TestControlFlow:
    def test_if_then_fi(self):
        ast = parse("if test -f foo then echo yes fi")
        assert len(ast.statements) == 1
        node = ast.statements[0]
        assert isinstance(node, IfNode)

    def test_if_else(self):
        ast = parse("if test -f foo then echo yes else echo no fi")
        node = ast.statements[0]
        assert isinstance(node, IfNode)
        assert node.else_ast is not None

    def test_while(self):
        ast = parse("while test -f lock do sleep 1 done")
        node = ast.statements[0]
        assert isinstance(node, WhileNode)

    def test_for(self):
        ast = parse("for i in a b c do echo $i done")
        node = ast.statements[0]
        assert isinstance(node, ForNode)
        assert node.var_name == "i"
        assert node.iter_items == ["a", "b", "c"]


class TestFunctionDef:
    def test_function_definition(self):
        ast = parse("greet() { echo hello ; }")
        node = ast.statements[0]
        assert isinstance(node, FunctionDefNode)
        assert node.func_name == "greet"
