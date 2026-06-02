#  Kishi Shell (v2.0.2.3)

[![CI](https://github.com/ozhangebesoglu/Kishi-Shell/actions/workflows/ci.yml/badge.svg)](https://github.com/ozhangebesoglu/Kishi-Shell/actions/workflows/ci.yml)

> **If you like this project, please give it a ⭐ star on [GitHub](https://github.com/ozhangebesoglu/Kishi-Shell) and vote on [AUR](https://aur.archlinux.org/packages/kishi-shell)! Your support helps the project grow.**

[![asciicast](https://asciinema.org/a/LQ7jQXtlGHgNoEVa.svg)](https://asciinema.org/a/LQ7jQXtlGHgNoEVa)

Kishi Shell is a next-generation command line developed 100% in Python that transforms into a full-fledged **Terminal User Interface (TUI) Operating System** without requiring any external software (Go, C) or plugins. It combines the traditional Bash command set with modern *IDE (Code Editor)* and *System Monitor* features.

##  Installation & Running

### Option 1: Install via AUR (Arch Linux) — Recommended
```bash
yay -S kishi-shell
```

### Option 2: Install from Source
```bash
git clone https://github.com/ozhangebesoglu/Kishi-Shell.git
cd Kishi-Shell
chmod +x install.sh
./install.sh
```
The installer will try `pip3 install .` first. If your system uses PEP 668 protection, it will offer you to create a **virtual environment** (recommended) or use `--break-system-packages`.

### Option 3: Install via pip (PyPI)
```bash
pip install --upgrade kishi-shell           # Core shell only (~30 KB)
pip install --upgrade "kishi-shell[krep]"   # + numpy/scipy for Krep AI's LSA model
```

The base install gives you the full Kishi Shell + the keyword-based `krep`
engine. The `[krep]` optional extra adds `numpy + scipy` for the dictionary-free
LSA model (`krep --learn PATH` and friends). Most shell users never need this.

Type `kishi` in your terminal to launch Kishi Shell. Type `exit` to return to your default shell.

---

##  How the Installer Works

### Linux (`install.sh`)
The installer automatically detects your distro (Arch, Fedora, Debian/Ubuntu, openSUSE, Void, etc.) and:
1. Installs system dependencies (`python3`, `pip`, `prompt_toolkit`, `psutil`) via your package manager
2. Runs `pip3 install .` — if PEP 668 protection blocks it, you can choose between `--break-system-packages` or a virtual environment (`~/.kishi-venv`)
3. Verifies the `kishi` command is available in your PATH

### Windows (`install.bat`)
1. Runs `pip install .` (tries `pip`, `python -m pip`, `python3 -m pip`)
2. Auto-detects the Python Scripts directory and adds it to your user PATH
3. You can always run with `python -m kishi` as a fallback

---

##  Using Kishi as Your Login Shell (Optional)

> **Note:** Kishi works perfectly as a regular shell — just type `kishi` to launch it. Setting it as a login shell is entirely optional and only needed if you want Kishi to be your default system shell.

If you want to set Kishi as your login shell:

```bash
# 1. Register kishi as an allowed shell
kishi --setup
# or manually:
echo $(which kishi) | sudo tee -a /etc/shells

# 2. Set as your default login shell
chsh -s $(which kishi)

# To revert back to bash at any time:
chsh -s /bin/bash
```

**Safety Features:**
- **Fallback protection:** If Kishi crashes on startup, it automatically falls back to `/bin/bash` or `/bin/sh` — your system will never be locked out
- **Profile sourcing:** Automatically sources `/etc/profile` and `~/.profile` (or `~/.bash_profile`) so your environment is properly set up
- **Display manager compatible:** Properly handles `kishi -c "exec gnome-session"` for GDM, SDDM, LightDM
- **Non-interactive mode:** Pipes (`echo "echo hello" | kishi`) and scripts work without blocking

**Invocation Modes:**
```bash
kishi                              # Interactive mode (prompt + UI)
kishi -c "ls -la"                  # Execute a single command and exit
kishi --login                      # Login shell mode (source profiles)
kishi -l -c "exec gnome-session"   # Login + command (used by display managers)
echo "echo hello" | kishi          # Pipe mode (non-interactive, no banner)
```

---

##  Advanced Visual Interfaces (TUI)
Kishi Shell doesn't make you install Midnight Commander or `top`/`htop`. It has its own zero-latency tools rendered 100% in Python.

### 1-) VSCode-like Unified IDE & Dashboard
No more reading files on a plain black screen! Kishi Shell doesn't make you install Midnight Commander or `top`/`htop`. It merges both into a perfect VSCode-like layout.
- **Command:** `dashboard`
Running isolated in the background, this system displays CPU Core Usage, RAM / SWAP Metrics, Root Disk space, and Live Network Traffic (Down/Up) in side panels. 
![Dashboard UI](assets/dashboard.png)
![Dark Mode](assets/darkmode.png)

- When you press **`Ctrl + E`**, the massive terminal in the center instantly transforms into a **Dual-Panel IDE (Development Environment)**. The screen splits from the top into two sections, placing the Folder Tree on the left and the Code Editor on the right. The bottom section remains as the Kishi Terminal.
- You can navigate between panels using the **`Tab`** key, creating a perfect cycle between Tree -> Editor -> Terminal -> Input Line.
- Write your code and save it instantly with **`Ctrl + S`**. 
![IDE Layout](assets/ide_layout.png)
![IDE + Vite Dev Server](assets/dashboard_ide_vite.png)

#### Dashboard Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Execute command |
| `Tab` | Auto-complete commands and paths |
| `Ctrl + E` | Toggle IDE Explorer (file tree + editor) |
| `Shift + Tab` | Cycle focus between panels |
| `Ctrl + R` | Fuzzy search command history |
| `Ctrl + C` | Send SIGINT to running process |
| `Ctrl + Q` | Quit dashboard |
| `PgUp / PgDn` | Scroll terminal output |
| `Home / End` | Jump to top / bottom of output |

### 2-) Interactive Terminal & Directory Synchronization
The Kishi Terminal at the bottom of the screen works in live sync with the Folder Tree! 
- When you type `cd` in the command line to change directories, the Tree updates automatically.
- When you run long-running Python or Bash scripts that wait for your input (like `input()`), the interface never freezes! Thanks to background binary streaming, command outputs are printed directly to the interface, and inputs you type in the command line at the bottom are forwarded directly to the code's `stdin` input.
- You can send **`Ctrl + C`** to kill a running process without closing the dashboard, then continue using the terminal normally.
- Programs that require a terminal (`python`, `node`, `java`) work properly thanks to full pseudo-terminal (PTY) support.
![Interactive Terminal](assets/interactive_terminal.png)
![Ctrl+C Signal Handling](assets/dashboard_sigint.png)
![Terminal Commands](assets/dashboard_terminal_ls.png)
![Dashboard Bash Help](assets/dashboard_bash_help.png)

### 3-) Standalone File Explorer
The IDE Explorer also works as a standalone dual-pane file browser outside the dashboard. Navigate your entire filesystem, preview directories, and edit code with line numbers.
- **Command:** `explore`
- **Shortcut:** **`Ctrl + E`**
![Standalone Explorer](assets/explorer_standalone.png)
![Code Editing & Save](assets/explorer_code_editing.png)

### 4-) Tab Completion & Syntax Highlighting
Kishi provides real-time tab completion for system commands, builtins, and filesystem paths. Known commands appear in green, unknown ones in red.
![Tab Completion](assets/tab_completion.png)

### 5-) Help System & History Search (Fuzzy Search)
- For Comprehensive Help: `help` — For Quick Shortcuts: `help less`
![Help Guide](assets/help_guide.png)
![Help Overview](assets/help_overview.png)

No need to install external FZF to find your old commands.
- **Shortcut:** **`Ctrl + R`**
As you type like a typewriter, it performs character matching among thousands of your old commands and brings the desired command to your screen in seconds. Press `Enter` to pull the command.

---

##  Plugin Marketplace
Kishi Shell features a dynamic, Python-powered plugin ecosystem. You can browse, install, and manage official extensions natively without leaving the terminal or reloading the environment.

### Plugin Commands

| Command | Description |
|---------|-------------|
| `plugin list` | List all installed plugins |
| `plugin market` | Browse available plugins in the marketplace |
| `plugin install <name>` | Install a plugin by name from the marketplace |
| `plugin install <url>` | Install a plugin from a direct GitHub raw URL |
| `plugin remove <name>` | Uninstall a plugin |

### Available Plugins

| Plugin | Command | Description | Usage |
|--------|---------|-------------|-------|
| **weather** | `weather` | Live weather from [wttr.in](https://wttr.in) | `weather` (auto-detect location) or `weather Istanbul` |
| **ip** | `ip` | Public IP & location info via [ipinfo.io](https://ipinfo.io) | `ip` |
| **qr** | `qr` | Generate ASCII QR codes in your terminal | `qr https://github.com` or `qr "Hello World"` |
| **hello** | `hello` | Demo plugin — test your marketplace connection | `hello` |

### Example Usage

```bash
# Browse the marketplace
Kishi$ -> plugin market
 Available Plugins in Kishi Marketplace:
  - hello.py
  - weather.py
  - ip.py
  - qr.py

# Install a plugin
Kishi$ -> plugin install weather
[*] Downloading 'weather.py' from marketplace...
[+] Plugin 'weather' installed successfully!

# Use it immediately — no restart needed
Kishi$ -> weather Istanbul
Istanbul: ⛅️ +18°C

# Check what you have installed
Kishi$ -> plugin list
 Installed Plugins:
  - weather

# Remove when you no longer need it
Kishi$ -> plugin remove weather
[+] Plugin 'weather' removed.
```

Once installed, plugins operate at native speed and are fully integrated into Kishi's event loop. Plugins are stored in `~/.kishi/plugins/` and loaded automatically on shell startup.

### Creating Your Own Plugin

Create a `.py` file where the **filename must exactly match** the command name it exports:

```python
# mycommand.py
def mycommand(args):
    """args[0] = command name, args[1:] = user arguments"""
    if len(args) < 2:
        print("Usage: mycommand <text>")
        return 1

    print(f"Hello, {args[1]}!")
    return 0  # exit code: 0 = success

PLUGIN_COMMANDS = {
    "mycommand": mycommand  # key MUST match filename (mycommand.py -> "mycommand")
}
```

Install from any source:
```bash
# From the official marketplace (submit a PR to Kishi-Plugins repo)
plugin install mycommand

# Or from any raw GitHub URL
plugin install https://raw.githubusercontent.com/user/repo/main/mycommand.py
```

For more details, see the [Kishi-Plugins](https://github.com/ozhangebesoglu/Kishi-Plugins) repository.

---

##  Scripting and Environment Variables

### Setting and Reading Variables (`export`)
You can define new variables in the Kishi environment that other programs can also read.
```bash
Kishi$ -> export MY_KEY="12345"
Kishi$ -> echo $MY_KEY
12345
```
Simply type `unset MY_KEY` to remove it. You can list all loaded variables in the environment by just typing `export`.

### Customizing the Terminal Cursor
You can customize the terminal cursor globally across all TUI interfaces (Dashboard, Explorer, etc.) by exporting the `CURSOR_SHAPE` variable. Add this to your `~/.kishirc`:
```bash
export CURSOR_SHAPE="BLINKING_BLOCK"
```
Available options: `BLOCK`, `BLINKING_BLOCK`, `UNDERLINE`, `BLINKING_UNDERLINE`, `BEAM`, `BLINKING_BEAM`.

### Create Your Own Commands (`myfunc`)
If you keep repeating a task, you can instantly teach Kishi code blocks (Sub-Routines). Defining functions is very easy:

```bash
Kishi$ -> greet() { echo "Welcome to the System $USER"; ls -l; }
Kishi$ -> greet
Welcome to the System ozhangebesoglu
drwxrwxr-x 2 user user 4096 ...
```
You can chain functions with semicolons (`;`) and run massive automation scripts in a single line. Moreover, you can squeeze complex Shell operators like `|`, `&&`, `>`, `>>` in between your commands and outputs!

---

##  Architecture

Kishi is built on a classic **compiler pipeline** following SOLID principles:

```
Input → Lexer → Parser → Expander → Executor
         │        │         │          │
      tokens     AST    expanded    fork/exec
                          args      pipelines
```

| Module | Responsibility |
|--------|---------------|
| `lexer.py` | Tokenization, quote tracking |
| `parser.py` | Recursive descent parser, AST generation |
| `expander.py` | `$VAR`, glob, tilde, `$(cmd)` expansion |
| `executor.py` | fork/exec, pipelines, redirections, job control |
| `builtins.py` | 26 built-in commands |
| `tui_dashboard.py` | VS Code-style dashboard (5 SOLID classes) |
| `tui_explorer.py` | Dual-pane IDE explorer |
| `tui_fuzzy.py` | Ctrl+R fuzzy search engine |
| `ui.py` | Syntax highlighting, completions, keybindings |
| `main.py` | Login shell, mode detection, profile sourcing |
| `krep.py` | 3D semantic vector search engine |
| `krep_learn.py` | PPMI + SVD model: dictionary-free corpus learning |
| `krep_core.pyx` | Cython acceleration for vectorize / cosine |
| `krep_cli.py` | Standalone `krep` CLI entry point |

---

##  Krep AI — Semantic Search (v2.0.2.3+)

Krep is a **3D semantic vector search** tool. Unlike `grep`, it understands
**meaning**: searching `"auth login"` also surfaces lines containing
`"password validated"`, `"token issued"`, or `"yetkilendirme reddedildi"`.

Krep ships as **both** an embedded Kishi builtin **and** a standalone CLI.
`pip install kishi-shell` adds two binaries to your PATH: `kishi` and `krep`.

```bash
# From any shell (bash, zsh, fish, sh):
$ krep "auth login" /var/log/
$ krep --learn /var/log/ --auto-refresh 1h
$ cat app.log | krep error

# From inside Kishi REPL:
Kishi$ -> krep "auth login" /var/log/
```

### What's new in v2.0.2.3

- **Cleaner output** — single-line header with right-aligned elapsed time,
  scores colored by similarity (green/yellow/red), terminal-width aware.
- **i18n (EN default, TR optional)** — `--lang en|tr` switches header,
  error messages, and scatter labels. Default is English.
- **Opt-in 3D scatter** — the ASCII vector chart is now hidden by default.
  Pass `--scatter` to render it.
- **Shell-agnostic** — verified on bash, zsh, fish, and POSIX sh.

```text
$ krep "auth login" /var/log/
krep · 3 results · 'auth login' · keyword engine                            4 ms
────────────────────────────────────────────────────────────────────────────────
1.00  auth.log:4   login authorization required
1.00  auth.log:6   login: success
0.89  auth.log:1   auth login failed

$ krep --lang tr "auth login" /var/log/
krep · 3 sonuç · 'auth login' · anahtar kelime motoru                       4 ms
────────────────────────────────────────────────────────────────────────────────
1.00  auth.log:4   login authorization required
...

$ krep --scatter "auth login" /var/log/   # also draws the 3D ASCII chart
```

### Two engines, automatic dispatch

1. **Keyword engine (default, zero-setup):** built-in 178-word vocabulary
   across 3 axes — Error / Security / Data. Works out of the box.
2. **LSA model (`krep --learn PATH`):** PPMI + SVD trained on your corpus.
   Vocabulary, axes, and word vectors are learned from the actual files —
   no manual dictionary. Multilingual by construction. **Requires the
   optional extra:** `pip install kishi-shell[krep]` (adds numpy + scipy).

When you run `krep --learn /var/log/`, Krep:
- Scans every non-binary file, tokenizes (Unicode-aware)
- Builds a sparse cooccurrence matrix
- Normalizes with PPMI (Positive Pointwise Mutual Information)
- Computes SVD rank-50 word embeddings (HD for cosine ranking)
- Reduces to PCA-3 (only for the ASCII scatter visualization)
- Auto-labels each axis from its top-5 representative terms
- Saves to `~/.cache/kishi/krep_models/<path-hash>/`

```bash
$ krep --learn /var/log/ --auto-refresh 1h
[krep --learn] Vocab: 12,438 terms, 891,234 lines
[krep --learn] SVD rank-50 + PCA-3 (var=17.3%), 2.1s
[krep --learn] Axis 0: error fail timeout exception denied
[krep --learn] Axis 1: auth login user session token
[krep --learn] Axis 2: file query select read write
[+] Model saved: ~/.cache/kishi/krep_models/var_log_a8f3.../
    12438 terms, 891234 lines, 2.1s · auto-refresh 1h
```

### Tail-aware incremental updates

Log files are append-only. Krep tracks each file's last-read byte offset,
mtime, and size. When you run `krep --update-learn`, only **new lines**
are processed:

```bash
$ krep --update-learn /var/log/        # tail-only, ~%5 of full build time
$ krep --list-models                   # see what's cached
$ krep --purge-models                  # wipe everything
```

Rotation/truncate is detected automatically: if a file's size shrinks,
it's re-read from the beginning.

### Lazy auto-refresh (no daemon, no cron)

`--auto-refresh INTERVAL` writes a freshness threshold into the model.
On every query, if the model is older than the threshold, Krep fires a
**background subprocess** to refresh it (fire-and-forget). The current
query keeps running with the old model; the next query sees the new one.

```bash
$ krep --learn /var/log/ --auto-refresh 1h
$ krep "auth failure" /var/log/         # 5 hours later
  # ↓ Lazy refresh triggered in background
  # ↓ This query uses the old model (still fast)
$ krep "auth failure" /var/log/         # 3 seconds later
  # ↓ New model loaded automatically (cache mtime-invalidated)
```

Intervals are human-readable: `1h`, `30m`, `1d`, `2w`, `45s`, or `0` to disable.

### When ripgrep is installed: 200-3000× speedup

If `rg` (ripgrep) is on your PATH, Krep automatically uses it as a
**streaming prefilter**: only matching lines are vectorized, the rest is
skipped. Early-termination after `limit × 10` matches. Falls back to the
built-in Python walker when:
- `rg` not installed,
- stdin pipe mode,
- `rg` returns 0 hits (semantic neighbor lookup needs the walker).

```bash
$ krep --no-rg "auth login" /var/log/   # force pure-Python engine
```

Verified benchmarks (3-run averages, 12-core x86_64):

| Corpus | Query | Walker | rg-streaming | Speedup |
|--------|-------|-------:|-------------:|--------:|
| Kishi repo (~5k lines)      | `auth login`     | 1068 ms | **5 ms** | 206× |
| Python stdlib (~6.8M lines) | `auth login`     | timeout | **11 ms** | >5000× |
| Python stdlib               | `database query` | timeout | **14 ms** | >4000× |
| 1 GB single file (17M lines)| `auth login`     | timeout | **6 ms**  | >10000× |

---

##  Krep Performance (v2.0.1.1+)

Krep AI uses a two-path search architecture for the `krep` builtin:

1. **ripgrep-streaming (default when `rg` is installed):**
   - Builds a word-only regex from the query (`auth login` → `auth|login`).
   - Runs `rg -i -n --max-count=20` as a streaming subprocess.
   - Reads stdout line by line, vectorizes each match, computes cosine similarity.
   - Terminates `rg` early when `limit × 10` matches are collected.
   - **Result: 100-3000x faster than the sequential walker.**

2. **Built-in Python walker (semantic fallback):** mtime-keyed in-memory
   concept-vector cache + line-level bigram vectorization. Used when:
   - ripgrep isn't installed,
   - stdin is the input,
   - rg's literal pass returned 0 matches but the user's query has a
     semantic neighbour in the corpus (e.g. `login authorization` →
     matches `auth token expired`).

Override:
```bash
krep --no-rg PATTERN PATH    # Force the Python fallback (debug/test)
```

Verified benchmarks (3-run averages, 12-core x86_64, Python 3.14, ripgrep 15.1):
| Corpus | Query | Walker | rg-streaming | Speedup |
|--------|-------|-------:|-------------:|--------:|
| Kishi repo (~5k lines)   | `auth login`     | 1068 ms | **5 ms** | 206x |
| Kishi repo               | `error timeout`  | 1103 ms | **7 ms** | 156x |
| Kishi repo               | `database query` | 1071 ms | **5 ms** | 210x |
| Tests dir (~3k lines)    | `auth login`     | 1053 ms | **6 ms** | 171x |
| Python stdlib (~6.8M lines) | `auth login`  | timeout (>60 s) | **11 ms** | >5000x |
| Python stdlib            | `error timeout`  | timeout | **9 ms** | >6000x |
| Python stdlib            | `database query` | timeout | **14 ms** | >4000x |

---

##  Help Center (`help`)
Kishi always assists you. If you want to remember all system features and command tips:
- For Comprehensive (Full) Help: `help`
- For Quick Shortcut Summaries: `help less`
is all you need to type.

---

## Contributing

We welcome contributions! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to get started.

---
**Developed by:** Ozhan Gebesoglu  
*Designed to push the limits of Python in the Terminal.*

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=ozhangebesoglu/Kishi-Shell&type=Date)](https://star-history.com/#ozhangebesoglu/Kishi-Shell&Date)
