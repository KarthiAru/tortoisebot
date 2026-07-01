#Requires -RunAsAdministrator
<#
.SYNOPSIS
  Flash and seed a Raspberry Pi SD card for TortoiseBot ROS 2 Humble.

.DESCRIPTION
  Downloads Ubuntu Server 22.04 arm64 Raspberry Pi image, writes it to a selected
  removable disk, then injects cloud-init files so first boot installs ROS 2
  Humble, clones this repo, builds the workspace, and applies Wi-Fi.

  This script is destructive. It overwrites the selected disk.
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [switch]$ListDisks,
  [int]$DiskNumber = -1,
  [string]$DriveLetter,
  [string]$WifiSsid,
  [string]$WifiPassword,
  [string]$HostName = "tortoisebot",
  [string]$Username = "tortoisebot",
  [string]$UserPassword = "raspberry",
  [string]$RepoUrl = "https://github.com/KarthiAru/tortoisebot.git",
  [string]$RepoBranch = "mcap-logging",
  [string]$ImageUrl = "https://cdimage.ubuntu.com/releases/22.04/release/ubuntu-22.04.5-preinstalled-server-arm64+raspi.img.xz",
  [string]$CacheDir,
  [string[]]$BlockedDriveLetters = @("C", "D"),
  [int]$MaxDiskSizeGB = 128,
  [Alias("Config")]
  [string]$LocalConfigPath,
  [switch]$ForceDownload,
  [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$ProvisioningDir = Split-Path -Parent $ScriptDir
if ([string]::IsNullOrWhiteSpace($CacheDir)) {
  $cacheRoot = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { $env:TEMP }
  $CacheDir = Join-Path $cacheRoot "TortoiseBot\cache"
}
if ([string]::IsNullOrWhiteSpace($LocalConfigPath)) {
  $LocalConfigPath = Join-Path $ProvisioningDir "config\tortoisebot-flash.local.ps1"
}

function Write-Info([string]$Message) {
  Write-Host "==> $Message" -ForegroundColor Cyan
}

function Assert-Admin {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = [Security.Principal.WindowsPrincipal]::new($identity)
  if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run PowerShell as Administrator."
  }
}

function Show-CandidateDisks {
  Write-Host "Drive-letter volumes:" -ForegroundColor Cyan
  Get-Volume |
    Where-Object DriveLetter |
    Sort-Object DriveLetter |
    Select-Object DriveLetter, FileSystemLabel, FileSystem, SizeRemaining, Size |
    Format-Table -AutoSize | Out-Host

  Write-Host "Physical disks:" -ForegroundColor Cyan
  Get-Disk |
    Sort-Object Number |
    Select-Object Number, FriendlyName, BusType, Size, PartitionStyle, OperationalStatus, IsOffline, IsReadOnly |
    Format-Table -AutoSize | Out-Host
}

