"""
Strict tests for kishi/executor.py
Tests focus on AST execution logic, not OS-level fork/exec.
"""
import os
import pytest
from unittest.mock import patch, MagicMock

from kishi import state
from kishi.parser import (
    SequenceNode, PipelineNode, CommandNode, LogicNode,
    IfNode, WhileNode, ForNode, FunctionDefNode,
)
from kishi.executor import execute_ast, execute_pipeline, process_command_line, get_close_match_suggestion


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_state():
    """Reset global state before every test to ensure isolation."""
    old_local = state.LOCAL_VARS.copy()
    old_aliases = state.ALIASES.copy()
    old_functions = state.FUNCTIONS.copy()
    old_builtins = state.BUILTINS.copy()
    old_session = state.KISHI_SESSION

    yield

    state.LOCAL_VARS.clear()
    state.LOCAL_VARS.update(old_local)
    state.ALIASES.clear()
    state.ALIASES.update(old_aliases)
    state.FUNCTIONS.clear()
    state.FUNCTIONS.update(old_functions)
    state.BUILTINS.clear()
    state.BUILTINS.update(old_builtins)
    state.KISHI_SESSION = old_session


def _make_pipeline(*arg_lists, is_bg=False):
    """Helper: create a PipelineNode from argument lists."""
    pipe = PipelineNode()
    pipe.is_background = is_bg
    for args in arg_lists:
        cmd = CommandNode()
        cmd.args = list(args)
        pipe.commands.append(cmd)
    return pipe


def _make_sequence(*nodes):
    """Helper: wrap nodes in a SequenceNode."""
    seq = SequenceNode()
    seq.statements = list(nodes)
    return seq


# ---------------------------------------------------------------------------
# Variable Assignment (VAR=value)
# ---------------------------------------------------------------------------

class TestVariableAssignment:
    def test_single_assignment(self):
        """VAR=hello should set LOCAL_VARS['VAR'] = 'hello'."""
        pipe = _make_pipeline(["FOO=hello"])
        result = execute_pipeline(pipe)
        assert result == 0
        assert state.LOCAL_VARS["FOO"] == "hello"

    def test_multiple_assignments(self):
        """A=1 B=2 should set both variables."""
        pipe = _make_pipeline(["A=1", "B=2"])
        result = execute_pipeline(pipe)
        assert result == 0
        assert state.LOCAL_VARS["A"] == "1"
        assert state.LOCAL_VARS["B"] == "2"

    def test_overwrite_existing(self):
        """Assigning to an existing variable should overwrite it."""
        state.LOCAL_VARS["X"] = "old"
        pipe = _make_pipeline(["X=new"])
        execute_pipeline(pipe)
        assert state.LOCAL_VARS["X"] == "new"

    def test_value_with_equals(self):
        """VAR=a=b should store 'a=b' as the value."""
        pipe = _make_pipeline(["KEY=a=b"])
        execute_pipeline(pipe)
        assert state.LOCAL_VARS["KEY"] == "a=b"


# ---------------------------------------------------------------------------
# Builtin Dispatch (single-command pipeline)
# ---------------------------------------------------------------------------

class TestBuiltinDispatch:
    def test_builtin_called_with_correct_args(self):
        """When a builtin is found, it should be called and its return value used."""
        mock_fn = MagicMock(return_value=42)
        state.BUILTINS["mockbuiltin"] = mock_fn

        pipe = _make_pipeline(["mockbuiltin", "arg1", "arg2"])
        result = execute_pipeline(pipe)

        mock_fn.assert_called_once_with(["mockbuiltin", "arg1", "arg2"])
        assert result == 42

    def test_builtin_with_env_prefix(self):
        """ENV=val builtin should set env then call builtin."""
        mock_fn = MagicMock(return_value=0)
        state.BUILTINS["mybuiltin"] = mock_fn

        pipe = _make_pipeline(["ENVKEY=envval", "mybuiltin", "x"])
        result = execute_pipeline(pipe)

        # The builtin should be called
        mock_fn.assert_called_once_with(["mybuiltin", "x"])
        assert result == 0

    def test_empty_pipeline_returns_zero(self):
        """An empty PipelineNode should return 0."""
        pipe = PipelineNode()
        assert execute_pipeline(pipe) == 0


# ---------------------------------------------------------------------------
# Function Definition and Call
# ---------------------------------------------------------------------------

