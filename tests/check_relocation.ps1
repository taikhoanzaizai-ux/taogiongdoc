# Run under PowerShell 7/Linux: real filesystem aliases, simulated robocopy.
# Windows junction behavior still requires native Windows verification.
$ErrorActionPreference='Stop'
. (Join-Path (Split-Path $PSScriptRoot -Parent) 'windows/portable-data.ps1')
$testRoot=Join-Path ([IO.Path]::GetTempPath()) ('qv relocation '+[guid]::NewGuid())
$script:crashDb=$false;$script:interrupted=$false;$script:copyFailure=$false
function New-Item {
 param([string]$ItemType,[string]$Path,[string]$Target,[switch]$Force)
 if($ItemType -eq 'Junction'){$ItemType='SymbolicLink'}
 $p=@{ItemType=$ItemType;Path=$Path;Force=$Force};if($Target){$p.Target=$Target}
 Microsoft.PowerShell.Management\New-Item @p
}
function Invoke-RestMethod {return $null}
function robocopy.exe {
 $src=$args[0];$dst=$args[1]
 Microsoft.PowerShell.Management\New-Item -ItemType Directory -Path $dst -Force|Out-Null
 if($args -notcontains '/MOVE'){
  if($script:copyFailure){$global:LASTEXITCODE=8;return}
  foreach($file in Get-ChildItem -LiteralPath $src -File -Recurse){
   $target=Join-Path $dst $file.FullName.Substring($src.Length+1)
   if(-not(Test-Path -LiteralPath $target)){
    Microsoft.PowerShell.Management\New-Item -ItemType Directory -Path (Split-Path $target -Parent) -Force|Out-Null
    Copy-Item -LiteralPath $file.FullName -Destination $target
   }
  }
  $global:LASTEXITCODE=1;return
 }
 Get-ChildItem -LiteralPath $src -Force|ForEach-Object{Microsoft.PowerShell.Management\Move-Item -LiteralPath $_.FullName -Destination $dst -Force}
 Microsoft.PowerShell.Management\Remove-Item -LiteralPath $src -Force
 $global:LASTEXITCODE=1
}
function Move-Item {
 param([string]$LiteralPath,[string]$Destination,[switch]$Force)
 Microsoft.PowerShell.Management\Move-Item -LiteralPath $LiteralPath -Destination $Destination -Force:$Force
 if($script:crashDb -and -not $script:interrupted -and (Split-Path $LiteralPath -Leaf) -eq 'studio.db'){$script:interrupted=$true;throw 'Simulated interruption after DB move'}
}
function Fixture([string]$Name){
 $base=Join-Path $testRoot $Name;$env:LOCALAPPDATA=Join-Path $base 'C local'
 $legacy=Join-Path $env:LOCALAPPDATA 'QuanVoiceStudio';$owner=Join-Path $base 'D old app/data';$dest=Join-Path $base 'E Phần mềm mới/data'
 New-Item -ItemType Directory -Path $legacy -Force|Out-Null
 foreach($name in @('app-env','voices','envs','cache','bootstrap','outputs')){
  New-Item -ItemType Directory -Path (Join-Path $owner $name) -Force|Out-Null
  New-Item -ItemType SymbolicLink -Path (Join-Path $legacy $name) -Target (Join-Path $owner $name)|Out-Null
 }
 foreach($path in @((Join-Path $owner 'wsl/Fish'),(Join-Path $dest 'bootstrap'))){New-Item -ItemType Directory -Path $path -Force|Out-Null}
 Set-Content -LiteralPath (Join-Path $owner 'studio.db') 'original saved library'
 Set-Content -LiteralPath (Join-Path $owner 'voices/quan.wav') 'VOICE BYTES'
 Set-Content -LiteralPath (Join-Path $owner 'envs/python.exe') 'MODEL ENV'
 Set-Content -LiteralPath (Join-Path $owner 'cache/weights.bin') 'WEIGHTS'
 Set-Content -LiteralPath (Join-Path $owner 'wsl/Fish/ext4.vhdx') 'REGISTERED WSL'
 Set-Content -LiteralPath (Join-Path $owner 'migration-from-localappdata.done') $legacy
 # State left by the version in the user's screenshot, before its alias error.
 Set-Content -LiteralPath (Join-Path $dest 'migration-from-localappdata.pending') $legacy
 Set-Content -LiteralPath (Join-Path $dest 'migration-aliases.json') '["app-env","voices"]'
 Set-Content -LiteralPath (Join-Path $dest 'bootstrap/mo-app.log') 'CURRENT LAUNCH LOG'
 return [pscustomobject]@{Legacy=$legacy;Owner=$owner;Dest=$dest}
}
try{
 $f=Fixture 'resume after db';$script:crashDb=$true
 try{Initialize-PortableData '/unused' $f.Dest;throw 'Expected crash'}catch{if($_.Exception.Message -notlike '*Simulated interruption*'){throw}}
 if(-not(Test-Path -LiteralPath (Join-Path $f.Dest 'studio.db'))){throw 'DB did not move before interruption'}
 if(Test-Path -LiteralPath (Join-Path $f.Owner 'studio.db')){throw 'Wrong test state'}
 Initialize-PortableData '/unused' $f.Dest
 foreach($pair in @(@('voices/quan.wav','VOICE BYTES'),@('envs/python.exe','MODEL ENV'),@('cache/weights.bin','WEIGHTS'))){
  foreach($root in @($f.Dest,$f.Owner,$f.Legacy)){if((Get-Content -LiteralPath (Join-Path $root $pair[0])) -ne $pair[1]){throw ('Data/compatibility alias lost: '+$root)}}
 }
 if((Get-Content -LiteralPath (Join-Path $f.Dest 'bootstrap/mo-app.log')) -ne 'CURRENT LAUNCH LOG'){throw 'Current launch log lost'}
 if((Get-Content -LiteralPath (Join-Path $f.Owner 'wsl/Fish/ext4.vhdx')) -ne 'REGISTERED WSL'){throw 'Registered WSL disk moved'}
 if((Get-Content -LiteralPath (Join-Path $f.Dest 'migration-from-localappdata.done')) -ne $f.Owner){throw 'Wrong path rewrite source'}
 Initialize-PortableData '/unused' $f.Dest
 $script:crashDb=$false
 $f=Fixture 'independent';Remove-Item -LiteralPath (Join-Path $f.Dest 'migration-from-localappdata.pending')
 Set-Content -LiteralPath (Join-Path $f.Dest 'studio.db') 'independent new library'
 Initialize-PortableData '/unused' $f.Dest
 if((Get-Content -LiteralPath (Join-Path $f.Dest 'studio.db')) -ne 'independent new library'){throw 'Existing library overwritten'}
 if(-not(Test-Path -LiteralPath (Join-Path $f.Owner 'studio.db'))){throw 'Independent old library changed'}
 $f=Fixture 'conflict';Set-Content -LiteralPath (Join-Path $f.Dest 'studio.db') 'conflicting database'
 try{Initialize-PortableData '/unused' $f.Dest;throw 'Conflict accepted'}catch{if($_.Exception.Message -notlike '*Conflicting saved databases*'){throw}}
 if((Get-Content -LiteralPath (Join-Path $f.Owner 'voices/quan.wav')) -ne 'VOICE BYTES'){throw 'Conflict moved data'}
 $f=Fixture 'multiple owners';$other=Join-Path $testRoot 'another library/voices';New-Item -ItemType Directory -Path $other -Force|Out-Null
 Remove-Item -LiteralPath (Join-Path $f.Legacy 'voices');New-Item -ItemType SymbolicLink -Path (Join-Path $f.Legacy 'voices') -Target $other|Out-Null
 try{Initialize-PortableData '/unused' $f.Dest;throw 'Multiple owners accepted'}catch{if($_.Exception.Message -notlike '*multiple libraries*'){throw}}
 $f=Fixture 'unidentified';Remove-Item -LiteralPath (Join-Path $f.Owner 'studio.db')
 Initialize-PortableData '/unused' $f.Dest
 if((Get-Content -LiteralPath (Join-Path $f.Dest 'voices/quan.wav')) -ne 'VOICE BYTES'){throw 'DB-less owner lost available voice audio'}
 if((Get-Content -LiteralPath (Join-Path $f.Owner 'voices/quan.wav')) -ne 'VOICE BYTES'){throw 'Original DB-less owner changed'}
 if(Test-Path -LiteralPath (Join-Path $f.Dest 'studio.db')){throw 'Invented missing database'}
 foreach($mode in @('legacy only DB','identical DBs','conflicting DBs','missing old directory','voice conflict','copy interrupted')){
  $f=Fixture $mode
  Set-Content -LiteralPath (Join-Path $f.Legacy 'studio.db') 'original saved library'
  if($mode -in @('legacy only DB','missing old directory','voice conflict','copy interrupted')){Remove-Item -LiteralPath (Join-Path $f.Owner 'studio.db')}
  if($mode -eq 'conflicting DBs'){
   Set-Content -LiteralPath (Join-Path $f.Legacy 'studio.db') 'ANOTHER DATABASE'
   try{Initialize-PortableData '/unused' $f.Dest;throw 'Conflicting DBs accepted'}catch{if($_.Exception.Message -notlike '*Conflicting saved databases*'){throw}}
   if(Test-Path -LiteralPath (Join-Path $f.Dest 'voices/quan.wav')){throw 'Conflict copied user data'}
   continue
  }
  if($mode -eq 'missing old directory'){Microsoft.PowerShell.Management\Remove-Item -LiteralPath (Join-Path $f.Owner 'voices') -Recurse -Force}
  if($mode -eq 'voice conflict'){
   New-Item -ItemType Directory -Path (Join-Path $f.Dest 'voices') -Force|Out-Null
   Set-Content -LiteralPath (Join-Path $f.Dest 'voices/quan.wav') 'DIFFERENT VOICE'
   try{Initialize-PortableData '/unused' $f.Dest;throw 'Voice conflict accepted'}catch{if($_.Exception.Message -notlike '*Conflicting saved file*'){throw}}
   if(-not(Test-Path -LiteralPath (Join-Path $f.Legacy 'studio.db'))){throw 'DB moved before detecting voice conflict'}
   if((Get-Content -LiteralPath (Join-Path $f.Dest 'voices/quan.wav')) -ne 'DIFFERENT VOICE'){throw 'Destination voice overwritten'}
   continue
  }
  if($mode -eq 'copy interrupted'){
   $script:copyFailure=$true
   try{Initialize-PortableData '/unused' $f.Dest;throw 'Failed copy accepted'}catch{if($_.Exception.Message -notlike '*copy interrupted*'){throw}}
   $script:copyFailure=$false
   if((Get-Content -LiteralPath (Join-Path $f.Owner 'voices/quan.wav')) -ne 'VOICE BYTES'){throw 'Copy failure lost source voice'}
  }
  Initialize-PortableData '/unused' $f.Dest
  if((Get-Content -LiteralPath (Join-Path $f.Dest 'studio.db')) -ne 'original saved library'){throw 'Split library lost database'}
  if($mode -ne 'missing old directory'){
   if((Get-Content -LiteralPath (Join-Path $f.Dest 'voices/quan.wav')) -ne 'VOICE BYTES'){throw 'Split library lost voice'}
   if((Get-Content -LiteralPath (Join-Path $f.Owner 'voices/quan.wav')) -ne 'VOICE BYTES'){throw 'Split library source voice removed'}
  }elseif(-not(Test-Path -LiteralPath (Join-Path $f.Dest 'voices') -PathType Container)){throw 'Missing foreign container blocks launch'}
  if((Get-Content -LiteralPath (Join-Path $f.Dest 'envs/python.exe')) -ne 'MODEL ENV'){throw 'Split library lost model environment'}
  $journal=Get-Content -LiteralPath (Join-Path $f.Dest 'migration-source.json') -Raw|ConvertFrom-Json
  if($journal.path_roots -notcontains $f.Owner){throw 'Foreign settings root not recorded'}
  Initialize-PortableData '/unused' $f.Dest
 }
 $f=Fixture 'multiple split owners with C database'
 Set-Content -LiteralPath (Join-Path $f.Legacy 'studio.db') 'original saved library'
 $other=Join-Path $testRoot 'split owner/voices';New-Item -ItemType Directory -Path $other -Force|Out-Null
 Set-Content -LiteralPath (Join-Path $other 'quan.wav') 'SPLIT VOICE'
 Remove-Item -LiteralPath (Join-Path $f.Legacy 'voices');New-Item -ItemType SymbolicLink -Path (Join-Path $f.Legacy 'voices') -Target $other|Out-Null
 Initialize-PortableData '/unused' $f.Dest
 if((Get-Content -LiteralPath (Join-Path $f.Dest 'voices/quan.wav')) -ne 'SPLIT VOICE'){throw 'Multiple split owners lost C database voice'}
 $f=Fixture 'normal directory conflict'
 Set-Content -LiteralPath (Join-Path $f.Legacy 'studio.db') 'original saved library'
 Remove-Item -LiteralPath (Join-Path $f.Legacy 'voices')
 New-Item -ItemType Directory -Path (Join-Path $f.Legacy 'voices') -Force|Out-Null
 Set-Content -LiteralPath (Join-Path $f.Legacy 'voices/quan.wav') 'LOCAL C VOICE'
 New-Item -ItemType Directory -Path (Join-Path $f.Dest 'voices') -Force|Out-Null
 Set-Content -LiteralPath (Join-Path $f.Dest 'voices/quan.wav') 'DESTINATION VOICE'
 try{Initialize-PortableData '/unused' $f.Dest;throw 'Normal conflict accepted'}catch{if($_.Exception.Message -notlike '*Conflicting saved file*'){throw}}
 if(-not(Test-Path -LiteralPath (Join-Path $f.Legacy 'studio.db'))){throw 'Normal directory conflict moved DB'}
 $f=Fixture 'legacy removed during resume';$script:crashDb=$true;$script:interrupted=$false
 try{Initialize-PortableData '/unused' $f.Dest;throw 'Expected interruption'}catch{if($_.Exception.Message -notlike '*Simulated interruption*'){throw}}
 Microsoft.PowerShell.Management\Remove-Item -LiteralPath $f.Legacy -Recurse -Force
 Initialize-PortableData '/unused' $f.Dest
 if(-not(Test-Path -LiteralPath (Join-Path $f.Dest 'migration-from-localappdata.done'))){throw 'Resume required removed C: aliases'}
 $script:crashDb=$false
 $f=Fixture 'root legacy alias';Microsoft.PowerShell.Management\Remove-Item -LiteralPath $f.Legacy -Recurse -Force
 New-Item -ItemType SymbolicLink -Path $f.Legacy -Target $f.Owner|Out-Null
 Initialize-PortableData '/unused' $f.Dest
 if((Get-Content -LiteralPath (Join-Path $f.Dest 'voices/quan.wav')) -ne 'VOICE BYTES'){throw 'Root legacy alias ignored'}
 $f=Fixture 'disconnected source'
 @{source=(Join-Path $testRoot 'disconnected');destination=$f.Dest;legacy=$f.Legacy}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $f.Dest 'migration-source.json')
 try{Initialize-PortableData '/unused' $f.Dest;throw 'Disconnected source accepted'}catch{if($_.Exception.Message -notlike '*Saved migration source is unavailable*'){throw}}
 $f=Fixture 'wrong journal'
 @{source=$f.Owner;destination=(Join-Path $testRoot 'other destination');legacy=$f.Legacy}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $f.Dest 'migration-source.json')
 try{Initialize-PortableData '/unused' $f.Dest;throw 'Wrong journal accepted'}catch{if($_.Exception.Message -notlike '*journal belongs to a different folder*'){throw}}
 $env:LOCALAPPDATA=Join-Path $testRoot 'missing core C';$legacy=Join-Path $env:LOCALAPPDATA 'QuanVoiceStudio';$dest=Join-Path $testRoot 'missing core E/data'
 New-Item -ItemType Directory -Path $legacy -Force|Out-Null
 New-Item -ItemType SymbolicLink -Path (Join-Path $legacy 'app-env') -Target (Join-Path $dest 'app-env')|Out-Null
 New-Item -ItemType SymbolicLink -Path (Join-Path $legacy 'cache') -Target (Join-Path $dest 'cache')|Out-Null
 Set-Content -LiteralPath (Join-Path $legacy 'studio.db') 'preserved voice database'
 Initialize-PortableData '/unused' $dest
 if(-not(Test-Path -LiteralPath (Join-Path $dest 'app-env') -PathType Container)){throw 'Missing app venv cannot be rebuilt'}
 if(-not(Test-Path -LiteralPath (Join-Path $dest 'cache') -PathType Container)){throw 'Missing cache still blocks opening'}
 if((Get-Content -LiteralPath (Join-Path $dest 'studio.db')) -ne 'preserved voice database'){throw 'Core rebuild lost database'}
 # A shared/external cache must not be mistaken for another voice database.
 $env:LOCALAPPDATA=Join-Path $testRoot 'shared cache C';$legacy=Join-Path $env:LOCALAPPDATA 'QuanVoiceStudio';$dest=Join-Path $testRoot 'shared cache E/data';$external=Join-Path $testRoot 'shared HF cache'
 foreach($p in @($legacy,$external,(Join-Path $dest 'cache'))){New-Item -ItemType Directory -Path $p -Force|Out-Null}
 Set-Content -LiteralPath (Join-Path $legacy 'studio.db') 'VOICE DB'
 Set-Content -LiteralPath (Join-Path $external 'weights.bin') 'ORIGINAL WEIGHTS'
 Set-Content -LiteralPath (Join-Path $external 'refs.txt') 'OLD REF'
 Set-Content -LiteralPath (Join-Path $dest 'cache/refs.txt') 'NEW REF'
 New-Item -ItemType SymbolicLink -Path (Join-Path $legacy 'cache') -Target $external|Out-Null
 $script:copyFailure=$true
 try{Initialize-PortableData '/unused' $dest;throw 'Copy failure accepted'}catch{if($_.Exception.Message -notlike '*Cache copy interrupted*'){throw}}
 if((Get-PortableLinkTarget (Get-Item -LiteralPath (Join-Path $legacy 'cache') -Force)) -ne $external){throw 'Failed copy changed original alias'}
 $script:copyFailure=$false;Initialize-PortableData '/unused' $dest
 if((Get-Content -LiteralPath (Join-Path $dest 'cache/weights.bin')) -ne 'ORIGINAL WEIGHTS'){throw 'Cache not copied'}
 if((Get-Content -LiteralPath (Join-Path $external 'weights.bin')) -ne 'ORIGINAL WEIGHTS'){throw 'External cache moved or deleted'}
 if((Get-Content -LiteralPath (Join-Path $dest 'cache/refs.txt')) -ne 'NEW REF'){throw 'Existing destination cache overwritten'}
 if((Get-PortableLinkTarget (Get-Item -LiteralPath (Join-Path $legacy 'cache') -Force)) -ne (Join-Path $dest 'cache')){throw 'Compatibility cache alias not updated'}
 $record=Get-Content -LiteralPath (Join-Path $dest 'migration-link-recovery.json') -Raw|ConvertFrom-Json
 if($record[0].old_target -ne $external){throw 'Original cache target not recorded'}
 # A broken alias elsewhere can be replaced without creating its missing target.
 $env:LOCALAPPDATA=Join-Path $testRoot 'dead cache C';$legacy=Join-Path $env:LOCALAPPDATA 'QuanVoiceStudio';$dest=Join-Path $testRoot 'dead cache E/data';$dead=Join-Path $testRoot 'old missing drive/cache'
 New-Item -ItemType Directory -Path $legacy -Force|Out-Null
 New-Item -ItemType SymbolicLink -Path (Join-Path $legacy 'cache') -Target $dead|Out-Null
 Set-Content -LiteralPath (Join-Path $legacy 'studio.db') 'SAVED VOICES'
 Initialize-PortableData '/unused' $dest
 if(Test-Path -LiteralPath $dead){throw 'Recreated a folder outside the selected drive'}
 if(-not(Test-Path -LiteralPath (Join-Path $dest 'cache'))){throw 'Missing cache still blocks opening'}
 if((Get-Content -LiteralPath (Join-Path $dest 'studio.db')) -ne 'SAVED VOICES'){throw 'Cache fix changed database'}
 # Follow aliases left by more than one earlier relocation.
 $f=Fixture 'multiple hops';$hop=Join-Path $testRoot 'intermediate app/data';New-Item -ItemType Directory -Path $hop -Force|Out-Null
 foreach($name in @('app-env','voices','envs','cache','bootstrap','outputs')){
  New-Item -ItemType SymbolicLink -Path (Join-Path $hop $name) -Target (Join-Path $f.Owner $name)|Out-Null
  Remove-Item -LiteralPath (Join-Path $f.Legacy $name)
  New-Item -ItemType SymbolicLink -Path (Join-Path $f.Legacy $name) -Target (Join-Path $hop $name)|Out-Null
 }
 Initialize-PortableData '/unused' $f.Dest
 if((Get-Content -LiteralPath (Join-Path $f.Legacy 'voices/quan.wav')) -ne 'VOICE BYTES'){throw 'Multiple-hop aliases lost voices'}
 # An in-place missing container must not block launching, including names
 # not in the rebuildable list. Missing original audio is not fabricated.
 $env:LOCALAPPDATA=Join-Path $testRoot 'missing voices C';$legacy=Join-Path $env:LOCALAPPDATA 'QuanVoiceStudio';$dest=Join-Path $testRoot 'missing voices E/data'
 New-Item -ItemType Directory -Path $legacy -Force|Out-Null
 $names=@('voices','jobs','outputs','preview_refs','uploads','references','models','custom-directory')
 foreach($name in $names){New-Item -ItemType SymbolicLink -Path (Join-Path $legacy $name) -Target (Join-Path $dest $name)|Out-Null}
 Set-Content -LiteralPath (Join-Path $legacy 'studio.db') 'VOICE DB'
 Initialize-PortableData '/unused' $dest
 foreach($name in $names){if(-not(Test-Path -LiteralPath (Join-Path $dest $name) -PathType Container)){throw ('Missing container still blocks launch: '+$name)}}
 if(Get-ChildItem -LiteralPath (Join-Path $dest 'voices') -File){throw 'Invented voice audio'}
 if((Get-Content -LiteralPath (Join-Path $dest 'studio.db')) -ne 'VOICE DB'){throw 'Container recreation changed database'}
 $recovery=Get-Content -LiteralPath (Join-Path $dest 'migration-link-recovery.json') -Raw|ConvertFrom-Json
 if($recovery.Count -ne $names.Count -or @($recovery|Where-Object{$_.source_available}).Count){throw 'Missing source not reported accurately'}
 $a=Join-Path $testRoot 'cycle-a';$b=Join-Path $testRoot 'cycle-b'
 New-Item -ItemType SymbolicLink -Path $a -Target $b|Out-Null;New-Item -ItemType SymbolicLink -Path $b -Target $a|Out-Null
 try{Resolve-PortableDirectoryTarget $a;throw 'Cycle accepted'}catch{if($_.Exception.Message -notlike '*links form a loop*'){throw}}
 'Relocation passed: previous C->D aliases to E, resume after DB move, two-hop aliases, voices/model cache/env preservation, current logs, independent/conflicting DBs, multiple/unknown owners, WSL exclusion, repeat opening.'
}finally{Microsoft.PowerShell.Management\Remove-Item -LiteralPath $testRoot -Recurse -Force}