function Normalize-DriveLetter([string]$Letter) {
  if ([string]::IsNullOrWhiteSpace($Letter)) { return $null }
  $normalized = $Letter.Trim().TrimEnd(':', '\').ToUpperInvariant()
  if ($normalized.Length -ne 1 -or $normalized -notmatch '^[A-Z]$') {
    throw "Drive letter must look like D or D:. Got '$Letter'."
  }
  return $normalized
}

function Resolve-DiskNumberFromDriveLetter([string]$Letter) {
  $normalized = Normalize-DriveLetter $Letter
  $blocked = @($BlockedDriveLetters | ForEach-Object { Normalize-DriveLetter $_ })
  if ($blocked -contains $normalized) {
    throw "Drive ${normalized}: is blocked for safety. This flasher will not target blocked drives: $($blocked -join ', ')."
  }
  $partitions = @(Get-Partition -DriveLetter $normalized -ErrorAction Stop)
  if ($partitions.Count -ne 1) {
    throw "Drive ${normalized}: matched $($partitions.Count) partitions; refusing to guess. Use -DiskNumber only after verifying with -ListDisks."
  }
  return [int]$partitions[0].DiskNumber
}


function Get-PartitionProperty([object]$Partition, [string]$Name) {
  $property = $Partition.PSObject.Properties[$Name]
  if ($property) { return $property.Value }
  return $null
}

function Show-TargetDiskDetails([int]$TargetDiskNumber) {
  $disk = Get-Disk -Number $TargetDiskNumber -ErrorAction Stop
  Write-Host "Selected target disk:" -ForegroundColor Yellow
  $disk | Select-Object Number, FriendlyName, SerialNumber, BusType, @{Name="SizeGB"; Expression={[math]::Round($_.Size / 1GB, 2)}}, Size, PartitionStyle, OperationalStatus, IsOffline, IsReadOnly | Format-List | Out-Host

  $partitions = @(Get-Partition -DiskNumber $TargetDiskNumber -ErrorAction SilentlyContinue)
  if ($partitions.Count -gt 0) {
    Write-Host "Partitions on selected disk:" -ForegroundColor Yellow
    $partitions |
      Sort-Object PartitionNumber |
      Select-Object DiskNumber, PartitionNumber, DriveLetter, Type, Size, IsActive, IsBoot, IsSystem |
      Format-Table -AutoSize | Out-Host

    $volumes = @($partitions | Get-Volume -ErrorAction SilentlyContinue)
    if ($volumes.Count -gt 0) {
      Write-Host "Volumes on selected disk:" -ForegroundColor Yellow
      $volumes |
        Select-Object DriveLetter, FileSystemLabel, FileSystem, SizeRemaining, Size |
        Format-Table -AutoSize | Out-Host
    }
  }
}

function Assert-TargetDiskSafe([int]$TargetDiskNumber) {
  $disk = Get-Disk -Number $TargetDiskNumber -ErrorAction Stop
  $partitions = @(Get-Partition -DiskNumber $TargetDiskNumber -ErrorAction SilentlyContinue)
  $blocked = @($BlockedDriveLetters | ForEach-Object { Normalize-DriveLetter $_ })
  $allowedBus = @("USB", "SD", "MMC")

  Show-TargetDiskDetails -TargetDiskNumber $TargetDiskNumber

  if (-not $Force -and $allowedBus -notcontains $disk.BusType.ToString()) {
    throw "Disk $TargetDiskNumber bus type is $($disk.BusType), not USB/SD/MMC. Pass -Force only if you are absolutely sure."
  }

  $blockedPartitions = @($partitions | Where-Object { $_.DriveLetter -and $blocked -contains (Normalize-DriveLetter ([string]$_.DriveLetter)) })
  if ($blockedPartitions.Count -gt 0) {
    throw "Disk $TargetDiskNumber contains blocked drive letter(s): $((@($blockedPartitions | ForEach-Object { $_.DriveLetter }) | Sort-Object -Unique) -join ', '). Refusing to flash."
  }

  $systemPartitions = @($partitions | Where-Object {
    $_.DriveLetter -eq "C" -or
    (Get-PartitionProperty $_ "IsBoot") -eq $true -or
    (Get-PartitionProperty $_ "IsSystem") -eq $true
  })
  if ($systemPartitions.Count -gt 0) {
    throw "Disk $TargetDiskNumber appears to contain a Windows boot/system partition. Refusing to flash."
  }

  $diskSizeGB = [math]::Round($disk.Size / 1GB, 2)
  if ($disk.Size -ge ($MaxDiskSizeGB * 1GB)) {
    throw "Disk $TargetDiskNumber is $diskSizeGB GB. Refusing to flash disks that are $MaxDiskSizeGB GB or larger."
  }
}
function Select-TargetDiskNumber {
  if (-not [string]::IsNullOrWhiteSpace($DriveLetter)) {
    $resolved = Resolve-DiskNumberFromDriveLetter $DriveLetter
    Write-Info "Drive $((Normalize-DriveLetter $DriveLetter)): maps to physical disk $resolved"
    return $resolved
  }

  if ($DiskNumber -ge 0) {
    return $DiskNumber
  }

  Show-CandidateDisks
  Write-Host ""
  $selection = Read-Host "Enter the SD card drive letter, like D, or physical disk number"
  if ($selection -match '^\s*[A-Za-z]:?\s*$') {
    return Resolve-DiskNumberFromDriveLetter $selection
  }
  if ($selection -match '^\s*\d+\s*$') {
    return [int]$selection
  }
  throw "Could not understand '$selection'. Enter a drive letter like D or a disk number like 3."
}

function Load-LocalDefaults {
  if (-not (Test-Path $LocalConfigPath)) { return }
  . $LocalConfigPath
  if (-not (Get-Variable -Name TortoiseBotFlashDefaults -Scope Local -ErrorAction SilentlyContinue)) { return }

  foreach ($key in $TortoiseBotFlashDefaults.Keys) {
    if (-not $PSBoundParameters.ContainsKey($key)) {
      Set-Variable -Name $key -Value $TortoiseBotFlashDefaults[$key] -Scope Script
    }
  }
}

function Get-FileNameFromUrl([string]$Url) {
  return [IO.Path]::GetFileName(([Uri]$Url).AbsolutePath)
}

function Download-Image([string]$Url, [string]$Destination) {
  if ($ForceDownload -and (Test-Path $Destination)) {
    Write-Info "Removing cached download: $Destination"
    Remove-Item -Force -Path $Destination
  }
  if (Test-Path $Destination) {
    Write-Info "Using existing download: $Destination"
    return
  }
  Write-Info "Downloading $Url"
  New-Item -ItemType Directory -Force -Path (Split-Path $Destination) | Out-Null
  curl.exe -L --fail --retry 3 -o $Destination $Url
}

function ConvertTo-WslPath([string]$Path) {
  $full = [IO.Path]::GetFullPath($Path)
  if ($full -match "^([A-Za-z]):\\(.*)$") {
    $drive = $Matches[1].ToLowerInvariant()
    $rest = $Matches[2].Replace("\", "/")
    return "/mnt/$drive/$rest"
  }
  throw "WSL xz fallback requires CacheDir on a local Windows drive. Got $Path"
}

function Expand-XzImage([string]$XzPath, [string]$ImgPath) {
  if ($ForceDownload -and (Test-Path $ImgPath)) {
    Write-Info "Removing cached expanded image: $ImgPath"
    Remove-Item -Force -Path $ImgPath
  }
  if (Test-Path $ImgPath) {
    Write-Info "Using existing expanded image: $ImgPath"
    return
  }

  Write-Info "Expanding image to $ImgPath"
  $sevenZip = Get-Command 7z.exe -ErrorAction SilentlyContinue
  if ($sevenZip) {
    cmd.exe /d /c "`"$($sevenZip.Source)`" x -so `"$XzPath`" > `"$ImgPath`""
    if ($LASTEXITCODE -ne 0) { throw "7z failed to expand $XzPath" }
    return
  }

  $xz = Get-Command xz.exe -ErrorAction SilentlyContinue
  if ($xz) {
    cmd.exe /d /c "`"$($xz.Source)`" -dc `"$XzPath`" > `"$ImgPath`""
    if ($LASTEXITCODE -ne 0) { throw "xz failed to expand $XzPath" }
    return
  }

  $wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
  if ($wsl) {
    $wslXz = ConvertTo-WslPath $XzPath
    $wslImg = ConvertTo-WslPath $ImgPath
    & $wsl.Source sh -lc "xz -dc `"$wslXz`" > `"$wslImg`""
    if ($LASTEXITCODE -ne 0) { throw "WSL xz failed to expand $XzPath" }
    return
  }

  throw "Need 7z.exe, xz.exe, or WSL with xz to expand raw .img.xz images."
}


function Initialize-NativeVolumeApi {
  if ("NativeVolume" -as [type]) { return }
  Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

public static class NativeVolume {
  [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
  public static extern SafeFileHandle CreateFile(
    string lpFileName,
    uint dwDesiredAccess,
    uint dwShareMode,
    IntPtr lpSecurityAttributes,
    uint dwCreationDisposition,
    uint dwFlagsAndAttributes,
    IntPtr hTemplateFile);

  [DllImport("kernel32.dll", SetLastError = true)]
  public static extern bool DeviceIoControl(
    SafeFileHandle hDevice,
    uint dwIoControlCode,
    IntPtr lpInBuffer,
    uint nInBufferSize,
    IntPtr lpOutBuffer,
    uint nOutBufferSize,
    out uint lpBytesReturned,
    IntPtr lpOverlapped);
}
"@
}

function Invoke-VolumeIoControl([Microsoft.Win32.SafeHandles.SafeFileHandle]$Handle, [uint32]$ControlCode, [string]$Description) {
  [uint32]$bytesReturned = 0
  $ok = [NativeVolume]::DeviceIoControl($Handle, $ControlCode, [IntPtr]::Zero, 0, [IntPtr]::Zero, 0, [ref]$bytesReturned, [IntPtr]::Zero)
  if (-not $ok) {
    $errorCode = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
    throw "$Description failed with Win32 error $errorCode."
  }
}

function Lock-VolumeByDriveLetter([string]$DriveLetter) {
  Initialize-NativeVolumeApi
  $letter = Normalize-DriveLetter $DriveLetter
  $path = "\\.\${letter}:"
  $genericReadWrite = [uint32]0xC0000000
  $shareReadWrite = [uint32]0x00000003
  $openExisting = [uint32]3
  $fsctlLockVolume = [uint32]0x00090018
  $fsctlDismountVolume = [uint32]0x00090020

  Write-Info "Locking volume ${letter}:"
  $handle = [NativeVolume]::CreateFile($path, $genericReadWrite, $shareReadWrite, [IntPtr]::Zero, $openExisting, 0, [IntPtr]::Zero)
  if ($handle.IsInvalid) {
    $errorCode = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
    throw "Could not open ${letter}: for locking. Win32 error $errorCode. Close File Explorer or any program using the SD card."
  }

  try {
    Invoke-VolumeIoControl -Handle $handle -ControlCode $fsctlLockVolume -Description "Lock ${letter}:"
    Invoke-VolumeIoControl -Handle $handle -ControlCode $fsctlDismountVolume -Description "Dismount ${letter}:"
    return $handle
  }
  catch {
    $handle.Dispose()
    throw
  }
}
function Dismount-TargetDiskVolumes([int]$TargetDiskNumber) {
  $partitions = @(Get-Partition -DiskNumber $TargetDiskNumber -ErrorAction SilentlyContinue)
  if ($partitions.Count -eq 0) { return @() }

  $locks = @()
  Write-Info "Locking/removing drive letters on disk $TargetDiskNumber"
  foreach ($partition in $partitions) {
    $volumes = @($partition | Get-Volume -ErrorAction SilentlyContinue)
    foreach ($volume in $volumes) {
      if ($volume.DriveLetter) {
        $locks += Lock-VolumeByDriveLetter ([string]$volume.DriveLetter)
      }
    }

    $accessPaths = @($partition.AccessPaths | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    foreach ($accessPath in $accessPaths) {
      Write-Info "Removing access path $accessPath from disk $TargetDiskNumber partition $($partition.PartitionNumber)"
      Remove-PartitionAccessPath -DiskNumber $TargetDiskNumber -PartitionNumber $partition.PartitionNumber -AccessPath $accessPath -ErrorAction SilentlyContinue
    }

    foreach ($volume in $volumes) {
      if ($volume.DriveLetter) {
        cmd.exe /d /c "mountvol $($volume.DriveLetter): /p" | Out-Null
      }
    }
  }

  Update-HostStorageCache
  Start-Sleep -Seconds 2
  return $locks
}
function Write-RawImage([string]$ImgPath, [int]$TargetDiskNumber) {
  $disk = Get-Disk -Number $TargetDiskNumber -ErrorAction Stop

  Write-Host ""
  Write-Host "About to overwrite the selected physical disk with image:" -ForegroundColor Yellow
  Write-Host "  Disk:  $TargetDiskNumber"
  Write-Host "  Size:  $([math]::Round($disk.Size / 1GB, 2)) GB"
  Write-Host "  Image: $ImgPath"
  $confirmation = Read-Host "Proceed with flashing disk ${TargetDiskNumber}? (Y/N)"
  if ($confirmation.Trim().ToUpperInvariant() -ne "Y") {
    throw "Confirmation declined; not writing the SD card."
  }

  if ($PSCmdlet.ShouldProcess("PhysicalDrive$TargetDiskNumber", "write image $ImgPath")) {
    Write-Info "Preparing disk for raw write"
    Set-Disk -Number $TargetDiskNumber -IsReadOnly $false -ErrorAction SilentlyContinue
    $diskWasSetOffline = $false
    $volumeLocks = @()
    try {
      Set-Disk -Number $TargetDiskNumber -IsOffline $true -ErrorAction Stop
      $diskWasSetOffline = $true
    }
    catch {
      if ($_.Exception.Message -notmatch "Not Supported|Removable media cannot be set to offline") {
        throw
      }
      Write-Warning "Windows cannot set removable media offline; locking/removing volumes before raw write."
    }

    if (-not $diskWasSetOffline) {
      $volumeLocks = @(Dismount-TargetDiskVolumes -TargetDiskNumber $TargetDiskNumber)
    }

    $target = "\\.\PhysicalDrive$TargetDiskNumber"
    $buffer = New-Object byte[] (8MB)
    $inputStream = $null
    $outputStream = $null
    try {
      $inputStream = [IO.File]::Open($ImgPath, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
      try {
        $outputStream = [IO.File]::Open($target, [IO.FileMode]::Open, [IO.FileAccess]::Write, [IO.FileShare]::ReadWrite)
      }
      catch [UnauthorizedAccessException] {
        throw "Access denied opening $target. Close File Explorer or any program using the SD card, unplug/reinsert the card, then rerun the script and choose the current drive letter."
      }
      $total = $inputStream.Length
      $written = 0L
      while (($read = $inputStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
        $outputStream.Write($buffer, 0, $read)
        $written += $read
        Write-Progress -Activity "Writing SD card image" -Status "$([math]::Round(($written / 1MB), 1)) MB / $([math]::Round(($total / 1MB), 1)) MB" -PercentComplete (($written / $total) * 100)
      }
      $outputStream.Flush()
    }
    finally {
      if ($outputStream) { $outputStream.Dispose() }
      if ($inputStream) { $inputStream.Dispose() }
      Write-Progress -Activity "Writing SD card image" -Completed
      foreach ($lock in $volumeLocks) {
        if ($lock) { $lock.Dispose() }
      }
      if ($diskWasSetOffline) {
        Set-Disk -Number $TargetDiskNumber -IsOffline $false -ErrorAction SilentlyContinue
      }
      Update-HostStorageCache
    }
  }
}

function Wait-SystemBootVolume([int]$TargetDiskNumber) {
  Write-Info "Waiting for Windows to mount the system-boot partition"
  for ($i = 0; $i -lt 60; $i++) {
    Update-HostStorageCache
    $volumes = Get-Partition -DiskNumber $TargetDiskNumber -ErrorAction SilentlyContinue | Get-Volume -ErrorAction SilentlyContinue
    $boot = $volumes | Where-Object { $_.FileSystemLabel -eq "system-boot" -or $_.FileSystemLabel -eq "system-boot-0" } | Select-Object -First 1
    if ($boot) {
      if (-not $boot.DriveLetter) {
        $used = (Get-Volume | Where-Object DriveLetter | Select-Object -ExpandProperty DriveLetter)
        $blocked = @($BlockedDriveLetters | ForEach-Object { Normalize-DriveLetter $_ })
        $letter = [char[]]([char]'D'..[char]'Z') | Where-Object { $used -notcontains $_ -and $blocked -notcontains ([string]$_) } | Select-Object -First 1
        if (-not $letter) { throw "No free drive letter available for system-boot." }
        $partition = Get-Partition -DiskNumber $TargetDiskNumber | Where-Object { $_.Guid -eq $boot.UniqueId -or $_.Type -eq "System" } | Select-Object -First 1
        if ($partition) { Set-Partition -DiskNumber $TargetDiskNumber -PartitionNumber $partition.PartitionNumber -NewDriveLetter $letter }
        Start-Sleep -Seconds 2
        $boot = Get-Volume -DriveLetter $letter
      }
      return "$($boot.DriveLetter):\"
    }
    Start-Sleep -Seconds 2
  }
  throw "Could not find the system-boot partition. Remove/reinsert the SD card and copy cloud-init files manually if needed."
}

function Escape-YamlDoubleQuoted([string]$Value) {
  return $Value.Replace("\", "\\").Replace('"', '\"')
}

function Render-Template([string]$TemplatePath, [string]$DestinationPath, [hashtable]$Values) {
  $content = Get-Content -Raw $TemplatePath
  foreach ($key in $Values.Keys) {
    $content = $content.Replace("__$key__", [string]$Values[$key])
  }
  Set-Content -Path $DestinationPath -Value $content -Encoding UTF8 -NoNewline
}

Assert-Admin
Load-LocalDefaults

if ($ListDisks) {
  Show-CandidateDisks
  return
}

$TargetDiskNumber = [int](Select-TargetDiskNumber)
Assert-TargetDiskSafe -TargetDiskNumber $TargetDiskNumber
if ([string]::IsNullOrWhiteSpace($WifiSsid) -or [string]::IsNullOrWhiteSpace($WifiPassword)) {
  throw "Pass -WifiSsid and -WifiPassword, or create provisioning/config/tortoisebot-flash.local.ps1."
}

New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null
$imageName = Get-FileNameFromUrl $ImageUrl
$xzPath = Join-Path $CacheDir $imageName
$imgPath = Join-Path $CacheDir ($imageName -replace '\.xz$', '')

Download-Image -Url $ImageUrl -Destination $xzPath
Expand-XzImage -XzPath $xzPath -ImgPath $imgPath
Write-RawImage -ImgPath $imgPath -TargetDiskNumber $TargetDiskNumber

$bootRoot = Wait-SystemBootVolume -TargetDiskNumber $TargetDiskNumber
Write-Info "Writing cloud-init files to $bootRoot"

$templateDir = Join-Path $ProvisioningDir "cloud-init"
$values = @{
  HOSTNAME      = $HostName
  USERNAME      = $Username
  PASSWORD      = $UserPassword
  WIFI_SSID     = Escape-YamlDoubleQuoted $WifiSsid
  WIFI_PASSWORD = Escape-YamlDoubleQuoted $WifiPassword
  REPO_URL      = $RepoUrl
  REPO_BRANCH   = $RepoBranch
}

Render-Template (Join-Path $templateDir "user-data.template") (Join-Path $bootRoot "user-data") $values
Render-Template (Join-Path $templateDir "meta-data.template") (Join-Path $bootRoot "meta-data") $values
Render-Template (Join-Path $templateDir "network-config.template") (Join-Path $bootRoot "network-config") $values

Write-Info "Done. Eject the SD card, boot the Raspberry Pi, and watch first boot with:"
Write-Host "  ssh $Username@$HostName.local"
Write-Host "  tail -f /var/log/tortoisebot-firstboot.log"
