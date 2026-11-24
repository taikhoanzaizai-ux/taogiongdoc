@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\setup-windows.ps1" -Profile recommended -NoWsl
if errorlevel 1 pause
