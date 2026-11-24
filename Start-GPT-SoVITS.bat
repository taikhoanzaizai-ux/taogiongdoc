@echo off
cd /d "%~dp0"
data\app-env\Scripts\python.exe desktop\start_service.py gpt-sovits
pause
