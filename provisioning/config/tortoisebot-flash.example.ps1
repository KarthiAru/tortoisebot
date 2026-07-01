# Copy this file to tortoisebot-flash.local.ps1 and fill in your values.
# The .local.ps1 file is ignored by Git so Wi-Fi credentials stay private.
$TortoiseBotFlashDefaults = @{
  # Prefer a drive letter from the SD card, like "D" or "G".
  # Use DiskNumber only for cards with no mounted drive letter.
  DriveLetter  = "D"
  # DiskNumber = 3
  WifiSsid     = "YOUR_WIFI_SSID"
  WifiPassword = "YOUR_WIFI_PASSWORD"
  HostName     = "tortoisebot"
  Username     = "tortoisebot"
  UserPassword = "raspberry"
  RepoUrl      = "https://github.com/KarthiAru/tortoisebot.git"
  RepoBranch   = "mcap-logging"
  # CacheDir = "C:\tortoisebot-cache"
}