class TestFunctionDefinitionAndCall:
    def test_function_def_registers(self):
        """FunctionDefNode should store body AST in FUNCTIONS."""
        body = _make_sequence(_make_pipeline(["echo", "hello"]))
        func_def = FunctionDefNode("greet", body)
        result = execute_ast(func_def)

        assert result == 0
        assert "greet" in state.FUNCTIONS
        assert state.FUNCTIONS["greet"] is body

    def test_function_call_executes_body(self):
        """Calling a defined function should execute its body AST."""
        # Register a function that calls a mock builtin
        mock_fn = MagicMock(return_value=0)
        state.BUILTINS["_testcmd"] = mock_fn

        body = _make_sequence(_make_pipeline(["_testcmd", "from_func"]))
        state.FUNCTIONS["myfunc"] = body

        pipe = _make_pipeline(["myfunc"])
        execute_pipeline(pipe)

        mock_fn.assert_called_once()

    def test_function_call_passes_args(self):
        """Function args should be accessible as $1, $2, etc."""
        captured = {}

        def capture_fn(args):
            captured["1"] = state.LOCAL_VARS.get("1", None)
            captured["2"] = state.LOCAL_VARS.get("2", None)
            return 0

        state.BUILTINS["_capture"] = capture_fn
        body = _make_sequence(_make_pipeline(["_capture"]))
        state.FUNCTIONS["paramfunc"] = body

        pipe = _make_pipeline(["paramfunc", "alpha", "beta"])
        execute_pipeline(pipe)

        assert captured["1"] == "alpha"
        assert captured["2"] == "beta"

    def test_function_args_restored_after_call(self):
        """Positional params should be restored after function returns."""
        state.LOCAL_VARS["1"] = "original"

        def noop(args):
            return 0

        state.BUILTINS["_noop"] = noop
        body = _make_sequence(_make_pipeline(["_noop"]))
        state.FUNCTIONS["tempfunc"] = body

        pipe = _make_pipeline(["tempfunc", "temp_arg"])
        execute_pipeline(pipe)

        assert state.LOCAL_VARS["1"] == "original"


# ---------------------------------------------------------------------------
# Logic Operators (&&, ||, &)
# ---------------------------------------------------------------------------

class TestLogicOperators:
    def _status_pipeline(self, return_code):
        """Create a pipeline that returns a specific exit code via a mock builtin."""
        name = f"_status{return_code}"
        state.BUILTINS[name] = lambda args: return_code
        return _make_pipeline([name])

    def test_and_both_succeed(self):
        """cmd1 && cmd2 — both succeed, result should be 0."""
        node = LogicNode(self._status_pipeline(0), "&&", self._status_pipeline(0))
        assert execute_ast(node) == 0

    def test_and_left_fails(self):
        """cmd1 && cmd2 — left fails, right should NOT execute."""
        right_mock = MagicMock(return_value=0)
        state.BUILTINS["_right"] = right_mock

        left = self._status_pipeline(1)
        right = _make_pipeline(["_right"])
        node = LogicNode(left, "&&", right)
        result = execute_ast(node)

        assert result == 1
        right_mock.assert_not_called()

    def test_or_left_succeeds(self):
        """cmd1 || cmd2 — left succeeds, right should NOT execute."""
        right_mock = MagicMock(return_value=0)
        state.BUILTINS["_right_or"] = right_mock

        left = self._status_pipeline(0)
        right = _make_pipeline(["_right_or"])
        node = LogicNode(left, "||", right)
        result = execute_ast(node)

        assert result == 0
        right_mock.assert_not_called()

    def test_or_left_fails(self):
        """cmd1 || cmd2 — left fails, right should execute."""
        right_mock = MagicMock(return_value=5)
        state.BUILTINS["_right_or2"] = right_mock

        left = self._status_pipeline(1)
        right = _make_pipeline(["_right_or2"])
        node = LogicNode(left, "||", right)
        result = execute_ast(node)

        assert result == 5
        right_mock.assert_called_once()

    def test_and_chained(self):
        """a && b && c — all succeed."""
        inner = LogicNode(self._status_pipeline(0), "&&", self._status_pipeline(0))
        outer = LogicNode(inner, "&&", self._status_pipeline(0))
        assert execute_ast(outer) == 0

    def test_and_chained_middle_fails(self):
        """a && b && c — b fails, c should not execute."""
        right_mock = MagicMock(return_value=0)
        state.BUILTINS["_chain_c"] = right_mock

        inner = LogicNode(self._status_pipeline(0), "&&", self._status_pipeline(2))
        outer = LogicNode(inner, "&&", _make_pipeline(["_chain_c"]))
        result = execute_ast(outer)

        assert result == 2
        right_mock.assert_not_called()

    def test_ampersand_runs_both(self):
        """cmd1 & cmd2 — both sides should execute."""
        left_mock = MagicMock(return_value=0)
        right_mock = MagicMock(return_value=7)
        state.BUILTINS["_amp_left"] = left_mock
        state.BUILTINS["_amp_right"] = right_mock

        left = _make_pipeline(["_amp_left"])
        right = _make_pipeline(["_amp_right"])
        node = LogicNode(left, "&", right)
        result = execute_ast(node)

        left_mock.assert_called_once()
        right_mock.assert_called_once()
        assert result == 7


