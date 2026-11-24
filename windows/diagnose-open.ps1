# Windows PowerShell 5.1. Launch the existing app with visible output.
param([switch]$FunctionsOnly)
function Write-OpenLog([string]$Path){
 process{
  $_|Out-File -LiteralPath $Path -Append -Encoding UTF8 -ErrorAction Stop
  Write-Output $_
 }
}
if($FunctionsOnly){return}
$ErrorActionPreference='Stop' 
$root=Split-Path $PSScriptRoot -Parent
$setup=Join-Path $PSScriptRoot 'setup-windows.ps1'
if(-not(Test-Path -LiteralPath $setup)){throw 'Missing windows/setup-windows.ps1. Extract this check into the existing app folder.'}
$data=if($env:QUAN_VOICE_DATA){$env:QUAN_VOICE_DATA}else{Join-Path $root 'data'}
$boot=Join-Path $data 'bootstrap'
New-Item -ItemType Directory -Force -Path $boot|Out-Null
$started=Get-Date
$log=Join-Path $boot ('mo-app-'+$PID+'.log')
@('QUAN Voice Studio - Startup check',('Time: '+$started.ToString('o')),('App folder: '+$root),('Data folder: '+$data),('PowerShell: '+$PSVersionTable.PSVersion))|Set-Content -LiteralPath $log -Encoding UTF8
Write-Host 'QUAN VOICE STUDIO - Mo ung dung va hien tien trinh' -ForegroundColor Cyan
Write-Host ('Nhat ky: '+$log)
Write-Host 'Giu cua so nay mo trong khi ung dung dang khoi dong.'
$code=1
try{
 Set-Location -LiteralPath $root
 # Separate process: setup's exit and parsing errors are both captured here.
 # Continue is local to the wrapper; setup keeps its own error handling.
 $ErrorActionPreference='Continue'
 & (Join-Path $PSHOME 'powershell.exe') -NoLogo -NoProfile -STA -ExecutionPolicy Bypass -File $setup -Profile none -Desktop 2>&1|Write-OpenLog $log
 $code=$LASTEXITCODE
 $ErrorActionPreference='Stop'
}catch{
 $code=1
 ($_|Out-String)|Write-OpenLog $log|Write-Host
}finally{
 # Include only error logs updated during this attempt, not old failures.
 $recent=@(Get-ChildItem -LiteralPath $boot -Filter 'desktop-launch-*.log' -ErrorAction SilentlyContinue|Where-Object{$_.LastWriteTime -ge $started.AddSeconds(-1)})
 $desktop=Join-Path $data 'logs\desktop.log'
 if(Test-Path -LiteralPath $desktop){$item=Get-Item -LiteralPath $desktop;if($item.LastWriteTime -ge $started.AddSeconds(-1)){$recent+= $item}}
 foreach($item in $recent){
  @('','--- '+$item.Name+' ---')|Write-OpenLog $log|Write-Host
  Get-Content -LiteralPath $item.FullName -Tail 100 -ErrorAction SilentlyContinue|Write-OpenLog $log|Write-Host
 }
 Write-Host ''
 Write-Host ('Ma ket thuc: '+$code)
 Write-Host ('Neu app khong mo, gui file nhat ky nay: '+$log) -ForegroundColor Yellow
}
exit $code
