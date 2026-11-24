$ErrorActionPreference='Stop'
& wsl.exe --install --no-distribution
$code=$LASTEXITCODE
Write-Host 'If Windows requests a restart, restart once and open BAT_DAU.bat again. No automatic restart.'
exit $code
