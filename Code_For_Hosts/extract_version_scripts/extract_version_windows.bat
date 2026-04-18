@echo off
setlocal enabledelayedexpansion

set "OUTPUT_FILE=VersionInfo.txt"

REM Clear file WITHOUT adding blank line
type nul > "%OUTPUT_FILE%"

REM -------- OpenVPN --------
set "OPENVPN_BIN="

for /f "delims=" %%A in ('where openvpn 2^>nul') do (
    set "OPENVPN_BIN=%%A"
    goto :openvpn_found
)

if exist "%ProgramFiles%\OpenVPN\bin\openvpn.exe" (
    set "OPENVPN_BIN=%ProgramFiles%\OpenVPN\bin\openvpn.exe"
)

:openvpn_found
if defined OPENVPN_BIN (
    for /f "tokens=2" %%A in ('"%OPENVPN_BIN%" --version ^| findstr /B "OpenVPN"') do (
        echo openvpn:openvpn:%%A>>"%OUTPUT_FILE%"
    )
)

REM -------- OpenSSH --------
where ssh >nul 2>&1
if %errorlevel%==0 (
    for /f "delims=" %%A in ('ssh -V 2^>^&1') do set "line=%%A"

    REM Extract after last underscore
    for /f "tokens=* delims=_" %%A in ("!line!") do set "version=%%A"

    REM Remove comma and trailing text
    for /f "tokens=1 delims=," %%A in ("!version!") do set "version=%%A"

    echo openbsd:openssh:!version!>>"%OUTPUT_FILE%"
)

REM -------- NGINX --------
set "NGINX_BIN="

for /f "delims=" %%A in ('where nginx 2^>nul') do (
    set "NGINX_BIN=%%A"
    goto :nginx_found
)

if exist "%ProgramFiles%\nginx\nginx.exe" (
    set "NGINX_BIN=%ProgramFiles%\nginx\nginx.exe"
)

:nginx_found
if defined NGINX_BIN (
    for /f "tokens=2 delims=/" %%A in ('"%NGINX_BIN%" -v 2^>^&1') do (
        echo f5:nginx:%%A>>"%OUTPUT_FILE%"
    )
)

echo Version info written to %OUTPUT_FILE%
endlocal