#!/bin/bash
set -e

echo "========================================="
echo "       Kishi Shell Linux Installation    "
echo "========================================="

echo "[1/2] Installing Python dependencies and Kishi package..."
if pip3 install . 2>/dev/null; then
    echo "- Package installed successfully."
elif pip3 install --user . 2>/dev/null; then
    echo "- Package installed in user directory (~/.local)."
else
    echo ""
    echo "[!] Standard installation failed (your system may use PEP 668 protection)."
    echo "   Choose an option:"
    echo "   1) Install with --break-system-packages (not recommended)"
    echo "   2) Create a virtual environment (recommended)"
    echo ""
    read -p "Enter choice (1/2): " choice
    case "$choice" in
        1)
            pip3 install . --break-system-packages
            ;;
        2)
            echo "Creating virtual environment at ~/.kishi-venv ..."
            python3 -m venv ~/.kishi-venv
            ~/.kishi-venv/bin/pip install .
            echo ""
            echo "[i] Add this alias to your ~/.bashrc or ~/.zshrc:"
            echo "   alias kishi='~/.kishi-venv/bin/kishi'"
            ;;
        *)
            echo "[X] Installation cancelled."
            exit 1
            ;;
    esac
fi

# Verify the installation was successful
if ! python3 -c "from kishi.main import main" 2>/dev/null; then
    echo "[X] Error: Kishi module could not be loaded. Installation may have failed."
    echo "   Please run 'pip3 install .' manually and check the error output."
    exit 1
fi

echo "[2/2] Verifying the 'kishi' command..."
if command -v kishi >/dev/null 2>&1; then
    echo "[OK] 'kishi' command is ready."
else
    echo "[!] 'kishi' was not found in PATH. You may need to add ~/.local/bin to your PATH."
    echo "   Run: export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

echo "========================================="
echo "[OK] Installation Complete!"
echo "Type 'kishi' in your terminal to launch Kishi Shell."
echo "To uninstall: pip3 uninstall kishi-shell"
echo "========================================="
