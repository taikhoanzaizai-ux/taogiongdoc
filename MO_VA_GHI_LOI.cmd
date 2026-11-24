@echo off
setlocal
title QUAN Voice Studio - Mo app va ghi loi
cd /d "%~dp0"
if not exist "%~dp0windows\diagnose-open.ps1" goto missing
if not exist "%~dp0windows\setup-windows.ps1" goto missing
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0windows\diagnose-open.ps1"
set "QV_OPEN_EXIT=%ERRORLEVEL%"
echo.
echo Cua so nay giu lai de ban doc thong bao. Bam phim bat ky de dong.
pause >nul
exit /b %QV_OPEN_EXIT%
:missing
echo Hay giai nen GOI KIEM TRA vao DUNG thu muc ung dung.
echo File MO_VA_GHI_LOI.cmd phai nam CUNG CHO voi QUAN_VOICE.vbs.
echo Giu nguyen thu muc data va cac model da co.
echo.
pause
exit /b 2
