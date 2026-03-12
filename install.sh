#!/bin/bash
set -e

echo "========================================="
echo "       Kishi Shell Linux Installation    "
echo "========================================="

detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo "$ID"
    elif command -v pacman >/dev/null 2>&1; then
        echo "arch"
    elif command -v dnf >/dev/null 2>&1; then
        echo "fedora"
    elif command -v apt >/dev/null 2>&1; then
        echo "debian"
    else
        echo "unknown"
    fi
}

DISTRO=$(detect_distro)
echo "[i] Detected distro: $DISTRO"
echo ""

install_system_deps() {
    case "$DISTRO" in
        arch|endeavouros|manjaro|garuda|cachyos)
            echo "[1/3] Installing system dependencies (pacman)..."
            sudo pacman -S --needed --noconfirm python python-pip python-prompt_toolkit python-psutil
            ;;
        fedora|nobara)
            echo "[1/3] Installing system dependencies (dnf)..."
            sudo dnf install -y python3 python3-pip python3-prompt_toolkit python3-psutil
            ;;
        rhel|centos|rocky|alma)
            echo "[1/3] Installing system dependencies (dnf)..."
            sudo dnf install -y python3 python3-pip
            ;;
        debian|ubuntu|linuxmint|pop|zorin|elementary|kali)
            echo "[1/3] Installing system dependencies (apt)..."
            sudo apt update -qq
            sudo apt install -y python3 python3-pip python3-venv python3-prompt-toolkit python3-psutil
            ;;
        opensuse*|suse*)
            echo "[1/3] Installing system dependencies (zypper)..."
            sudo zypper install -y python3 python3-pip python3-prompt_toolkit python3-psutil
            ;;
        void)
            echo "[1/3] Installing system dependencies (xbps)..."
            sudo xbps-install -Sy python3 python3-pip python3-prompt_toolkit python3-psutil
            ;;
        *)
            echo "[1/3] Unknown distro. Skipping system package install."
            echo "    Make sure python3 and pip3 are installed."
            ;;
    esac
}

install_system_deps

echo ""
echo "[2/3] Installing Kishi Shell package..."
if pip3 install . 2>/dev/null; then
    echo "    Package installed successfully."
elif pip3 install --user . 2>/dev/null; then
    echo "    Package installed in user directory (~/.local)."
else
    echo ""
    echo "[!] Standard installation failed (your system may use PEP 668 protection)."
    echo "    Choose an option:"
    echo "    1) Install with --break-system-packages (not recommended)"
    echo "    2) Create a virtual environment (recommended)"
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
            echo "[i] Add this to your shell config (~/.bashrc or ~/.zshrc):"
            echo '    export PATH="$HOME/.kishi-venv/bin:$PATH"'
            ;;
        *)
            echo "[X] Installation cancelled."
            exit 1
            ;;
    esac
fi

if ! python3 -c "from kishi.main import main" 2>/dev/null; then
    echo "[X] Error: Kishi module could not be loaded. Installation may have failed."
    echo "    Please run 'pip3 install .' manually and check the error output."
    exit 1
fi

echo ""
echo "[3/3] Verifying the 'kishi' command..."
if command -v kishi >/dev/null 2>&1; then
    echo "    [OK] 'kishi' command is ready."
else
    echo "    [!] 'kishi' was not found in PATH."
    echo '    Run: export PATH="$HOME/.local/bin:$PATH"'
fi

echo ""
echo "========================================="
echo "[OK] Installation Complete!"
echo "Type 'kishi' in your terminal to launch."
echo "Run  'kishi --setup' to register as a shell."
echo "To uninstall: pip3 uninstall kishi-shell"
echo "========================================="
