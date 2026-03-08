# 🚀 Kishi Shell (v1.8.0)

Kishi Shell is a next-generation command-line interface built 100% in Python. Without relying on external C or Go binaries, it transforms your standard terminal experience into a fully-fledged **Terminal Operating System Interface (TUI)**. It combines traditional Bash syntax with modern *IDE (Code Editor)* and *System Monitor* capabilities natively out of the box.

## 📥 Installation
Install Kishi Shell system-wide using pip:
```bash
pip install --upgrade kishi-shell
```
Type `kishi` in your terminal to enter a whole new world!

---

## 🔥 Advanced Visual Interfaces (TUI)
Kishi Shell completely negates the need to install third-party tools like Midnight Commander or `htop`. It ships with zero-latency, 100% Python-rendered visual tools.

### 1-) Dual-Pane IDE (File Explorer)
Stop reading files in a plain black screen.
- **Command:** `explore` (or shortcut **`Ctrl + E`**)
Kishi splits the screen into two. On the left, it generates a smart **Directory Tree** that you can navigate using arrow keys (It automatically identifies Python, Text, and Media files with `[PY]`, `[TXT]`, `[VID]` tags).
- If you hover over a file and press **`Tab`**, the right panel instantly transforms into a **Fully Functional Text Editor** powered by `prompt_toolkit`.
- The editor works right out of the box! You can instantly type, write your code, and view line numbers on the left margin. Standard keyboard mappings intuitively apply natively.
- You can save your edits instantly using **`Ctrl + S`** and quit the interface by pressing **`Q`**.

### 2-) System Monitor (Dashboard)
Monitor your computer's heart in real-time.
- **Command:** `dashboard`
Running entirely isolated on a Background Daemon Thread, this monitor visualizes your CPU Core Utilization, RAM / SWAP Metrics, Root Storage, and Live Network Traffic (Down/Up). Thanks to its asynchronous architecture, your terminal will never suffer input lag while the dashboard is running.

### 3-) Fuzzy History Search
No need to install FZF externally to search your bash history.
- **Shortcut:** **`Ctrl + R`**
As you type, Kishi filters thousands of your past commands using advanced fuzzy-logic string matching and brings your target command directly to your screen in milliseconds. Press `Enter` to select and run.

---

## 💻 Scripting and Environment Variables

### Assigning Variables (`export`)
You can define new environment variables directly inside Kishi so that native OS binaries can inherit them.
```bash
Kishi$ -> export MY_KEY="12345"
Kishi$ -> echo $MY_KEY
12345
```
Simply type `unset MY_KEY` to wipe it. If you type `export` without any arguments, Kishi will print out all currently loaded environment variables.

### Build Your Own Commands (`myfunc`)
If you constantly repeat specific tasks, you can deploy your own Sub-Routines (Functions) straight into Kishi's memory:

```bash
Kishi$ -> hello() { echo "Welcome to the system $USER"; ls -l; }
Kishi$ -> hello
Welcome to the system ozhangebesoglu
drwxrwxr-x 2 user user 4096 ...
```
You can chain multiple complex functions, pipe their outputs (`|`), use logical chains (`&&`), or even deploy standard redirectors (`>`, `>>`) all within Kishi's powerful Abstract Syntax Tree engine.

---

## 🙋‍♂️ Help Center (`help`)
Kishi acts as a co-pilot. If you ever forget how to use the IDE or declare variables:
- For comprehensive manual: `help`
- For a quick shortcut cheat-sheet: `help less`

---
**Developed by:** Ozhan Gebesoglu  
*Engineered to push the limits of Python in the Terminal environment.*
