@echo off
chcp 65001 >nul 2>&1
echo =========================================
echo        Kishi Shell Windows Installation
echo =========================================
echo.
echo [1/2] Installing Kishi Shell package...

pip install . 2>nul
if %errorlevel% neq 0 (
    echo     pip not found, trying python -m pip...
    python -m pip install . 2>nul
    if %errorlevel% neq 0 (
        python3 -m pip install . 2>nul
        if %errorlevel% neq 0 (
            echo.
            echo [!] Installation failed. Make sure Python and pip are installed.
            echo     Download Python from: https://www.python.org/downloads/
            echo     During installation, check "Add Python to PATH".
            echo.
            pause
            exit /b 1
        )
    )
)

echo     Package installed successfully.
echo.
echo [2/2] Verifying installation...
where kishi >nul 2>&1 && (
    echo     [OK] 'kishi' command is ready.
) || (
    echo     [!] 'kishi' was not found in PATH. You may need to restart your terminal.
)
echo.
echo =========================================
echo [OK] Installation Complete!
echo Type 'kishi' in your terminal (CMD, PowerShell or Windows Terminal)
echo to launch Kishi Shell.
echo To uninstall: pip uninstall kishi-shell
echo =========================================
pause
