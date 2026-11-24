# Preserve relocated virtual environments through zero-size compatibility junctions.
# WSL virtual disks are moved only by WSL itself, never copied while registered.
# Windows PowerShell 5.1 emits a JSON array as one pipeline object, unlike
# newer PowerShell. Explicitly flatten arrays before consuming journal entries.
function Read-PortableJsonItems([string]$Path){
 $parsed=Get-Content -LiteralPath $Path -Raw -ErrorAction Stop|ConvertFrom-Json -ErrorAction Stop
 $pending=New-Object 'System.Collections.Generic.Stack[object]'
 $pending.Push($parsed)
 while($pending.Count){
  $value=$pending.Pop()
  if($value -is [Array]){
   for($i=$value.Count-1;$i -ge 0;$i--){$pending.Push($value[$i])}
  }elseif($null -ne $value){Write-Output $value}
 }
}
function Read-PortableAliasNames([string]$Path){
 foreach($value in (Read-PortableJsonItems $Path)){
  if($value -isnot [string] -or [string]::IsNullOrWhiteSpace($value) -or $value -in @('.','..') -or $value.IndexOfAny([char[]]'\/:') -ge 0){
   throw ('Invalid directory name in migration journal: '+$Path+'. Keep the data folders and original journal.')
  }
  Write-Output $value
 }
}
function Get-PortableFullPath([string]$Path){
 if($Path.StartsWith('\\?\UNC\',[StringComparison]::OrdinalIgnoreCase)){$Path='\\'+$Path.Substring(8)}
 elseif($Path.StartsWith('\??\') -or $Path.StartsWith('\\?\')){$Path=$Path.Substring(4)}
 return [IO.Path]::GetFullPath($Path).TrimEnd('\','/')
}
function Get-PortableLinkTarget($Item){
 $target=[string]@($Item.Target)[0]
 if(-not $target){throw ('Cannot read saved data link: '+$Item.FullName)}
 if(-not [IO.Path]::IsPathRooted($target)){$parent=if($Item.Parent){$Item.Parent.FullName}else{$Item.DirectoryName};$target=Join-Path $parent $target}
 return (Get-PortableFullPath $target)
}
function Resolve-PortableDirectoryTarget([string]$Path){
 $current=Get-PortableFullPath $Path;$visited=@()
 for($i=0;$i -lt 32;$i++){
  if($visited -contains $current){throw ('Saved directory links form a loop: '+$Path+'. Keep the original folders.')}
  $visited+=$current
  $entry=Get-Item -LiteralPath $current -Force -ErrorAction SilentlyContinue
  if(-not $entry -or -not($entry.Attributes -band [IO.FileAttributes]::ReparsePoint)){return $current}
  $current=Get-PortableLinkTarget $entry
 }
 throw ('Too many saved directory links: '+$Path+'. Keep the original folders.')
}
function Test-PortableRebuildable([string]$Name){return $Name -in @('app-env','cache','temp','logs','bootstrap','envs','sources','tools','runtimes')}
function Get-PortableTransferBytes([string]$Root){
 $todo=New-Object 'System.Collections.Generic.Stack[string]';$todo.Push($Root);[long]$bytes=0
 while($todo.Count){
  $dir=$todo.Pop()
  foreach($entry in Get-ChildItem -LiteralPath $dir -Force -ErrorAction Stop){
   if(($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -or ($dir -eq $Root -and $entry.Name -eq 'wsl')){continue}
   if($entry.PSIsContainer){$todo.Push($entry.FullName)}else{$bytes+=$entry.Length}
  }
 }
 return $bytes
}
# User files may be copied from a relocated owner, but never overwritten.
function Test-PortableDirectoryMerge([string]$Source,[string]$Destination){
 $todo=New-Object 'System.Collections.Generic.Stack[string]';$todo.Push($Source)
 while($todo.Count){
  $dir=$todo.Pop()
  foreach($entry in Get-ChildItem -LiteralPath $dir -Force -ErrorAction Stop){
   if($entry.Attributes -band [IO.FileAttributes]::ReparsePoint){throw ('Nested saved data link requires manual recovery: '+$entry.FullName+'. Original files are preserved.')}
   $dest=Join-Path $Destination $entry.FullName.Substring($Source.Length+1)
   $existing=Get-Item -LiteralPath $dest -Force -ErrorAction SilentlyContinue
   if($existing){
    if(($existing.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $entry.PSIsContainer -ne $existing.PSIsContainer){throw ('Conflicting saved file: '+$dest+'. Original files are preserved.')}
    if(-not $entry.PSIsContainer -and (Get-FileHash -LiteralPath $entry.FullName).Hash -ne (Get-FileHash -LiteralPath $dest).Hash){throw ('Conflicting saved file: '+$dest+'. Original files are preserved.')}
   }
   if($entry.PSIsContainer){$todo.Push($entry.FullName)}
  }
 }
}
function Repair-PortableRebuildableLink($Item,[string]$Dest,[string]$Data){
 $originalTarget=Get-PortableLinkTarget $Item;$target=Resolve-PortableDirectoryTarget $originalTarget;$destination=Get-PortableFullPath $Dest
 $available=Test-Path -LiteralPath $target -PathType Container
 if($target -ieq $destination -and $available){return $true}
 # A compatibility directory alias already pointing to this app is in place,
 # even if its directory was not included in a copied/extracted data folder.
 # Recreate the container for every directory name, never invent its old files.
 $directoryAlias=$Item.PSIsContainer -or ($Item.Attributes -band [IO.FileAttributes]::Directory) -or $Item.LinkType -eq 'Junction' -or -not [IO.Path]::HasExtension($Item.Name)
 $sameDestination=$target -ieq $destination -and $directoryAlias
 if(-not $directoryAlias){return $false}
 if(-not $sameDestination -and -not(Test-PortableRebuildable $Item.Name) -and (Split-Path $target -Leaf) -ine $Item.Name){return $false}
 if(Test-Path -LiteralPath $Dest){
  $current=Get-Item -LiteralPath $Dest -Force
  if($current.Attributes -band [IO.FileAttributes]::ReparsePoint){throw ('Destination folder is itself a link: '+$Dest+'. Keep both folders. Target: '+(Get-PortableLinkTarget $current))}
 }
 if($available){
  $sep=[IO.Path]::DirectorySeparatorChar
  if($destination.StartsWith($target+$sep,[StringComparison]::OrdinalIgnoreCase) -or $target.StartsWith($destination+$sep,[StringComparison]::OrdinalIgnoreCase)){throw 'Saved directory source and destination overlap. Keep both folders.'}
  if($Item.Name -ne 'cache' -and -not(Test-PortableRebuildable $Item.Name)){Test-PortableDirectoryMerge $target $destination}
  $bytes=Get-PortableTransferBytes $target
  $drive=New-Object IO.DriveInfo ([IO.Path]::GetPathRoot($destination))
  if($drive.AvailableFreeSpace -lt ($bytes+512MB)){throw ('Not enough space to copy the saved directory to '+$Dest+'. The original directory is preserved.')}
  Write-Host ('Copying saved directory from '+$target+' to '+$Dest+'. Original directory is preserved.') -ForegroundColor Cyan
  # Existing destination files and the external source remain untouched.
  & robocopy.exe $target $Dest /E /XJ /COPY:DAT /DCOPY:DAT /XC /XN /XO /R:2 /W:2 /NFL /NDL /NP|Out-Host
  if($LASTEXITCODE -ge 8){$label=if($Item.Name -eq 'cache'){'Cache'}else{'Saved directory'};throw ($label+' copy interrupted. Original source is preserved: '+$target+'. Open Studio again to resume.')}
 }else{
  Write-Host ('Recreating missing directory '+$Item.Name+' at '+$Dest+'. This restores the folder, not missing original files. Old target: '+$target) -ForegroundColor Yellow
 }
 New-Item -ItemType Directory -Path $Dest -Force|Out-Null
 $record=Join-Path $Data 'migration-link-recovery.json'
 $entries=@(if(Test-Path -LiteralPath $record){Read-PortableJsonItems $record})
 $entries+=@{link=$Item.FullName;old_target=$originalTarget;resolved_target=$target;destination=$Dest;source_available=[bool]$available;time=[DateTime]::UtcNow.ToString('o')}
 ConvertTo-Json -InputObject @($entries) -Depth 5|Set-Content -LiteralPath ($record+'.tmp') -Encoding UTF8
 Move-Item -LiteralPath ($record+'.tmp') -Destination $record -Force
 if($target -ine $destination){
  $link=Get-Item -LiteralPath $Item.FullName -Force
  if(-not($link.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw ('Saved link changed during recovery: '+$Item.FullName)}
  # Non-recursive removal of the junction itself; never delete its target.
  if($link.Attributes -band [IO.FileAttributes]::Directory){[IO.Directory]::Delete($Item.FullName)}else{[IO.File]::Delete($Item.FullName)}
  New-Item -ItemType Junction -Path $Item.FullName -Target $Dest|Out-Null
 }
 return $true
}
function Find-PortableMigrationSource([string]$Legacy,[string]$Data){
 $journal=Join-Path $Data 'migration-source.json'
 # Resume even after studio.db has already moved out of the recorded source.
 if((Test-Path -LiteralPath $journal) -and (Test-Path -LiteralPath (Join-Path $Data 'migration-from-localappdata.pending'))){
  $saved=Get-Content -LiteralPath $journal -Raw|ConvertFrom-Json
  if((Get-PortableFullPath $saved.destination) -ine (Get-PortableFullPath $Data) -or (Get-PortableFullPath $saved.legacy) -ine (Get-PortableFullPath $Legacy)){throw 'Migration journal belongs to a different folder. Keep both data folders.'}
  if(-not(Test-Path -LiteralPath $saved.source -PathType Container)){throw ('Saved migration source is unavailable: '+$saved.source+'. Reconnect that drive and open Studio again.')}
  return [string]$saved.source
 }
 $root=Get-Item -LiteralPath $Legacy -Force
 if($root.Attributes -band [IO.FileAttributes]::ReparsePoint){
  $target=Resolve-PortableDirectoryTarget (Get-PortableLinkTarget $root)
  if($target -ieq (Get-PortableFullPath $Data)){return $Legacy}
  if(Test-Path -LiteralPath (Join-Path $target 'studio.db') -PathType Leaf){return $target}
  throw ('Old library link has no studio.db: '+$target+'. Keep both folders.')
 }
 $owners=@()
 foreach($item in Get-ChildItem -LiteralPath $Legacy -Force){
  if($item.Name -eq 'wsl' -or -not($item.Attributes -band [IO.FileAttributes]::ReparsePoint)){continue}
  $target=Resolve-PortableDirectoryTarget (Get-PortableLinkTarget $item)
  if($target -ieq (Get-PortableFullPath (Join-Path $Data $item.Name))){continue}
  # Cache may be shared independently. Missing rebuildable links are not proof
  # of another voice library; include broken links even if -Directory omits them.
  if($item.Name -eq 'cache' -or ((Test-PortableRebuildable $item.Name) -and -not(Test-Path -LiteralPath $target))){continue}
  if((Split-Path $target -Leaf) -ine $item.Name){throw ('Saved data link has an unexpected target: '+$item.FullName+'. Keep the original folder.')}
  $owners+=(Split-Path $target -Parent)
 }
 $owners=@($owners|Sort-Object -Unique)
 $legacyDb=Join-Path $Legacy 'studio.db'
 if(Test-Path -LiteralPath $legacyDb -PathType Leaf){
  foreach($candidate in $owners){
   $candidateDb=Join-Path $candidate 'studio.db'
   if((Test-Path -LiteralPath $candidateDb -PathType Leaf) -and (Get-FileHash -LiteralPath $legacyDb).Hash -ne (Get-FileHash -LiteralPath $candidateDb).Hash){throw 'Conflicting saved databases. Keep both libraries; they cannot be merged automatically.'}
  }
  return $Legacy
 }
 if(-not $owners.Count){return $Legacy}
 if($owners.Count -ne 1){throw 'Old data points to multiple libraries. Keep all folders; they cannot be merged automatically.'}
 $owner=$owners[0]
 # A database can remain in C: after a partial move, while directories already
 # point elsewhere. A missing owner DB does not make those aliases a second DB.
 $ownerDb=Join-Path $owner 'studio.db'
 if(-not(Test-Path -LiteralPath $ownerDb -PathType Leaf)){
  Write-Host ('No saved database found at '+$owner+'. Recovering available directories; missing original files cannot be restored automatically.') -ForegroundColor Yellow
  return $Legacy
 }
 Write-Host ('Found previously relocated library: '+$owner) -ForegroundColor Cyan
 return $owner
}
function Initialize-PortableData([string]$AppRoot,[string]$Data){
 $legacy=Join-Path $env:LOCALAPPDATA 'QuanVoiceStudio'
 if([IO.Path]::GetFullPath($legacy).TrimEnd('\') -ieq [IO.Path]::GetFullPath($Data).TrimEnd('\')){return}
 if(-not(Test-Path -LiteralPath $legacy) -and -not((Test-Path -LiteralPath (Join-Path $Data 'migration-source.json')) -and (Test-Path -LiteralPath (Join-Path $Data 'migration-from-localappdata.pending')))){return}
 $marker=Join-Path $Data 'migration-from-localappdata.pending'
 $done=Join-Path $Data 'migration-from-localappdata.done'
 $aliases=Join-Path $Data 'migration-aliases.json'
 if(Test-Path -LiteralPath $done){return}
 if((Test-Path -LiteralPath (Join-Path $Data 'studio.db')) -and -not(Test-Path -LiteralPath $marker)){
  # Two independent existing libraries: never overwrite or merge their databases.
  Write-Host 'Using existing application-local data; the older C: library is preserved.' -ForegroundColor Yellow
  return
 }
 $originalLegacy=$legacy
 $legacy=Find-PortableMigrationSource $legacy $Data
 if((Get-PortableFullPath $legacy) -ieq (Get-PortableFullPath $Data)){return}
 if(Test-Path -LiteralPath $aliases){$null=@(Read-PortableAliasNames $aliases)}
 $oldDb=Join-Path $legacy 'studio.db';$newDb=Join-Path $Data 'studio.db'
 if((Test-Path -LiteralPath $oldDb) -and (Test-Path -LiteralPath $newDb) -and (Get-FileHash -LiteralPath $oldDb).Hash -ne (Get-FileHash -LiteralPath $newDb).Hash){throw 'Conflicting saved databases. Keep both libraries; they cannot be merged automatically.'}
 $oldFull=Get-PortableFullPath $legacy;$newFull=Get-PortableFullPath $Data
 if($newFull.StartsWith($oldFull+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or $oldFull.StartsWith($newFull+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Application data must not be inside its old data directory, or contain that directory. Extract the app to a separate folder.'}
 $legacyItem=Get-Item -LiteralPath $legacy -Force
 if($legacyItem.Attributes -band [IO.FileAttributes]::ReparsePoint){return}
 foreach($entry in Get-ChildItem -LiteralPath $legacy -Force){
  if($entry.Name -eq 'wsl' -or $entry.Name -eq 'cache' -or (Test-PortableRebuildable $entry.Name)){continue}
  $isLink=$entry.Attributes -band [IO.FileAttributes]::ReparsePoint
  if(-not $isLink -and -not $entry.PSIsContainer){continue}
  $target=if($isLink){Resolve-PortableDirectoryTarget (Get-PortableLinkTarget $entry)}else{$entry.FullName}
  $dest=Get-PortableFullPath (Join-Path $Data $entry.Name)
  if($target -ine $dest -and (Test-Path -LiteralPath $target -PathType Container)){Test-PortableDirectoryMerge $target $dest}
 }
 $ports=@(8765)
 foreach($root in @($legacy,$Data)){
  try{$record=Get-Content -LiteralPath (Join-Path $root 'server-instance.json') -Raw|ConvertFrom-Json;if($record.port -ge 1024 -and $record.port -le 65535){$ports+=([int]$record.port)}}catch{}
 }
 foreach($port in ($ports|Select-Object -Unique)){
  $running=$null;try{$running=Invoke-RestMethod ('http://127.0.0.1:'+ $port +'/api/health') -TimeoutSec 2}catch{}
  if($running -and $running.product -eq 'QuanVoiceStudio'){throw 'Close the old Studio and model windows before transferring saved data.'}
 }
 New-Item -ItemType Directory -Force -Path $Data|Out-Null
 $recordedSource=if(Test-Path -LiteralPath $marker){(Get-Content -LiteralPath $marker -Raw).Trim()}else{''}
 if(-not(Test-Path -LiteralPath $marker) -or -not(Test-Path -LiteralPath (Join-Path $Data 'migration-source.json')) -or (Get-PortableFullPath $recordedSource) -ine (Get-PortableFullPath $legacy)){
  # Require destination space before moving anything; partial transfers can resume.
  $bytes=Get-PortableTransferBytes $legacy
  $drive=New-Object IO.DriveInfo ([IO.Path]::GetPathRoot([IO.Path]::GetFullPath($Data)))
  if($drive.AvailableFreeSpace -lt ($bytes+512MB)){throw ('Not enough space for saved data on '+$drive.Name+'. Need approximately '+[math]::Round(($bytes+512MB)/1GB,1)+' GiB. Keep the original data.')}
  $names=@(Get-ChildItem -LiteralPath $legacy -Force|Where-Object{$_.Name -ne 'wsl' -and ($_.PSIsContainer -or ($_.Attributes -band [IO.FileAttributes]::ReparsePoint))}|ForEach-Object{$_.Name})
  # Save the owner before any move; the C: aliases may become two-link chains.
  $roots=@($legacy,$originalLegacy)
  foreach($entry in Get-ChildItem -LiteralPath $legacy -Force){
   if($entry.Name -eq 'wsl' -or -not($entry.Attributes -band [IO.FileAttributes]::ReparsePoint)){continue}
   $target=Resolve-PortableDirectoryTarget (Get-PortableLinkTarget $entry)
   if((Split-Path $target -Leaf) -ieq $entry.Name){$roots+=(Split-Path $target -Parent)}
  }
  @{source=$legacy;destination=$Data;legacy=$originalLegacy;path_roots=@($roots|Sort-Object -Unique)}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $Data 'migration-source.json') -Encoding UTF8
  ConvertTo-Json -InputObject $names|Set-Content -LiteralPath $aliases -Encoding UTF8
  Set-Content -LiteralPath $marker -Value $legacy -Encoding UTF8
 }
 Write-Host ('Moving saved voices, models and caches to '+$Data+'. Do not close this window.') -ForegroundColor Cyan
 foreach($item in Get-ChildItem -LiteralPath $legacy -Force){
  if($item.Name -in @('wsl','migration-from-localappdata.pending','migration-from-localappdata.done','migration-aliases.json','migration-source.json','migration-link-recovery.json')){continue}
  $dest=Join-Path $Data $item.Name
  if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){
   # Previous successful directory moves leave compatibility junctions here.
   $linkTarget=Resolve-PortableDirectoryTarget (Get-PortableLinkTarget $item)
   if(Repair-PortableRebuildableLink $item $dest $Data){continue}
   if(-not(Test-Path -LiteralPath $dest) -or $linkTarget -ine (Get-PortableFullPath $dest)){throw ('Saved data link cannot be transferred: '+$item.FullName+'. Old target: '+$linkTarget+'. Destination: '+$dest+'. Restore the original saved files; keep both folders.')}
   continue
  }
  if($item.PSIsContainer){
   & robocopy.exe $item.FullName $dest /E /MOVE /XJ /COPY:DAT /DCOPY:DAT /R:2 /W:2 /NFL /NDL /NP
   if($LASTEXITCODE -ge 8){throw ('Data transfer interrupted: '+$item.FullName+'. Open BAT_DAU.bat again to resume; do not delete either folder.')}
   if(Test-Path -LiteralPath $item.FullName){
    if(Get-ChildItem -LiteralPath $item.FullName -Force){throw ('Source directory is not empty after transfer: '+$item.FullName)}
    Remove-Item -LiteralPath $item.FullName -Force
   }
   New-Item -ItemType Junction -Path $item.FullName -Target $dest|Out-Null
  }else{
   if(Test-Path -LiteralPath $dest){
    if((Get-FileHash -LiteralPath $item.FullName).Hash -ne (Get-FileHash -LiteralPath $dest).Hash){throw ('Conflicting saved file: '+$dest+'. Original files have been preserved.')}
    Remove-Item -LiteralPath $item.FullName -Force
   }else{Move-Item -LiteralPath $item.FullName -Destination $dest}
  }
 }
 # A process may stop between a completed move and junction creation. Rebuild
 # those aliases from the journal before marking migration complete.
 if(Test-Path -LiteralPath $aliases){
  foreach($name in (Read-PortableAliasNames $aliases)){
   $oldPath=Join-Path $legacy $name;$newPath=Join-Path $Data $name
   if(-not(Test-Path -LiteralPath $oldPath) -and (Test-Path -LiteralPath $newPath)){New-Item -ItemType Junction -Path $oldPath -Target $newPath|Out-Null}
  }
 }
 Move-Item -LiteralPath $marker -Destination $done -Force
}
