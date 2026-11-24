# Requires PowerShell 7 on Linux for native-command stand-ins, not Windows GUI QA.
$ErrorActionPreference='Stop'
$repo=Split-Path $PSScriptRoot -Parent
. (Join-Path $repo 'windows/launch-support.ps1')
. (Join-Path $repo 'windows/diagnose-open.ps1') -FunctionsOnly
$originalLocation=Get-Location
$testRoot=Join-Path ([IO.Path]::GetTempPath()) ('qv launcher '+[guid]::NewGuid().ToString())
$AppRoot=Join-Path $testRoot 'app with spaces [Quân]';$Data=Join-Path $AppRoot 'data'
New-Item -ItemType Directory -Force -Path (Join-Path $Data 'app-env/Scripts'),(Join-Path $Data 'bootstrap'),(Join-Path $Data 'tools/git/cmd'),(Join-Path $Data 'tools/ffmpeg/bin'),(Join-Path $AppRoot 'desktop')|Out-Null
$python=Join-Path $Data 'app-env/Scripts/python.exe';$receipt=Join-Path $Data 'bootstrap/requirements.sha256';$requirements=Join-Path $AppRoot 'desktop/requirements.txt'
Set-Content -LiteralPath $requirements 'requirements fixture'
$goodHash=(Get-FileHash -LiteralPath $requirements -Algorithm SHA256).Hash;Set-Content -LiteralPath $receipt $goodHash
Set-Content -LiteralPath (Join-Path $Data 'tools/git/cmd/git.exe') 'fixture';Set-Content -LiteralPath (Join-Path $Data 'tools/ffmpeg/bin/ffmpeg.exe') 'fixture'
$marker=Join-Path $testRoot 'launched.txt';$base=Join-Path $testRoot 'base python'
$env:QV_TEST_MARKER=$marker;$env:QV_TEST_BASE=$base
$fake=@'
#!/bin/sh
if [ "$1" = "-c" ]; then
 if [ "$QV_TEST_BROKEN" = "1" ]; then exit 1; fi
 printf '{"base_home":"%s"}\n' "$QV_TEST_BASE"
else
 if [ "$QV_TEST_NATIVE_EXIT" = "7" ]; then printf 'fatal fixture\n' >&2; exit 7; fi
 printf 'ordinary stderr progress\n' >&2
 printf '%s\n' "$1" >> "$QV_TEST_MARKER"
