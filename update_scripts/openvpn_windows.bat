@echo off
set LOGDIR=logs
set LOGFILE=%LOGDIR%\install_openvpn.log

echo ================================
echo Installing OpenVPN...
echo ================================

:: Check admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Run as Administrator!
    pause
    exit /b
)

echo [INFO] Installing/Updating OpenVPN...

winget upgrade --id OpenVPNTechnologies.OpenVPN -e --silent >> %LOGFILE% 2>&1
if %errorLevel% neq 0 (
    winget install --id OpenVPNTechnologies.OpenVPN -e --silent >> %LOGFILE% 2>&1
)

if %errorLevel% neq 0 (
    echo [ERROR] OpenVPN installation failed!
    exit /b
)

echo [SUCCESS] OpenVPN installed.

echo ================================
echo Done. Logs: %LOGFILE%
echo ================================
pause