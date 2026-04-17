@echo off
set LOGDIR=logs
set LOGFILE=%LOGDIR%\install_nginx.log

echo ================================
echo Installing NGINX...
echo ================================

:: Check admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Run as Administrator!
    pause
    exit /b
)

echo [INFO] Installing/Updating NGINX...

winget upgrade --id nginxinc.nginx -e --silent >> %LOGFILE% 2>&1
if %errorLevel% neq 0 (
    winget install --id nginxinc.nginx -e --silent >> %LOGFILE% 2>&1
)

if %errorLevel% neq 0 (
    echo [ERROR] NGINX installation failed!
    exit /b
)

echo [SUCCESS] NGINX installed.

echo ================================
echo Done. Logs: %LOGFILE%
echo ================================
pause