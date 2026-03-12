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
    goto :done
)

echo     [!] 'kishi' was not found in PATH.
echo.

REM Find Python Scripts directory and add to user PATH
for /f "delims=" %%i in ('python -c "import sysconfig; print(sysconfig.get_path(\"scripts\"))"') do set "SCRIPTS_DIR=%%i"

if defined SCRIPTS_DIR (
    echo     Python Scripts directory: %SCRIPTS_DIR%
    echo     Adding to user PATH...
    setx PATH "%PATH%;%SCRIPTS_DIR%" >nul 2>&1
    echo     [OK] PATH updated. Please restart your terminal.
) else (
    echo     Could not detect Python Scripts directory.
)

echo.
echo     You can always run Kishi with:
echo       python -m kishi

:done
echo.
echo =========================================
echo [OK] Installation Complete!
echo Type 'kishi' or 'python -m kishi' to launch Kishi Shell.
echo To uninstall: pip uninstall kishi-shell
echo =========================================
pause
