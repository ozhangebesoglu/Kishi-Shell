# Contributing to Kishi Shell

Thank you for your interest in contributing to Kishi Shell! Every contribution matters — from fixing a typo to implementing a new TUI module.

## Quick Start

```bash
git clone https://github.com/ozhangebesoglu/Kishi-Shell.git
cd Kishi-Shell
python3 -m venv venv
source venv/bin/activate
pip install -e .
kishi
```

## Project Architecture

Kishi Shell follows a classical compiler-pipeline architecture:

```
Input → Lexer → Parser → Expander → Executor
         ↓        ↓         ↓          ↓
      tokens     AST    expanded    fork/exec
                          args      pipelines
```

| Module | Responsibility |
|--------|----------------|
| `kishi/lexer.py` | Tokenizes raw input (state machine) |
| `kishi/parser.py` | Builds AST via recursive descent |
| `kishi/expander.py` | Expands `$VAR`, globs, tilde, `$(cmd)` |
| `kishi/executor.py` | Walks AST, fork/exec, pipes, job control |
| `kishi/builtins.py` | Built-in commands (`cd`, `export`, `test`, etc.) |
| `kishi/state.py` | Centralized global state |
| `kishi/ui.py` | prompt_toolkit session, completion, syntax highlighting |
| `kishi/tui_dashboard.py` | Full-screen system monitor + embedded IDE |
| `kishi/tui_explorer.py` | Dual-pane file explorer with code editor |
| `kishi/tui_fuzzy.py` | Fuzzy history search (Ctrl+R) |

## How to Contribute

### Reporting Bugs

Open an issue with:
- Steps to reproduce
- Expected vs actual behavior
- Your OS and Python version (`python3 --version`)

### Submitting Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/your-feature`)
3. Make your changes
4. Test manually: run `kishi` and verify your changes work
5. Commit with [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat(module): description` — new feature
   - `fix(module): description` — bug fix
   - `refactor(module): description` — code restructuring
   - `docs: description` — documentation only
6. Push and open a Pull Request

### Good First Issues

Look for issues labeled `good-first-issue`. Some areas that welcome contributions:

- **New built-in commands** — Add a new command in `builtins.py` and register it in `BUILTINS_DICT`
- **Icon mappings** — Add file extension → emoji mappings in `tui_explorer.py` `IconProvider`
- **Tab completion** — Enhance context-aware completion in `ui.py` `KishiCompleter`
- **Bottom toolbar hints** — Add more command-specific help text in `ui.py` `get_bottom_toolbar()`

### Adding a Built-in Command

```python
# In kishi/builtins.py

def kishi_mycommand(args):
    """All builtins receive args as a list and return an int exit status."""
    # args[0] is the command name itself
    print("Hello from my command!")
    return 0

# Register it in BUILTINS_DICT at the bottom of the file:
BUILTINS_DICT = {
    # ...existing commands...
    "mycommand": kishi_mycommand,
}
```

## Code Style

- Python 3.8+ compatible
- No external dependencies beyond `prompt_toolkit` and `psutil`
- Keep modules focused — each file has a single responsibility
- Lazy imports for TUI modules (they're optional features)
- All builtins return `int` exit status (0 = success, non-zero = error)

## License

By contributing, you agree that your contributions will be licensed under the [GNU GPLv3](LICENSE).
