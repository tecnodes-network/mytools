@echo off
title H15 MySQL Tunnel
echo Starting SSH tunnel to MySQL...

:: Check if already running
tasklist | findstr /I "ssh.exe" >nul
if %errorlevel% equ 0 (
    echo [WARNING] SSH already running! Check taskbar.
    timeout /t 3 >nul
    exit
)

:: Start minimized to system tray/taskbar
start /min "" ssh -p 1221 -i "%USERPROFILE%\.ssh\id_tunnel" -o ServerAliveInterval=60 -o ExitOnForwardFailure=yes -N -L 3306:localhost:3306 akhan@167.235.33.106

echo [OK] Tunnel started! 
echo Connect to: localhost:3306 (or 127.0.0.1:3306)
echo.
echo To stop, run stop-mysql-tunnel.bat
echo Or kill ssh.exe in Task Manager
timeout /t 5 >nul