fi
'@
[IO.File]::WriteAllText($python,$fake.Replace("`r`n","`n"));& /bin/chmod +x $python
$child=$null;$mutex=$null
try{
 $progress=Join-Path $AppRoot 'progress [Quân].log'
 @('stdout','warning')|Write-OpenLog $progress|Out-Null
 if((Get-Content -LiteralPath $progress -Raw) -notlike '*warning*'){throw 'Diagnostic log path failed'}
 $probeLog=Join-Path $testRoot 'native-output.log'
 Invoke-StudioChecked $python @('warning-success') $probeLog
 if((Get-Content -LiteralPath $probeLog -Raw) -notlike '*ordinary stderr progress*'){throw 'Native progress was not captured'}
 $env:QV_TEST_NATIVE_EXIT='7'
 try{Invoke-StudioChecked $python @('failure') $probeLog;throw 'Non-zero native exit accepted'}catch{if($_.Exception.Message -notlike '*Command failed (7)*'){throw}}
 Remove-Item Env:QV_TEST_NATIVE_EXIT
 if($ErrorActionPreference -ne 'Stop'){throw 'Native wrapper changed caller error handling'}
 if(-not(Get-InstalledStudio $AppRoot $Data)){throw 'Installed app not recognized'}
 Set-Content -LiteralPath $receipt 'stale hash'
 if(Get-InstalledStudio $AppRoot $Data){throw 'Stale requirements accepted'}
 Set-Content -LiteralPath $receipt $goodHash;$env:QV_TEST_BROKEN='1'
 if(Get-InstalledStudio $AppRoot $Data){throw 'Broken environment accepted'}
 Remove-Item Env:QV_TEST_BROKEN
 Set-Content -LiteralPath (Join-Path $Data 'migration-from-localappdata.pending') 'incomplete'
 if(Get-InstalledStudio $AppRoot $Data){throw 'Partial migration bypassed'}
 Remove-Item -LiteralPath (Join-Path $Data 'migration-from-localappdata.pending')
 $owner=Join-Path $testRoot 'owner.ps1'
 @'
param($Name,$Ready,$Release,[int]$AutoRelease=0)
$m=New-Object Threading.Mutex($false,$Name)
$m.WaitOne()|Out-Null
Set-Content -LiteralPath $Ready 'locked'
if($AutoRelease -gt 0){Start-Sleep -Milliseconds $AutoRelease;$m.ReleaseMutex();$m.Dispose();exit 0}
while(-not(Test-Path -LiteralPath $Release)){Start-Sleep -Milliseconds 40}
# Deliberately exit without releasing: parent keeps an open handle.
exit 0
'@|Set-Content -LiteralPath $owner
 $exe=Join-Path $PSHOME 'pwsh'
 function Start-Owner([string]$Name,[int]$AutoRelease){
  $ready=Join-Path $testRoot 'owner-ready';Remove-Item -LiteralPath $ready -ErrorAction SilentlyContinue
  $release=Join-Path $testRoot 'owner-release';Remove-Item -LiteralPath $release -ErrorAction SilentlyContinue
  $p=Start-Process $exe -ArgumentList @('-NoProfile','-File',('"'+$owner+'"'),$Name,('"'+$ready+'"'),('"'+$release+'"'),$AutoRelease) -PassThru
  $deadline=[DateTime]::UtcNow.AddSeconds(10)
  while(-not(Test-Path -LiteralPath $ready)){
   if($p.HasExited -or [DateTime]::UtcNow -gt $deadline){throw 'Owner did not lock mutex'}
   Start-Sleep -Milliseconds 30
  }
  return $p
 }
 $name='qv-test-'+[guid]::NewGuid().ToString();$mutex=New-Object Threading.Mutex($false,$name)
 $child=Start-Owner $name 0
 if(Enter-SetupMutex $mutex){throw 'Live installer lock stolen'}
 # An installed app must launch even while another process holds setup ownership.
 if(-not(Open-ReadyStudio $AppRoot $Data 'all' -Desktop)){throw 'Ready launch was blocked by setup'}
 if(-not(Test-Path -LiteralPath $marker) -or (Get-Content -LiteralPath $marker -Raw) -notlike '*desktop_app.py*'){throw 'Desktop launcher did not run'}
 if(Enter-SetupMutex $mutex){throw 'Fast launch unexpectedly changed mutex ownership'}
 $wait=Wait-StudioSetup $mutex $AppRoot $Data -AllowReady
 if($wait.State -ne 'ready'){throw 'Busy setup did not hand off ready environment'}
 Set-Content -LiteralPath (Join-Path $testRoot 'owner-release') 'exit';$child.WaitForExit();$child.Dispose();$child=$null
 if(-not(Enter-SetupMutex $mutex)){throw 'Abandoned mutex not recovered'}
 $mutex.ReleaseMutex();$mutex.Dispose();$mutex=$null
 $name='qv-test-'+[guid]::NewGuid().ToString();$mutex=New-Object Threading.Mutex($false,$name)
 $child=Start-Owner $name 900
 $wait=Wait-StudioSetup $mutex $AppRoot $Data
 if($wait.State -ne 'acquired'){throw 'Wait did not resume when setup finished'}
 $mutex.ReleaseMutex();$mutex.Dispose();$mutex=$null;$child.WaitForExit();$child.Dispose();$child=$null
 'Launcher passed: native stderr progress/exit failures, installed fast launch under a live lock, stale receipt/broken env/partial migration rejected, ready handoff, abandoned mutex recovery, wait/resume, paths with spaces.'
}finally{
 if($child -and -not $child.HasExited){$child.Kill();$child.WaitForExit()}
 if($child){$child.Dispose()};if($mutex){$mutex.Dispose()}
 Set-Location $originalLocation;Remove-Item -LiteralPath $testRoot -Recurse -Force
}
