#  Kishi Shell (v1.9.8)

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
pip install --upgrade kishi-shell
```

Type `kishi` in your terminal to launch Kishi Shell. Type `exit` to return to your default shell.

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

### 2-) Interactive Terminal & Directory Synchronization
The Kishi Terminal at the bottom of the screen works in live sync with the Folder Tree! 
- When you type `cd` in the command line to change directories, the Tree updates automatically.
- When you run long-running Python or Bash scripts that wait for your input (like `input()`), the interface never freezes! Thanks to background binary streaming, command outputs are printed directly to the interface, and inputs you type in the command line at the bottom are forwarded directly to the code's `stdin` input.
- You can send **`Ctrl + C`** to kill a running process without closing the dashboard, then continue using the terminal normally.
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

##  Scripting and Environment Variables

### Setting and Reading Variables (`export`)
You can define new variables in the Kishi environment that other programs can also read.
```bash
Kishi$ -> export MY_KEY="12345"
Kishi$ -> echo $MY_KEY
12345
```
Simply type `unset MY_KEY` to remove it. You can list all loaded variables in the environment by just typing `export`.

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
