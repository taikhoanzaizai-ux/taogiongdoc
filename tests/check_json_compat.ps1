# Exercise Windows PowerShell 5.1 JSON-array pipeline semantics on PowerShell 7.
# This checks only pipeline behavior; it is not native Windows GUI validation.
$ErrorActionPreference='Stop'
if($PSVersionTable.PSVersion.Major -ge 6){
 # Windows PowerShell 5.1 has one scalar ChildPath parameter. PowerShell 7
 # additionally accepts trailing child paths, so retain the older binding too.
 function Join-Path {
  [CmdletBinding()]
  param([Parameter(Position=0,Mandatory=$true)][string]$Path,[Parameter(Position=1,Mandatory=$true)][string]$ChildPath)
  Microsoft.PowerShell.Management\Join-Path -Path $Path -ChildPath $ChildPath
 }
 function ConvertFrom-Json {
  [CmdletBinding()]
  param([Parameter(ValueFromPipeline=$true)][string]$InputObject)
  process{
   $parsed=Microsoft.PowerShell.Utility\ConvertFrom-Json -InputObject $InputObject -NoEnumerate
   $PSCmdlet.WriteObject($parsed,$false)
  }
 }
}
$root=Split-Path $PSScriptRoot -Parent
. (Join-Path $root 'windows/portable-data.ps1')
$temp=Join-Path ([IO.Path]::GetTempPath()) ('qv json [Quân] '+[guid]::NewGuid())
$null=Microsoft.PowerShell.Management\New-Item -ItemType Directory -Path $temp
$journal=Join-Path $temp 'aliases.json'
try{
 # The old @(... ConvertFrom-Json) leaves one object[] as the loop item.
 '["app-env","bootstrap","cache","envs","jobs","logs","models","outputs","preview_refs","sources","tools","voices"]'|Set-Content -LiteralPath $journal -Encoding UTF8
 $old=@(Get-Content -LiteralPath $journal -Raw|ConvertFrom-Json)
 if($old.Count -ne 1 -or $old[0] -isnot [array]){throw 'Compatibility fixture did not retain the legacy JSON array object'}
 $names=@(Read-PortableAliasNames $journal)
 if($names.Count -ne 12 -or @($names|Where-Object{$_ -isnot [string]}).Count){throw 'Names were not flattened into twelve strings'}
 foreach($name in $names){$null=Join-Path $temp $name}
 foreach($json in @('[]','["voices"]','"voices"','[["voices","custom folder"],["outputs"]]')){
  $json|Set-Content -LiteralPath $journal -Encoding UTF8
  $items=@(Read-PortableAliasNames $journal)
  $expected=switch($json){'[]'{0};'["voices"]'{1};'"voices"'{1};default{3}}
  if($items.Count -ne $expected){throw ('Alias count mismatch: '+$json)}
  if($expected -eq 3 -and ($items -join '|') -ne 'voices|custom folder|outputs'){throw 'Nested order/space in name changed'}
 }
 foreach($json in @('["../voices"]','[".."]','["E:\\voices"]','["voices",{}]','[5]')){
  $json|Set-Content -LiteralPath $journal -Encoding UTF8
  try{$null=@(Read-PortableAliasNames $journal);throw 'Invalid alias accepted'}catch{if($_.Exception.Message -notlike '*Invalid directory name*'){throw}}
 }
 '[[{"id":1},{"id":2}],{"id":3}]'|Set-Content -LiteralPath $journal -Encoding UTF8
 $entries=@(Read-PortableJsonItems $journal)
 if(($entries.id -join ',') -ne '1,2,3'){throw 'Nested recovery log not flattened in order'}
}finally{Microsoft.PowerShell.Management\Remove-Item -LiteralPath $temp -Recurse -Force}
& (Join-Path $PSScriptRoot 'check_migration.ps1')
& (Join-Path $PSScriptRoot 'check_relocation.ps1')
'JSON compatibility passed: PS5.1 array object, scalar/empty/nested journals, safe names, recovery log, interrupted transfer and repeat launch.'