# ---------------------------------------------------------------------------
# Sequence Execution
# ---------------------------------------------------------------------------

class TestSequenceExecution:
    def test_returns_last_status(self):
        """Sequence should return the exit code of the last statement."""
        state.BUILTINS["_s0"] = lambda args: 0
        state.BUILTINS["_s3"] = lambda args: 3

        seq = _make_sequence(
            _make_pipeline(["_s0"]),
            _make_pipeline(["_s3"]),
        )
        assert execute_ast(seq) == 3

    def test_all_commands_execute(self):
        """Every statement in a sequence should execute, regardless of exit codes."""
        calls = []
        state.BUILTINS["_track1"] = lambda args: (calls.append(1), 0)[1]
        state.BUILTINS["_track2"] = lambda args: (calls.append(2), 1)[1]
        state.BUILTINS["_track3"] = lambda args: (calls.append(3), 0)[1]

        seq = _make_sequence(
            _make_pipeline(["_track1"]),
            _make_pipeline(["_track2"]),
            _make_pipeline(["_track3"]),
        )
        execute_ast(seq)
        assert calls == [1, 2, 3]

    def test_empty_sequence(self):
        """Empty sequence should return 0."""
        seq = SequenceNode()
        seq.statements = []
        assert execute_ast(seq) == 0


# ---------------------------------------------------------------------------
# If Node
# ---------------------------------------------------------------------------

class TestIfNode:
    def test_condition_true_runs_then(self):
        """If condition is 0 (true), then branch should execute."""
        state.BUILTINS["_true"] = lambda args: 0
        then_mock = MagicMock(return_value=0)
        state.BUILTINS["_then"] = then_mock

        cond = _make_sequence(_make_pipeline(["_true"]))
        then_ast = _make_sequence(_make_pipeline(["_then"]))
        node = IfNode(cond, then_ast, [], None)
        execute_ast(node)

        then_mock.assert_called_once()

    def test_condition_false_runs_else(self):
        """If condition is non-zero (false), else branch should execute."""
        state.BUILTINS["_false"] = lambda args: 1
        else_mock = MagicMock(return_value=0)
        state.BUILTINS["_else"] = else_mock

        cond = _make_sequence(_make_pipeline(["_false"]))
        then_ast = _make_sequence(_make_pipeline(["_true_unreachable"]))
        else_ast = _make_sequence(_make_pipeline(["_else"]))
        node = IfNode(cond, then_ast, [], else_ast)
        execute_ast(node)

        else_mock.assert_called_once()

    def test_elif_chain(self):
        """Elif should be evaluated when if-condition is false."""
        state.BUILTINS["_f"] = lambda args: 1
        state.BUILTINS["_t"] = lambda args: 0
        elif_mock = MagicMock(return_value=0)
        state.BUILTINS["_elif_body"] = elif_mock

        cond = _make_sequence(_make_pipeline(["_f"]))
        then_ast = _make_sequence(_make_pipeline(["_unreachable"]))

        elif_cond = _make_sequence(_make_pipeline(["_t"]))
        elif_body = _make_sequence(_make_pipeline(["_elif_body"]))

        node = IfNode(cond, then_ast, [(elif_cond, elif_body)], None)
        execute_ast(node)

        elif_mock.assert_called_once()

    def test_no_else_returns_zero(self):
        """If condition false and no else, return 0."""
        state.BUILTINS["_f2"] = lambda args: 1
        cond = _make_sequence(_make_pipeline(["_f2"]))
        then_ast = _make_sequence(_make_pipeline(["_unreachable2"]))
        node = IfNode(cond, then_ast, [], None)
        assert execute_ast(node) == 0


# ---------------------------------------------------------------------------
# For Node
# ---------------------------------------------------------------------------

