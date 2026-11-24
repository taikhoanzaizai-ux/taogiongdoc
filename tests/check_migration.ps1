# Filesystem simulation; native Windows junction and WSL behavior require Windows QA.
$ErrorActionPreference='Stop'
. (Join-Path (Split-Path $PSScriptRoot -Parent) 'windows/portable-data.ps1')
$testRoot=Join-Path ([IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
$env:LOCALAPPDATA=Join-Path $testRoot 'old'
$legacy=Join-Path $env:LOCALAPPDATA 'QuanVoiceStudio';$dest=Join-Path $testRoot 'app/data'
Microsoft.PowerShell.Management\New-Item -ItemType Directory -Path "$legacy/voices","$legacy/envs","$legacy/wsl/QuanVoice-Fish" -Force|Out-Null
Set-Content "$legacy/voices/quan.wav" 'voice';Set-Content "$legacy/envs/python.exe" 'environment';Set-Content "$legacy/studio.db" 'saved db';Set-Content "$legacy/wsl/QuanVoice-Fish/ext4.vhdx" 'registered virtual disk'
function Invoke-RestMethod {return $null}
function New-Item {
 param([string]$ItemType,[string]$Path,[string]$Target,[switch]$Force)
 if($ItemType -eq 'Junction'){$ItemType='SymbolicLink'}
 $p=@{ItemType=$ItemType;Path=$Path;Force=$Force};if($Target){$p.Target=$Target}
 Microsoft.PowerShell.Management\New-Item @p
}
$script:interrupted=$false
function robocopy.exe {
 $src=$args[0];$dst=$args[1]
 Microsoft.PowerShell.Management\New-Item -ItemType Directory -Path $dst -Force|Out-Null
 Get-ChildItem -LiteralPath $src -Force|ForEach-Object{Move-Item $_.FullName $dst}
 Remove-Item -LiteralPath $src -Force
 if(-not $script:interrupted){$script:interrupted=$true;throw 'Simulated power loss after a directory moved'}
 $global:LASTEXITCODE=1
}
try{
 try{Initialize-PortableData '/unused' $dest;throw 'Expected interruption'}catch{if($_.Exception.Message -notlike '*Simulated power loss*'){throw}}
 Initialize-PortableData '/unused' $dest
 if((Get-Content "$dest/voices/quan.wav") -ne 'voice'){throw 'Voice lost'}
 if((Get-Content "$legacy/envs/python.exe") -ne 'environment'){throw 'Compatibility alias missing'}
 if((Get-Content "$legacy/voices/quan.wav") -ne 'voice'){throw 'Interrupted directory alias not recovered'}
 if((Get-Content "$dest/studio.db") -ne 'saved db'){throw 'DB lost'}
 if(-not(Test-Path "$legacy/wsl/QuanVoice-Fish/ext4.vhdx")){throw 'Registered WSL disk touched'}
 Initialize-PortableData '/unused' $dest
 'Migration simulation passed: resume, voice/database, environment aliases, WSL exclusion, repeat startup.'
}finally{Microsoft.PowerShell.Management\Remove-Item -LiteralPath $testRoot -Recurse -Force}
