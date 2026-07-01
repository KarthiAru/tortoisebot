# Raspberry Pi SD Card Provisioning

Use Ubuntu Server 22.04 LTS 64-bit for Raspberry Pi as the base image. ROS 2
Humble binary packages target Ubuntu Jammy, so this is the most reliable route
for TortoiseBot hardware.

The repeatable flow is:

1. Flash the Ubuntu Raspberry Pi image to the microSD card.
2. Inject cloud-init Wi-Fi, user, repo, and first-boot installer config.
3. Boot the Pi and let cloud-init install ROS 2 Humble, clone this repo, run
   `rosdep`, and build the workspace.

## Windows Automated Flashing

Run PowerShell as Administrator from this repo checkout.

List visible drive letters and physical disks first:

```powershell
.\provisioning\scripts\flash_tortoisebot_sd.ps1 -ListDisks
```

Create your private defaults file:

```powershell
Copy-Item .\provisioning\config\tortoisebot-flash.example.ps1 `
  .\provisioning\config\tortoisebot-flash.local.ps1
notepad .\provisioning\config\tortoisebot-flash.local.ps1
```

Fill in `DriveLetter`, `WifiSsid`, `WifiPassword`, `RepoUrl`, and `RepoBranch`. Use `DiskNumber` only when the card has no mounted drive letter.
The `.local.ps1` file is ignored by Git so Wi-Fi credentials stay private.

Flash and seed the card:

```powershell
.\provisioning\scripts\flash_tortoisebot_sd.ps1
```

Or pass values directly:

```powershell
.\provisioning\scripts\flash_tortoisebot_sd.ps1 `
  -DriveLetter D `
  -WifiSsid "YOUR_WIFI_SSID" `
  -WifiPassword "YOUR_WIFI_PASSWORD" `
  -RepoUrl "https://github.com/KarthiAru/tortoisebot.git" `
  -RepoBranch "mcap-logging"
```

The script downloads the official Ubuntu 22.04.5 Raspberry Pi arm64 image,
expands it, writes it to the selected physical disk, then writes these files to
`system-boot`:

The Ubuntu `.img.xz` and expanded `.img` are cached in `%LOCALAPPDATA%\TortoiseBot\cache` by default, so later runs reuse the same OS image instead of downloading and expanding it again. Pass `-CacheDir` to use another local Windows folder. Use `-ForceDownload` when you want to refresh the cached files:

```powershell
.\provisioning\scripts\flash_tortoisebot_sd.ps1 -ForceDownload
```


- `user-data`
- `meta-data`
- `network-config`

The write step is destructive and still requires answering `Y` before
anything is written. Drive letters are easier to recognize, but raw image writing
happens to the whole physical disk underneath that drive letter.

By default, `BlockedDriveLetters = @("C", "D")`, so the script refuses to target any disk containing either of those drive letters and will not assign them while mounting `system-boot`. It also refuses disks that are 128 GB or larger by default.

## First Boot

Insert the card into the Raspberry Pi and boot it. Provisioning can take a while
because ROS 2, Nav2, Cartographer, rosbag2 MCAP support, and the workspace build
all run on first boot.

SSH in after the Pi joins Wi-Fi:

```bash
ssh tortoisebot@tortoisebot.local
```

Default generated login is:

| Field | Default |
|---|---|
| Hostname | `tortoisebot` |
| Username | `tortoisebot` |
| Password | `raspberry` |

Watch first-boot progress:

```bash
sudo tail -f /var/log/tortoisebot-firstboot.log
```

The first-boot script is idempotent and writes this sentinel when complete:

```bash
/var/lib/tortoisebot/.firstboot-complete
```

## Manual Flashing Fallback

If you prefer Raspberry Pi Imager:

1. Open Raspberry Pi Imager.
2. Select Ubuntu Server 22.04 LTS 64-bit.
3. In OS customization, set hostname, username, SSH, locale, and Wi-Fi.
4. Flash the SD card and boot the Raspberry Pi.
5. SSH in, clone this repo, then run:

```bash
cd ~/tb_ws/src/tortoisebot
sudo bash provisioning/scripts/install_tortoisebot_humble.sh
cd ~/tb_ws
rosdep install --from-paths src --ignore-src -r -y --rosdistro humble
colcon build
```

## Bake It Into an Image

Yes, this repo can be packaged with ROS 2 Humble into a prebuilt SD-card image.
The recommended approach is to customize an Ubuntu Server 22.04 Raspberry Pi
image or automate first boot with cloud-init. Baking the install into stock
Raspberry Pi OS is not recommended for Humble because Raspberry Pi OS is
Debian-based while Humble binary packages are built for Ubuntu Jammy.

This provisioning layout mirrors the useful ARK-OS pattern: keep the live/device
installer idempotent, keep repeatable inputs in a config file, and run runtime
steps on first boot instead of expecting them to work inside an image-build
chroot.