class TestForNode:
    def test_iterates_items(self):
        """For loop should iterate over items and set loop variable."""
        collected = []

        def collector(args):
            collected.append(state.LOCAL_VARS.get("i"))
            return 0

        state.BUILTINS["_collect"] = collector
        body = _make_sequence(_make_pipeline(["_collect"]))
        node = ForNode("i", ["a", "b", "c"], body)
        execute_ast(node)

        assert collected == ["a", "b", "c"]

    def test_loop_var_set_after_loop(self):
        """After loop completes, the variable should hold the last value."""
        state.BUILTINS["_noop2"] = lambda args: 0
        body = _make_sequence(_make_pipeline(["_noop2"]))
        node = ForNode("loopvar", ["x", "y", "z"], body)
        execute_ast(node)

        assert state.LOCAL_VARS["loopvar"] == "z"

    def test_empty_items(self):
        """For loop with empty items should not execute body."""
        mock = MagicMock(return_value=0)
        state.BUILTINS["_empty_loop"] = mock
        body = _make_sequence(_make_pipeline(["_empty_loop"]))
        node = ForNode("i", [], body)
        execute_ast(node)

        mock.assert_not_called()


# ---------------------------------------------------------------------------
# While Node
# ---------------------------------------------------------------------------

class TestWhileNode:
    def test_loops_until_condition_false(self):
        """While should loop until condition returns non-zero."""
        counter = {"n": 3}

        def cond_fn(args):
            if counter["n"] > 0:
                return 0  # true
            return 1  # false

        def body_fn(args):
            counter["n"] -= 1
            return 0

        state.BUILTINS["_while_cond"] = cond_fn
        state.BUILTINS["_while_body"] = body_fn

        cond = _make_sequence(_make_pipeline(["_while_cond"]))
        body = _make_sequence(_make_pipeline(["_while_body"]))
        node = WhileNode(cond, body)
        execute_ast(node)

        assert counter["n"] == 0

    def test_false_from_start(self):
        """While with immediately false condition should not execute body."""
        state.BUILTINS["_always_false"] = lambda args: 1
        body_mock = MagicMock(return_value=0)
        state.BUILTINS["_while_body_skip"] = body_mock

        cond = _make_sequence(_make_pipeline(["_always_false"]))
        body = _make_sequence(_make_pipeline(["_while_body_skip"]))
        node = WhileNode(cond, body)
        execute_ast(node)

        body_mock.assert_not_called()


# ---------------------------------------------------------------------------
# execute_ast edge cases
# ---------------------------------------------------------------------------

class TestExecuteAstEdgeCases:
    def test_none_returns_zero(self):
        """execute_ast(None) should return 0."""
        assert execute_ast(None) == 0

    def test_unknown_node_returns_zero(self):
        """An unrecognized node type should return 0 (fallthrough)."""

        class UnknownNode:
            pass

        assert execute_ast(UnknownNode()) == 0


# ---------------------------------------------------------------------------
# Alias Expansion in Pipeline
# ---------------------------------------------------------------------------

class TestAliasExpansion:
    def test_alias_expanded_before_execution(self):
        """Aliases should be expanded to their full command in pipeline."""
        mock_fn = MagicMock(return_value=0)
        state.BUILTINS["ls"] = mock_fn
        state.ALIASES["ll"] = "ls -la"

        pipe = _make_pipeline(["ll", "/tmp"])
        execute_pipeline(pipe)

        # After alias expansion, should be called with ["ls", "-la", "/tmp"]
        mock_fn.assert_called_once_with(["ls", "-la", "/tmp"])


# ---------------------------------------------------------------------------
# process_command_line
# ---------------------------------------------------------------------------

class TestProcessCommandLine:
    def test_empty_input(self):
        """Empty or whitespace-only input should return without error."""
        process_command_line("")
        process_command_line("   ")

    def test_whitespace_only_input(self):
        """Whitespace-only input should return without error."""
        process_command_line("     ")
        process_command_line("\t  ")

    def test_valid_builtin_via_process(self):
        """process_command_line should invoke builtins correctly."""
        mock_fn = MagicMock(return_value=0)
        state.BUILTINS["_pcl_test"] = mock_fn

        process_command_line("_pcl_test arg1")
        mock_fn.assert_called_once()


# ---------------------------------------------------------------------------
# get_close_match_suggestion
# ---------------------------------------------------------------------------

class TestGetCloseMatchSuggestion:
    def test_returns_suggestion_for_close_match(self):
        """Should suggest a similar command name."""
        state.SYSTEM_COMMANDS = ["python", "pip", "git", "grep"]
        result = get_close_match_suggestion("pythn")
        assert "python" in result

    def test_returns_empty_for_no_match(self):
        """Should return empty string when nothing matches."""
        state.SYSTEM_COMMANDS = ["python", "pip"]
        result = get_close_match_suggestion("zzzzzzz")
        assert result == ""

    def test_returns_empty_when_no_system_commands(self):
        """Should return empty when SYSTEM_COMMANDS is empty."""
        state.SYSTEM_COMMANDS = []
        result = get_close_match_suggestion("anything")
        assert result == ""
