@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Cap nhat WSL va khoi dong lai rieng QuanVoice-Fish. Dong Studio truoc khi chay.
wsl.exe --update
if errorlevel 1 goto failed
wsl.exe --terminate QuanVoice-Fish
wsl.exe -d QuanVoice-Fish -u root --exec /bin/true
if errorlevel 1 goto failed
echo WSL da khoi dong. Mo BAT_DAU.bat va bam Thu lai Fish Speech.
pause
exit /b 0
:failed
echo WSL chua san sang. Khoi dong lai Windows, kiem tra Virtualization va dung luong o dia, roi thu lai.
echo Khong xoa hay unregister QuanVoice-Fish. Giu lai thong bao loi phia tren.
pause
exit /b 1
