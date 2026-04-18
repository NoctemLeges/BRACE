@echo off
set LOGDIR=logs
set LOGFILE=%LOGDIR%\install_openssh.log

echo ================================
echo Installing OpenSSH...
echo ================================

:: Check admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Run as Administrator!
    pause
    exit /b
)

echo [INFO] Installing/Updating OpenSSH...

winget upgrade --id Microsoft.OpenSSH.Beta -e --silent >> %LOGFILE% 2>&1
if %errorLevel% neq 0 (
    winget install --id Microsoft.OpenSSH.Beta -e --silent >> %LOGFILE% 2>&1
)

if %errorLevel% neq 0 (
    echo [ERROR] OpenSSH installation failed!
    exit /b
)

echo [SUCCESS] OpenSSH installed.

:: Start service
sc config sshd start= auto >> %LOGFILE% 2>&1
net start sshd >> %LOGFILE% 2>&1

echo ================================
echo Done. Logs: %LOGFILE%
echo ================================
pause