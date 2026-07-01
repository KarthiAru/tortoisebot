#Requires -RunAsAdministrator
<#
.SYNOPSIS
  Inspect a provisioned TortoiseBot Raspberry Pi SD card without modifying it.

.DESCRIPTION
  Checks the Windows-visible system-boot partition for rendered cloud-init files,
  verifies that user-data contains the expected username and SSH public key, and
  prints commands for reading cloud-init logs from the Linux root partition.
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

Show-Check "user-data exists" (Test-Path $userDataPath) $userDataPath
Show-Check "meta-data exists" (Test-Path $metaDataPath) $metaDataPath
Show-Check "network-config exists" (Test-Path $networkConfigPath) $networkConfigPath

if (-not (Test-Path $userDataPath)) { throw "No user-data file found on system-boot. The SD card was not seeded." }

$userData = Get-Content -Raw -Path $userDataPath
$metaData = if (Test-Path $metaDataPath) { Get-Content -Raw -Path $metaDataPath } else { "" }
$networkConfig = if (Test-Path $networkConfigPath) { Get-Content -Raw -Path $networkConfigPath } else { "" }
$expectedKey = if (Test-Path $PublicKeyPath) { (Get-Content -Raw -Path $PublicKeyPath).Trim() } else { "" }

Show-Check "cloud-config header" ($userData.StartsWith("#cloud-config"))
Show-Check "no unresolved template tokens" ($userData -notmatch "__[A-Z0-9_]+__")
Show-Check "username rendered" ($userData -match ("name:\s*" + [regex]::Escape($Username))) $Username
Show-Check "bootstrap script present" ($userData -match "tortoisebot-bootstrap-login.sh")
Show-Check "bootstrap log enabled" ($userData -match "tortoisebot-bootstrap-login.log")
Show-Check "password ssh enabled" ($userData -match "PasswordAuthentication yes")
Show-Check "pubkey ssh enabled" ($userData -match "PubkeyAuthentication yes")
Show-Check "network-config has Wi-Fi block" ($networkConfig -match "wifis:")
Show-Check "meta-data has current manual SSH seed" ($metaData -match "manual-ssh-v[0-9]+")

$keyCount = ([regex]::Matches($userData, "ssh-(ed25519|rsa|ecdsa)\s+[A-Za-z0-9+/=]+")).Count
Show-Check "user-data contains at least one SSH public key" ($keyCount -gt 0) "$keyCount key(s)"
if ([string]::IsNullOrWhiteSpace($expectedKey)) {
  Show-Check "local expected public key exists" $false $PublicKeyPath
}
else {
  Show-Check "user-data contains local public key" ($userData.Contains($expectedKey)) $PublicKeyPath
}

$statusLogPath = Join-Path $bootRoot "tortoisebot-cloud-init-status.log"
if (Test-Path $statusLogPath) {
  Show-Check "boot-visible cloud-init status log exists" $true $statusLogPath
  Write-Host ""
  Write-Host "---- tortoisebot-cloud-init-status.log ----" -ForegroundColor Cyan
  Get-Content -Path $statusLogPath | Select-Object -Last 80 | Out-Host
}
else {
  Show-Check "boot-visible cloud-init status log exists" $false "not found yet; boot the Pi once, power it off, then inspect again"
}

Write-Host ""
Write-Host "Next diagnostic loop:" -ForegroundColor Yellow
Write-Host "  1. Boot the Raspberry Pi once with this SD card and wait 2-3 minutes after Wi-Fi appears."
Write-Host "  2. Power it off, put the SD card back in this PC, then rerun this inspector."
Write-Host "  3. If tortoisebot-cloud-init-status.log exists, cloud-init ran and the log above shows where it stopped."
Write-Host "  4. If the status log is missing, the Ubuntu image did not consume the system-boot user-data seed."
Write-Host "Note: WSL could not mount this removable SD reader on your machine, so this script uses the FAT boot partition for logs."
