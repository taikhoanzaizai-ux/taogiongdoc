# Windows PowerShell 5.1 compatible. Setup ownership stays on the UI thread.
function Invoke-StudioChecked([string]$Exe,[string[]]$Arguments,[string]$LogPath=''){
 # stderr may contain ordinary progress/warnings. Exit status decides success.
 Get-Command $Exe -ErrorAction Stop|Out-Null
 $previous=$ErrorActionPreference;$code=1
 try{
  $ErrorActionPreference='Continue'
  if($LogPath){& $Exe @Arguments 2>&1|Out-File -LiteralPath $LogPath -Encoding UTF8 -ErrorAction Stop}else{& $Exe @Arguments}
  $code=$LASTEXITCODE
 }finally{$ErrorActionPreference=$previous}
 if($code -ne 0){throw ('Command failed ('+$code+'): '+$Exe+$(if($LogPath){'. Log: '+$LogPath}else{''}))}
}
function Enter-SetupMutex($Mutex){
 try{return $Mutex.WaitOne(0)}
 catch [System.Threading.AbandonedMutexException]{return $true}
}
function Get-InstalledStudio([string]$AppRoot,[string]$Data){
 if(Test-Path -LiteralPath (Join-Path $Data 'migration-from-localappdata.pending')){return $null}
 $python=Join-Path $Data 'app-env\Scripts\python.exe'
 $receipt=Join-Path $Data 'bootstrap\requirements.sha256'
 $requirements=Join-Path $AppRoot 'desktop\requirements.txt'
 $git=Join-Path $Data 'tools\git\cmd\git.exe'
 if(-not(Test-Path -LiteralPath $python) -or -not(Test-Path -LiteralPath $receipt) -or -not(Test-Path -LiteralPath $git)){return $null}
 try{
  if((Get-Content -LiteralPath $receipt -Raw).Trim() -ine (Get-FileHash -LiteralPath $requirements -Algorithm SHA256).Hash){return $null}
  $ff=Get-ChildItem -LiteralPath (Join-Path $Data 'tools\ffmpeg') -Recurse -Filter ffmpeg.exe -ErrorAction Stop|Select-Object -First 1
  if(-not $ff){return $null}
  # A receipt alone is insufficient: validate imports and the Python version too.
  $previous=$ErrorActionPreference
  try{$ErrorActionPreference='Continue';$raw=& $python -c "import sys,struct,json,fastapi,uvicorn,httpx,multipart,uv;assert sys.version_info[:2]==(3,11) and struct.calcsize('P')==8;print(json.dumps({'base_home':sys.base_prefix}))" 2>$null;$exitCode=$LASTEXITCODE}finally{$ErrorActionPreference=$previous}
  if($exitCode -ne 0){return $null}
  $info=($raw -join "`n")|ConvertFrom-Json
  return [pscustomobject]@{Python=$python;BaseHome=[string]$info.base_home;Git=$git;FFmpeg=$ff.FullName}
 }catch{return $null}
}
function Set-StudioEnvironment([string]$Data,[string]$Profile,$Installed){
 $env:QUAN_VOICE_DATA=$Data;$env:QUAN_VOICE_SETUP_PROFILE=$Profile
 $paths=@($Installed.BaseHome,(Join-Path $Installed.BaseHome 'Scripts'),(Split-Path $Installed.Git),(Split-Path $Installed.FFmpeg))
 $env:Path=($paths -join ';')+';'+$env:Path
 foreach($key in @('TEMP','TMP','TMPDIR')){[Environment]::SetEnvironmentVariable($key,(Join-Path $Data 'temp'),'Process')}
 New-Item -ItemType Directory -Force -Path (Join-Path $Data 'temp')|Out-Null
 $env:UV_CACHE_DIR=Join-Path $Data 'cache\uv';$env:UV_PYTHON_INSTALL_DIR=Join-Path $Data 'runtimes\uv-python';$env:PIP_CACHE_DIR=Join-Path $Data 'cache\pip'
 $env:UV_HTTP_TIMEOUT='120';$env:UV_HTTP_RETRIES='5'
}
function Invoke-InstalledStudio([string]$AppRoot,[string]$Data,[string]$Profile,$Installed,[switch]$Desktop){
 Set-StudioEnvironment $Data $Profile $Installed
 $boot=Join-Path $Data 'bootstrap';New-Item -ItemType Directory -Force -Path $boot|Out-Null
 try{
  $shell=New-Object -ComObject WScript.Shell
  $link=$shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'QUAN Voice Studio.lnk'))
  $link.TargetPath=Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
  $link.Arguments=('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}" -Profile all -Desktop' -f (Join-Path $AppRoot 'windows\setup-windows.ps1'))
  $link.WindowStyle=7;$link.WorkingDirectory=$AppRoot;$link.IconLocation=Join-Path $AppRoot 'desktop\app.ico';$link.Save()
 }catch{}
 Set-Location -LiteralPath $AppRoot
 if($Desktop){
  $env:QUAN_VOICE_DESKTOP='1'
  # Each click has its own log. A still-open launcher must not lock a shared log.
  $log=Join-Path $boot ('desktop-launch-'+$PID+'.log')
  Invoke-StudioChecked $Installed.Python @((Join-Path $AppRoot 'desktop\desktop_app.py')) $log
 }else{
  Remove-Item Env:QUAN_VOICE_DESKTOP -ErrorAction SilentlyContinue
  Invoke-StudioChecked $Installed.Python @((Join-Path $AppRoot 'desktop\server.py'))
 }
}
function Open-ReadyStudio([string]$AppRoot,[string]$Data,[string]$Profile,[switch]$Desktop){
 $installed=Get-InstalledStudio $AppRoot $Data
 if(-not $installed){return $false}
 Invoke-InstalledStudio $AppRoot $Data $Profile $installed -Desktop:$Desktop
 return $true
}
function Wait-StudioSetup($Mutex,[string]$AppRoot,[string]$Data,[switch]$Desktop,[switch]$AllowReady){
 $form=$null;$details=$null
 try{
  if($Desktop){
   try{
    Add-Type -AssemblyName System.Windows.Forms
    $form=New-Object System.Windows.Forms.Form;$form.Text='QUAN Voice Studio - Đang chuẩn bị';$form.Width=650;$form.Height=390;$form.StartPosition='CenterScreen'
    $label=New-Object System.Windows.Forms.Label;$label.SetBounds(18,15,600,65)
    $label.Text="Một lần cài đặt khác đang chạy. Studio sẽ mở khi sẵn sàng.`nĐóng cửa sổ này chỉ hủy lần mở thêm; không dừng bộ cài đầu tiên."
    $bar=New-Object System.Windows.Forms.ProgressBar;$bar.SetBounds(18,85,600,18);$bar.Style='Marquee'
    $details=New-Object System.Windows.Forms.TextBox;$details.SetBounds(18,118,600,190);$details.Multiline=$true;$details.ReadOnly=$true;$details.ScrollBars='Vertical'
    $cancel=New-Object System.Windows.Forms.Button;$cancel.SetBounds(468,316,150,28);$cancel.Text='Đóng lần mở thêm';$cancel.Add_Click({$form.Close()}.GetNewClosure())
    $form.Controls.AddRange(@($label,$bar,$details,$cancel));$form.Show()
   }catch{if($form){$form.Dispose()};$form=$null}
  }
  $nextProbe=[DateTime]::MinValue
  Write-Host 'Studio setup is already active. Waiting without starting a second installer.'
  while($true){
   if($form){[System.Windows.Forms.Application]::DoEvents();if($form.IsDisposed -or -not $form.Visible){return [pscustomobject]@{State='cancelled';Installed=$null}}}
   if(Enter-SetupMutex $Mutex){return [pscustomobject]@{State='acquired';Installed=$null}}
   if($AllowReady -and [DateTime]::UtcNow -ge $nextProbe){
    $nextProbe=[DateTime]::UtcNow.AddSeconds(5)
    $ready=Get-InstalledStudio $AppRoot $Data;if($ready){return [pscustomobject]@{State='ready';Installed=$ready}}
   }
   if($details){
    $log=Join-Path $Data 'bootstrap\setup.log'
    if(-not(Test-Path -LiteralPath $log)){$log=Join-Path $env:LOCALAPPDATA 'QuanVoiceStudio\bootstrap\setup.log'}
    try{$details.Text=((Get-Content -LiteralPath $log -Tail 14 -ErrorAction Stop) -join "`r`n")}catch{$details.Text='Đang chờ bộ cài đầu tiên. Kiểm tra hộp thoại Windows hoặc yêu cầu quyền quản trị nếu có.'}
   }
   Start-Sleep -Milliseconds 500
  }
 }finally{if($form){$form.Dispose()}}
}
