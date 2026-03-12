@echo off
echo =========================================
echo        Kishi Shell Windows Installation
echo =========================================
echo.
echo [1/2] Installing Kishi Shell package (pip)...
pip install .
echo.
echo [2/2] Verifying installation...
where kishi >nul 2>&1 && (
    echo ✅ 'kishi' command is ready.
) || (
    echo ⚠️  'kishi' was not found in PATH. You may need to restart your terminal.
)
echo.
echo =========================================
echo ✅ Installation Complete!
echo Type 'kishi' in your terminal (CMD, PowerShell or Windows Terminal)
echo to launch Kishi Shell.
echo To uninstall: pip uninstall kishi-shell
echo =========================================
pause
