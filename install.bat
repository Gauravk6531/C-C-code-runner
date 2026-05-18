@echo off
setlocal enabledelayedexpansion

echo ==============================================
echo       CODERUN WINDOWS GLOBAL INSTALLER
echo ==============================================
echo.

:: Define target installation folder
set "INSTALL_DIR=%LOCALAPPDATA%\coderun"
set "EXE_SOURCE=dist\coderun_gui.exe"

:: Check if the executable has been compiled
if not exist "%EXE_SOURCE%" (
    echo [ERROR] The executable 'dist\coderun_gui.exe' was not found!
    echo [ERROR] Please run 'python build_exe.py' first to build the executable.
    pause
    exit /b 1
)

:: Create installation directory if it doesn't exist
if not exist "%INSTALL_DIR%" (
    echo [INFO] Creating installation folder: %INSTALL_DIR%
    mkdir "%INSTALL_DIR%"
) else (
    :: Clean up old coderun.exe from previous installation if it exists
    if exist "%INSTALL_DIR%\coderun.exe" del /f /q "%INSTALL_DIR%\coderun.exe" >nul 2>&1
)

:: Close any running instances of coderun_gui.exe and coderun.exe to unlock files
echo [INFO] Closing any open coderun instances...
taskkill /f /im coderun_gui.exe >nul 2>&1
taskkill /f /im coderun.exe >nul 2>&1
ping -n 2 127.0.0.1 >nul

:: Copy coderun_gui.exe to the installation folder
echo [INFO] Copying executable to target folder...
copy /y "%EXE_SOURCE%" "%INSTALL_DIR%\coderun_gui.exe" >nul
if %errorlevel% neq 0 (
    echo [ERROR] Failed to copy the executable. Please check folder permissions.
    pause
    exit /b 1
)

:: Create batch wrapper inside the target installation directory to inherit parent shell working directories
echo [INFO] Generating command launcher batch wrapper...
(
echo @echo off
echo start "" "%%~dp0coderun_gui.exe" "%%CD%%"
) > "%INSTALL_DIR%\coderun.bat"

echo [INFO] Executable successfully installed to: %INSTALL_DIR%\coderun_gui.exe
echo [INFO] Command wrapper successfully generated at: %INSTALL_DIR%\coderun.bat

:: Add installation folder to User PATH using safe PowerShell environment scripting
echo [INFO] Safely appending installation path to Windows USER PATH environment variable...
powershell -NoProfile -Command ^
    "$userPath = [Environment]::GetEnvironmentVariable('PATH', 'User');" ^
    "if ($userPath -split ';' -notcontains '%INSTALL_DIR%') {" ^
    "    $newPath = $userPath + ';%INSTALL_DIR%';" ^
    "    [Environment]::SetEnvironmentVariable('PATH', $newPath, 'User');" ^
    "    Write-Host '[SUCCESS] Coderun added to Windows USER PATH!';" ^
    "} else {" ^
    "    Write-Host '[INFO] Coderun already exists in USER PATH.';" ^
    "}"

echo.
echo ==============================================
echo [SUCCESS] INSTALLATION COMPLETED!
echo ==============================================
echo.
echo You can now close this terminal, open a NEW CMD window anywhere,
echo and type:
echo.
echo    coderun
echo.
echo to launch the GUI for that specific folder!
echo.
pause
