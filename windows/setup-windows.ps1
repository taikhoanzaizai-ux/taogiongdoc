param([ValidateSet('all','recommended','none')][string]$Profile='all',[switch]$NoLaunch,[switch]$NoWsl,[switch]$FunctionsOnly,[switch]$Desktop,[switch]$Repair)
$ErrorActionPreference='Stop'
function Merge-PathEntries([string]$Existing,[string[]]$Entries){
 $parts=New-Object 'System.Collections.Generic.List[string]'
 foreach($p in ($Existing -split ';')){if($p.Trim()){$parts.Add($p.Trim())}}
 foreach($entry in $Entries){if($entry -and -not ($parts|Where-Object{$_.TrimEnd('\') -ieq $entry.TrimEnd('\')})){$parts.Add($entry)}}
 return ($parts -join ';')
}
function Checked([string]$Exe,[string[]]$Arguments){Invoke-StudioChecked $Exe $Arguments}
function Test-Python311([string]$Exe){
 if(-not $Exe -or -not (Test-Path -LiteralPath $Exe)){return $false}
 try{& $Exe -c "import sys,struct;sys.exit(0 if sys.version_info[:2]==(3,11) and struct.calcsize('P')==8 else 1)" 2>$null;return ($LASTEXITCODE -eq 0)}catch{return $false}
}
function Asset([string]$Name){
 $item=$script:Manifest.assets|Where-Object{$_.file -eq $Name}|Select-Object -First 1
 if(-not $item){throw "Missing manifest entry: $Name"}
 $file=Join-Path $script:Assets $Name
 if(-not(Test-Path -LiteralPath $file)){New-Item -ItemType Directory -Force -Path (Split-Path $file)|Out-Null;Invoke-WebRequest -UseBasicParsing -Uri $item.url -OutFile ($file+'.part');Move-Item -LiteralPath ($file+'.part') -Destination $file -Force}
 if((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ine $item.sha256){throw "Damaged installer: $Name. Extract the package again."}
 return $file
}
. (Join-Path $PSScriptRoot 'launch-support.ps1')
if($FunctionsOnly){return}
if([Environment]::OSVersion.Platform -ne 'Win32NT' -or -not [Environment]::Is64BitOperatingSystem){throw 'Windows x64 is required.'}
$env:PYTHONUTF8='1';$env:PYTHONIOENCODING='utf-8'
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
$AppRoot=Split-Path $PSScriptRoot -Parent
$Data=if($env:QUAN_VOICE_DATA){$env:QUAN_VOICE_DATA}else{Join-Path $AppRoot 'data'}
$Boot=Join-Path $Data 'bootstrap';$TranscriptStarted=$false
$mutex=$null;$held=$false
Write-Host 'QUAN VOICE STUDIO 1.6.8 - Opening application' -ForegroundColor Cyan
try{
 # Opening an installed app does not need ownership of its installer mutex.
 if(-not $NoLaunch -and -not $Repair){
  if(Open-ReadyStudio $AppRoot $Data $Profile -Desktop:$Desktop){return}
 }
 $mutex=New-Object Threading.Mutex($false,'Local\QuanVoiceStudioSetup')
 $held=Enter-SetupMutex $mutex
 if(-not $held){
  $wait=Wait-StudioSetup $mutex $AppRoot $Data -Desktop:$Desktop -AllowReady:([bool](-not $NoLaunch -and -not $Repair))
  if($wait.State -eq 'cancelled'){return}
  if($wait.State -eq 'ready'){Invoke-InstalledStudio $AppRoot $Data $Profile $wait.Installed -Desktop:$Desktop;return}
  $held=$true
  if(-not $NoLaunch -and -not $Repair){
   $ready=Get-InstalledStudio $AppRoot $Data
   if($ready){$mutex.ReleaseMutex();$held=$false;Invoke-InstalledStudio $AppRoot $Data $Profile $ready -Desktop:$Desktop;return}
  }
 }
 . (Join-Path $PSScriptRoot 'portable-data.ps1')
 if(-not $env:QUAN_VOICE_DATA){Initialize-PortableData -AppRoot $AppRoot -Data $Data}
 $env:QUAN_VOICE_DATA=$Data
 New-Item -ItemType Directory -Force -Path $Boot|Out-Null
 Start-Transcript -Path (Join-Path $Boot 'setup.log') -Append|Out-Null;$TranscriptStarted=$true
 foreach($key in @('TEMP','TMP','TMPDIR')){[Environment]::SetEnvironmentVariable($key,(Join-Path $Data 'temp'),'Process')}
 New-Item -ItemType Directory -Force -Path $env:TEMP|Out-Null
 $env:UV_CACHE_DIR=Join-Path $Data 'cache\uv';$env:UV_PYTHON_INSTALL_DIR=Join-Path $Data 'runtimes\uv-python';$env:PIP_CACHE_DIR=Join-Path $Data 'cache\pip'
 $env:UV_HTTP_TIMEOUT='120';$env:UV_HTTP_RETRIES='5'
 $script:Manifest=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'assets-manifest.json') -Raw|ConvertFrom-Json
 $script:Assets=Join-Path $AppRoot 'install-assets';if(-not(Test-Path -LiteralPath $script:Assets)){$script:Assets=Join-Path $Boot 'downloads'}
 Write-Host 'QUAN VOICE STUDIO - Automatic Windows setup' -ForegroundColor Cyan
 Write-Host '1/4 - Python 3.11 x64, pip, Python Launcher and PATH'
 $PyHome=Join-Path $Data 'runtimes\Python311';$Python=Join-Path $PyHome 'python.exe'
 if(-not(Test-Python311 $Python)){
  $candidates=@((Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'))
  foreach($name in @('python.exe','python3.exe')){try{$candidates+=(Get-Command $name -CommandType Application -ErrorAction Stop).Source}catch{}}
  foreach($key in @('HKCU:\Software\Python\PythonCore\3.11\InstallPath','HKLM:\Software\Python\PythonCore\3.11\InstallPath')){try{$candidates+=(Join-Path (Get-Item -LiteralPath $key -ErrorAction Stop).GetValue('') 'python.exe')}catch{}}
  try{$found=(& py.exe -3.11 -c 'import sys;print(sys.executable)' 2>$null|Select-Object -Last 1);$candidates+=$found}catch{}
  foreach($candidate in ($candidates|Select-Object -Unique)){if(Test-Python311 $candidate){$Python=$candidate;$PyHome=Split-Path $Python;break}}
 }
 $launcher=(Test-Path -LiteralPath (Join-Path $env:LOCALAPPDATA 'Programs\Python\Launcher\py.exe')) -or [bool](Get-Command py.exe -ErrorAction SilentlyContinue)
 if(-not(Test-Python311 $Python)){
  $file=Asset 'python-installer.exe'
  $process=Start-Process $file -ArgumentList @('/passive','/norestart','InstallAllUsers=0','Include_launcher=1','InstallLauncherAllUsers=0','Include_pip=1','PrependPath=1','Include_test=0','Include_doc=0',('TargetDir="{0}"' -f $PyHome)) -Wait -PassThru
  if($process.ExitCode -notin @(0,3010)){throw "Python installation failed: $($process.ExitCode)"}
  $Python=Join-Path $PyHome 'python.exe';if(-not(Test-Python311 $Python)){throw 'Python 3.11 x64 was not installed.'}
 }
 $launcher=(Test-Path -LiteralPath (Join-Path $env:LOCALAPPDATA 'Programs\Python\Launcher\py.exe')) -or [bool](Get-Command py.exe -ErrorAction SilentlyContinue)
 if(-not $launcher){Write-Host 'Python Launcher is absent; using the verified Python 3.11 executable directly.' -ForegroundColor Yellow}
 Write-Host '2/4 - Git for Windows (MinGit) and FFmpeg'
 $Tools=Join-Path $Data 'tools';New-Item -ItemType Directory -Force -Path $Tools|Out-Null
 $GitRoot=Join-Path $Tools 'git';$Git=Join-Path $GitRoot 'cmd\git.exe'
 if(-not(Test-Path -LiteralPath $Git)){
  $file=Asset 'mingit.zip';$stage=Join-Path $Tools 'git-stage';if(Test-Path -LiteralPath $stage){Remove-Item -LiteralPath $stage -Recurse -Force};Expand-Archive -LiteralPath $file -DestinationPath $stage -Force
  if(-not(Test-Path -LiteralPath (Join-Path $stage 'cmd\git.exe'))){throw 'Incomplete Git archive.'}
  if(Test-Path -LiteralPath $GitRoot){Remove-Item -LiteralPath $GitRoot -Recurse -Force};Move-Item -LiteralPath $stage -Destination $GitRoot
 }
 $FFRoot=Join-Path $Tools 'ffmpeg';$FF=Get-ChildItem -LiteralPath $FFRoot -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue|Select-Object -First 1
 if(-not $FF){$file=Asset 'ffmpeg.zip';Expand-Archive -LiteralPath $file -DestinationPath $FFRoot -Force;$FF=Get-ChildItem -LiteralPath $FFRoot -Recurse -Filter ffmpeg.exe|Select-Object -First 1}
 if(-not $FF){throw 'Incomplete FFmpeg archive.'}
 $Paths=@($PyHome,(Join-Path $PyHome 'Scripts'),(Join-Path $env:LOCALAPPDATA 'Programs\Python\Launcher'),(Split-Path $Git),(Split-Path $FF.FullName))
 [Environment]::SetEnvironmentVariable('Path',(Merge-PathEntries ([Environment]::GetEnvironmentVariable('Path','User')) $Paths),'User')
 $env:Path=($Paths -join ';')+';'+$env:Path
 Checked $Git @('--version');Checked $FF.FullName @('-version')
 Write-Host 'Checking Microsoft Visual C++ x64 runtime'
 try{
  $vc=Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64' -ErrorAction SilentlyContinue
  if(-not $vc -or $vc.Installed -ne 1){
   $file=Asset 'vc_redist.x64.exe'
   $process=Start-Process $file -Verb RunAs -ArgumentList @('/install','/passive','/norestart') -Wait -PassThru
   if($process.ExitCode -notin @(0,3010,1638)){throw "Visual C++ runtime installation returned $($process.ExitCode)"}
  }
 }catch{Write-Host ('Runtime setup needs attention: '+$_.Exception.Message+'. Models may require the Visual C++ runtime.') -ForegroundColor Yellow}
 Write-Host '3/4 - Application environment and bundled offline wheels'
 $Venv=Join-Path $Data 'app-env';$AppPython=Join-Path $Venv 'Scripts\python.exe'
 if(-not(Test-Python311 $AppPython)){
  if(Test-Path -LiteralPath $Venv){
   $backup=Join-Path $Data ('app-env-before-repair-'+[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')+'-'+$PID)
   Move-Item -LiteralPath $Venv -Destination $backup
   Write-Host ('Preserved the unusable app environment: '+$backup) -ForegroundColor Yellow
  }
  Checked $Python @('-m','venv',$Venv)
 }
 $Requirements=Join-Path $AppRoot 'desktop\requirements.txt';$Hash=(Get-FileHash -LiteralPath $Requirements -Algorithm SHA256).Hash;$Receipt=Join-Path $Boot 'requirements.sha256'
 $old=if(Test-Path -LiteralPath $Receipt){(Get-Content -LiteralPath $Receipt -Raw).Trim()}else{''}
 $CoreValid=$false;try{& $AppPython -c 'import fastapi,uvicorn,httpx,multipart,uv' 2>$null;$CoreValid=($LASTEXITCODE -eq 0)}catch{}
 if($old -ne $Hash -or -not $CoreValid){
  $Wheels=Join-Path $script:Assets 'wheels';$offline=$false
  if(Test-Path -LiteralPath $Wheels){
   foreach($w in $script:Manifest.wheels){$p=Join-Path $script:Assets $w.file;if(-not(Test-Path -LiteralPath $p) -or (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash -ine $w.sha256){throw "Damaged wheel: $($w.file)"}}
   try{Checked $AppPython @('-m','pip','install','--no-index','--find-links',$Wheels,'-r',$Requirements);$offline=$true}catch{Write-Host ('Offline core setup: '+$_.Exception.Message+'. Trying online packages.') -ForegroundColor Yellow}
  }
  if(-not $offline){Checked $AppPython @('-m','pip','install','-r',$Requirements)}
  Checked $AppPython @('-c','import fastapi,uvicorn,httpx,multipart,uv');Set-Content -LiteralPath $Receipt $Hash -Encoding ASCII
 }
 if($Profile -eq 'all' -and -not $NoWsl -and -not(Test-Path -LiteralPath (Join-Path $Data 'studio.db'))){
  try{$ready=$false;if(Get-Command wsl.exe -ErrorAction SilentlyContinue){& wsl.exe --status 2>&1|Out-File -LiteralPath (Join-Path $Boot 'wsl.log') -Encoding UTF8;$ready=($LASTEXITCODE -eq 0)}
   if(-not $ready -and -not(Test-Path -LiteralPath (Join-Path $Boot 'wsl-requested.flag'))){
    Write-Host 'Windows may request administrator approval for WSL. No automatic reboot.' -ForegroundColor Yellow
    $enable=Join-Path $PSScriptRoot 'enable-wsl.ps1'
    $p=Start-Process powershell.exe -Verb RunAs -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"{0}"' -f $enable)) -Wait -PassThru
    if($p.ExitCode -in @(0,3010)){Set-Content -LiteralPath (Join-Path $Boot 'wsl-requested.flag') 'Restart Windows if requested, then open BAT_DAU.bat again.'}
   }
  }catch{Write-Host ('WSL is not ready: '+$_.Exception.Message) -ForegroundColor Yellow}
 }
 Write-Host '4/4 - Opening the studio; models are prepared in the background.'
 $env:QUAN_VOICE_DATA=$Data;$env:QUAN_VOICE_SETUP_PROFILE=$Profile
 if(-not $NoLaunch){
  if($Desktop){
   $DesktopRequirements=Join-Path $AppRoot 'desktop\desktop-requirements.txt';$DesktopReceipt=Join-Path $Boot 'desktop-requirements.sha256'
   $DesktopHash=(Get-FileHash -LiteralPath $DesktopRequirements -Algorithm SHA256).Hash
   $previous=if(Test-Path -LiteralPath $DesktopReceipt){(Get-Content -LiteralPath $DesktopReceipt -Raw).Trim()}else{''}
   $WebViewPresent=$false;try{& $AppPython -c 'import webview' 2>$null;$WebViewPresent=($LASTEXITCODE -eq 0)}catch{}
   if($previous -ne $DesktopHash -or -not $WebViewPresent){
    try{Add-Type -AssemblyName System.Windows.Forms;$notice=New-Object System.Windows.Forms.NotifyIcon;$notice.Icon=[System.Drawing.SystemIcons]::Information;$notice.Visible=$true;$notice.ShowBalloonTip(5000,'QUAN Voice Studio','Preparing the desktop window for the first time. Keep Internet connected; saved voice models are reused.',[System.Windows.Forms.ToolTipIcon]::Info)}catch{}
    try{
     $desktopOffline=$false;$Wheels=Join-Path $script:Assets 'wheels'
     if(Test-Path -LiteralPath $Wheels){
      foreach($w in $script:Manifest.wheels){$p=Join-Path $script:Assets $w.file;if(-not(Test-Path -LiteralPath $p) -or (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash -ine $w.sha256){throw ('Damaged bundled wheel: '+$w.file)}}
      try{Checked $AppPython @('-m','pip','install','--no-index','--find-links',$Wheels,'-r',$DesktopRequirements);$desktopOffline=$true}catch{Write-Host ('Offline desktop setup: '+$_.Exception.Message+'. Trying online packages.') -ForegroundColor Yellow}
     }
     if(-not $desktopOffline){Checked $AppPython @('-m','pip','install','--prefer-binary','-r',$DesktopRequirements)}
     Set-Content -LiteralPath $DesktopReceipt $DesktopHash -Encoding ASCII
    }catch{Write-Host ('WebView install: '+$_.Exception.Message+'. Trying browser app mode.') -ForegroundColor Yellow}
   }
   if($notice){$notice.Dispose()}
  }
  $installed=[pscustomobject]@{Python=$AppPython;BaseHome=$PyHome;Git=$Git;FFmpeg=$FF.FullName}
  if($TranscriptStarted){Stop-Transcript|Out-Null;$TranscriptStarted=$false}
  $mutex.ReleaseMutex();$held=$false
  Invoke-InstalledStudio $AppRoot $Data $Profile $installed -Desktop:$Desktop
 }

}catch{Write-Host ('SETUP ERROR: '+$_.Exception.Message) -ForegroundColor Red;Write-Host ('Log: '+$Boot);if($Desktop){try{Add-Type -AssemblyName System.Windows.Forms;[System.Windows.Forms.MessageBox]::Show(($_.Exception.Message+"`nLog: "+$Boot),'QUAN Voice Studio 1.6.8')|Out-Null}catch{}};exit 1}
finally{if($held){$mutex.ReleaseMutex()};if($mutex){$mutex.Dispose()};if($TranscriptStarted){Stop-Transcript|Out-Null}}
