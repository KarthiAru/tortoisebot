#Requires -RunAsAdministrator
<#
.SYNOPSIS
  Inspect a provisioned TortoiseBot Raspberry Pi SD card without modifying it.

.DESCRIPTION
  Checks the Windows-visible system-boot partition for rendered provisioning files,
  verifies that the firstboot hook and SSH public key are present, and shows
  boot logs written back to the FAT boot partition.
#>
[CmdletBinding()]
param(
  [int]$DiskNumber = -1,
  [string]$DriveLetter,
  [string]$Username = "tortoisebot",
  [string]$PublicKeyPath = (Join-Path $env:USERPROFILE ".ssh\id_ed25519.pub"),
  [int]$MaxDiskSizeGB = 128
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) {
  Write-Host "==> $Message" -ForegroundColor Cyan
}

function Normalize-DriveLetter([string]$Letter) {
  if ([string]::IsNullOrWhiteSpace($Letter)) { return $null }
  $normalized = $Letter.Trim().TrimEnd(':', '\').ToUpperInvariant()
  if ($normalized.Length -ne 1 -or $normalized -notmatch '^[A-Z]$') {
    throw "Drive letter must look like E or E:. Got '$Letter'."
  }
  return $normalized
}

function Resolve-DiskNumberFromDriveLetter([string]$Letter) {
  $normalized = Normalize-DriveLetter $Letter
  $partitions = @(Get-Partition -DriveLetter $normalized -ErrorAction Stop)
  if ($partitions.Count -ne 1) {
    throw "Drive ${normalized}: matched $($partitions.Count) partitions; refusing to guess."
  }
  return [int]$partitions[0].DiskNumber
}

function Get-AvailableDriveLetter {
  $used = @(Get-Volume | Where-Object DriveLetter | ForEach-Object { $_.DriveLetter.ToString().ToUpperInvariant() })
  foreach ($letter in 'E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T','U','V','W','X','Y','Z') {
    if ($used -notcontains $letter) { return $letter }
  }
  return $null
}

function Select-TargetDiskNumber {
  if (-not [string]::IsNullOrWhiteSpace($DriveLetter)) {
    return Resolve-DiskNumberFromDriveLetter $DriveLetter
  }
  if ($DiskNumber -ge 0) { return $DiskNumber }

  Write-Host "Drive-letter volumes:" -ForegroundColor Cyan
  Get-Volume |
    Where-Object DriveLetter |
    Sort-Object DriveLetter |
    Select-Object DriveLetter, FileSystemLabel, FileSystem, SizeRemaining, Size |
    Format-Table -AutoSize | Out-Host

  Write-Host "Physical disks:" -ForegroundColor Cyan
  Get-Disk |
    Sort-Object Number |
    Select-Object Number, FriendlyName, BusType, Size, PartitionStyle, OperationalStatus |
    Format-Table -AutoSize | Out-Host

  $selection = Read-Host "Enter the SD card drive letter, like E, or physical disk number"
  if ($selection -match '^\s*[A-Za-z]:?\s*$') { return Resolve-DiskNumberFromDriveLetter $selection }
  if ($selection -match '^\s*\d+\s*$') { return [int]$selection }
  throw "Could not understand '$selection'."
}

function Find-SystemBootPartition([int]$TargetDiskNumber) {
  $partitions = @(Get-Partition -DiskNumber $TargetDiskNumber -ErrorAction Stop | Sort-Object PartitionNumber)
  foreach ($partition in $partitions) {
    $volume = $partition | Get-Volume -ErrorAction SilentlyContinue
    if (-not $volume) { continue }
    $isSystemBoot = $volume.FileSystemLabel -eq "system-boot" -or $volume.FileSystemLabel -eq "system-boot-0"
    $isLikelyBoot = $volume.FileSystem -eq "FAT32" -and $partition.Size -lt 1GB
    if ($isSystemBoot -or $isLikelyBoot) { return $partition }
  }
  return $null
}

function Mount-SystemBoot([int]$TargetDiskNumber) {
  $partition = Find-SystemBootPartition -TargetDiskNumber $TargetDiskNumber
  if (-not $partition) { throw "Could not find a FAT32 system-boot partition on disk $TargetDiskNumber." }
  $volume = $partition | Get-Volume -ErrorAction Stop
  if (-not $volume.DriveLetter) {
    $letter = Get-AvailableDriveLetter
    if (-not $letter) { throw "No free drive letter is available to mount system-boot." }
    Write-Info "Assigning ${letter}: to system-boot partition $($partition.PartitionNumber)"
    Set-Partition -DiskNumber $TargetDiskNumber -PartitionNumber $partition.PartitionNumber -NewDriveLetter $letter -ErrorAction Stop
    Start-Sleep -Seconds 2
    $volume = Get-Volume -DriveLetter $letter -ErrorAction Stop
  }
  return "$($volume.DriveLetter):\"
}

function Show-Check([string]$Name, [bool]$Pass, [string]$Detail = "") {
  $color = if ($Pass) { "Green" } else { "Red" }
  $status = if ($Pass) { "PASS" } else { "FAIL" }
  if ([string]::IsNullOrWhiteSpace($Detail)) {
    Write-Host ("[{0}] {1}" -f $status, $Name) -ForegroundColor $color
  }
  else {
    Write-Host ("[{0}] {1}: {2}" -f $status, $Name, $Detail) -ForegroundColor $color
  }
}

function Show-LogFile([string]$Path, [string]$Title) {
  if (Test-Path $Path) {
    Show-Check "$Title exists" $true $Path
    Write-Host ""
    Write-Host "---- $Title ----" -ForegroundColor Cyan
    Get-Content -Path $Path | Select-Object -Last 80 | Out-Host
  }
  else {
    Show-Check "$Title exists" $false "not found yet; boot the Pi once, power it off, then inspect again"
  }
}

$targetDiskNumber = Select-TargetDiskNumber
$disk = Get-Disk -Number $targetDiskNumber -ErrorAction Stop
$diskSizeGB = [math]::Round($disk.Size / 1GB, 2)
if ($disk.Size -ge ($MaxDiskSizeGB * 1GB)) {
  throw "Disk $targetDiskNumber is $diskSizeGB GB. Refusing to inspect a disk at or above $MaxDiskSizeGB GB."
}

Write-Info "Inspecting disk $targetDiskNumber ($($disk.FriendlyName), $($disk.BusType), $diskSizeGB GB)"
Get-Partition -DiskNumber $targetDiskNumber | Sort-Object PartitionNumber | Format-Table -AutoSize | Out-Host

$bootRoot = Mount-SystemBoot -TargetDiskNumber $targetDiskNumber
Write-Info "system-boot mounted at $bootRoot"

$userDataPath = Join-Path $bootRoot "user-data"
$metaDataPath = Join-Path $bootRoot "meta-data"
$networkConfigPath = Join-Path $bootRoot "network-config"
$cmdlinePath = Join-Path $bootRoot "cmdline.txt"
$firstbootPath = Join-Path $bootRoot "tortoisebot-firstboot.sh"

Show-Check "user-data exists" (Test-Path $userDataPath) $userDataPath
Show-Check "meta-data exists" (Test-Path $metaDataPath) $metaDataPath
Show-Check "network-config exists" (Test-Path $networkConfigPath) $networkConfigPath
Show-Check "cmdline.txt exists" (Test-Path $cmdlinePath) $cmdlinePath
Show-Check "firstboot script exists" (Test-Path $firstbootPath) $firstbootPath

if (-not (Test-Path $userDataPath)) { throw "No user-data file found on system-boot. The SD card was not seeded." }

$userData = Get-Content -Raw -Path $userDataPath
$metaData = if (Test-Path $metaDataPath) { Get-Content -Raw -Path $metaDataPath } else { "" }
$networkConfig = if (Test-Path $networkConfigPath) { Get-Content -Raw -Path $networkConfigPath } else { "" }
$cmdline = if (Test-Path $cmdlinePath) { Get-Content -Raw -Path $cmdlinePath } else { "" }
$firstboot = if (Test-Path $firstbootPath) { Get-Content -Raw -Path $firstbootPath } else { "" }
$expectedKey = if (Test-Path $PublicKeyPath) { (Get-Content -Raw -Path $PublicKeyPath).Trim() } else { "" }

Show-Check "cloud-config header" ($userData.StartsWith("#cloud-config"))
Show-Check "no unresolved template tokens in user-data" ($userData -notmatch "__[A-Z0-9_]+__")
Show-Check "no unresolved template tokens in firstboot" ($firstboot -notmatch "__[A-Z0-9_]+__")
Show-Check "username rendered" ($userData -match ("name:\s*" + [regex]::Escape($Username))) $Username
Show-Check "network-config has Wi-Fi block" ($networkConfig -match "wifis:")
Show-Check "meta-data has current manual SSH seed" ($metaData -match "manual-ssh-v[0-9]+")
Show-Check "firstboot cmdline hook installed" ($cmdline -match "systemd\.run=/boot/firmware/tortoisebot-firstboot\.sh")
Show-Check "firstboot creates SSH user" ($firstboot -match "useradd -m -s /bin/bash")
Show-Check "firstboot enables SSH password auth" ($firstboot -match "PasswordAuthentication yes")
Show-Check "firstboot writes authorized_keys" ($firstboot -match "authorized_keys")


$keyCount = ([regex]::Matches(($userData + "`n" + $firstboot), "ssh-(ed25519|rsa|ecdsa)\s+[A-Za-z0-9+/=]+")).Count
Show-Check "provisioning contains at least one SSH public key" ($keyCount -gt 0) "$keyCount key(s)"
if ([string]::IsNullOrWhiteSpace($expectedKey)) {
  Show-Check "local expected public key exists" $false $PublicKeyPath
}
else {
  Show-Check "provisioning contains local public key" (($userData.Contains($expectedKey)) -or ($firstboot.Contains($expectedKey))) $PublicKeyPath
}

Show-LogFile -Path (Join-Path $bootRoot "tortoisebot-firstboot.log") -Title "tortoisebot-firstboot.log"
Show-LogFile -Path (Join-Path $bootRoot "tortoisebot-cloud-init-status.log") -Title "tortoisebot-cloud-init-status.log"

Write-Host ""
Write-Host "Next diagnostic loop:" -ForegroundColor Yellow
Write-Host "  1. Boot the Raspberry Pi once with this SD card and wait 2-3 minutes after Wi-Fi appears."
Write-Host "  2. Power it off, put the SD card back in this PC, then rerun this inspector."
Write-Host "  3. If tortoisebot-firstboot.log exists, the non-cloud-init firstboot path ran and the log above shows where it stopped."
Write-Host "  4. If tortoisebot-firstboot.log is missing, the systemd.run hook did not execute."
