# Raspberry Pi SD Card Provisioning

Use Ubuntu Server 22.04 LTS 64-bit for Raspberry Pi as the base image. ROS 2 Humble binary packages target Ubuntu Jammy, so this is the most reliable route for TortoiseBot hardware.

The recommended workflow now runs on an Ubuntu/Linux machine. It edits the Raspberry Pi image root filesystem directly, so user login, SSH, Wi-Fi, and the manual installer are present before the card ever boots. The old Windows workflow is deprecated because Windows cannot reliably edit the Linux ext4 root partition on the SD card.

For the longer-term YARI OS user experience, the image should not require Wi-Fi credentials at flash time. It should boot into a setup access point, expose a local web setup page, store credentials on the device, and reconnect on reboot. See [YARI OS Device Onboarding](yari-os-onboarding.md).

## Ubuntu Image Builder

Install host tools on the Ubuntu machine:

```bash
sudo apt-get update
sudo apt-get install -y curl xz-utils util-linux openssl coreutils
# Also install Node.js >= 18 and npm to bake the Svelte YARI OS portal into images.
```

Create a private config file:

```bash
cp provisioning/config/tortoisebot-image.example.env provisioning/config/tortoisebot-image.local.env
nano provisioning/config/tortoisebot-image.local.env
```

Fill in hostname, username/password, repo URL, and branch. Wi-Fi is optional: leave `WIFI_SSID` and `WIFI_PASSWORD` blank to use the first-boot YARI setup access point at `http://192.168.4.1`. Set `YARI_PORTAL_BUILD=always` for production-style YARI OS images so missing/outdated Node tooling fails early instead of silently baking the legacy portal. The `.local.env` file is ignored by Git so credentials stay private.

Build a configured image without flashing:

```bash
sudo bash provisioning/scripts/build_tortoisebot_image.sh
```

The script caches the Ubuntu `.img.xz` and expanded `.img` under `~/.cache/tortoisebot` by default. It writes finished images to `provisioning/output/`. When `YARI_ONBOARDING_ENABLED=1`, the builder runs the Svelte portal build before mounting the image if Node.js >= 18 and npm are available, then copies `provisioning/yari-onboarding/portal/dist` into `/opt/yari/onboarding/web`.

Force a fresh download and expansion:

```bash
sudo bash provisioning/scripts/build_tortoisebot_image.sh --force-download
```

Flash the finished image directly to a microSD card:

```bash
lsblk -o NAME,SIZE,MODEL,TRAN,MOUNTPOINTS
sudo bash provisioning/scripts/build_tortoisebot_image.sh --device /dev/sdX
```

Replace `/dev/sdX` with the whole removable device, not a partition like `/dev/sdX1`. The script refuses devices at or above `MAX_DEVICE_SIZE_GB` from the config, shows `lsblk`, and requires typing `YES` before running `dd`.

## What Gets Baked Into The Image

The Ubuntu builder mounts the image partitions and writes directly into the root filesystem:

- `/etc/hostname` and `/etc/hosts`
- `/etc/passwd`, `/etc/shadow`, `/etc/group`, and `/etc/gshadow` for the TortoiseBot use
- `/home/<user>/.ssh/authorized_keys` with correct Linux ownership and permissions
- `/etc/sudoers.d/90-tortoisebot`
- `/etc/ssh/sshd_config` and `/etc/ssh/sshd_config.d/10-tortoisebot-auth.conf`
- `/etc/netplan/01-tortoisebot-wifi.yaml`
- `/usr/local/sbin/tortoisebot-install.sh`
- `/etc/motd`

It also writes minimal `user-data`, `meta-data`, and `network-config` to the boot partition for compatibility with Ubuntu Raspberry Pi images, but login does not depend on cloud-init creating the user.

Wi-Fi can still be baked into the image as a development convenience. The first boot uses the Ubuntu Server `systemd-networkd` path so the Pi can get online before extra packages are installed. The manual TortoiseBot installer then installs NetworkManager, enables it, and rewrites the persistent netplan file to use `renderer: NetworkManager` for future boots.

If `WIFI_SSID` and `WIFI_PASSWORD` are blank, the image installs the YARI onboarding service. On boot, if no network connection is available, the device attempts to start setup AP `YARI-<hostname>` and serves a local setup page at `http://192.168.4.1`. The onboarding service prefers NetworkManager hotspot mode when NetworkManager is available and falls back to `wpa_supplicant` plus `systemd-networkd` DHCP on minimal Ubuntu Server images.

## First Boot and Manual Install

### First-Boot Setup AP

If no Wi-Fi credentials were baked into the image, or if the configured network is unavailable, the onboarding service attempts to start a setup access point:

| Setting | Value |
|---|---|
| SSID | `YARI-<hostname>` |
| URL | `http://192.168.4.1` |

Connect your laptop/phone to that access point, open the URL, enter Wi-Fi credentials, and save. The device writes persistent network configuration and reboots.

The onboarding service prefers NetworkManager (`nmcli`) for AP mode and falls back to `wpa_supplicant` AP mode with `systemd-networkd` DHCP. If neither backend is available, the service records a clear error in `/var/lib/yari/onboarding/state.json`.

Insert the card into the Raspberry Pi and boot it. The base system should join Wi-Fi and allow SSH with the configured user.

```bash
ssh tortoisebot@tortoisebot.local
```

If `.local` name resolution is unavailable on Windows, use the IP shown by your router:

```powershell
ssh tortoisebot@192.168.0.xxx
```

Default generated login is:

| Field | Default |
|---|---|
| Hostname | `tortoisebot` |
| Username | `tortoisebot` |
| Password | `raspberry` |

Start the TortoiseBot install manually after SSH login:

```bash
sudo /usr/local/sbin/tortoisebot-install.sh
```

The installer clones `REPO_URL` at `REPO_BRANCH`, installs ROS 2 Humble packages, installs hardware dependencies, runs `rosdep`, and builds the workspace. It logs to the console and to disk:

```bash
tail -f /var/log/tortoisebot-install.log
```

The install is idempotent and writes this sentinel when complete:

```bash
/var/lib/tortoisebot/.install-complete
```

Remove that file only when you intentionally want to rerun the full install.

## Deprecated Windows Flow

The PowerShell scripts are kept for reference only:

- `provisioning/scripts/flash_tortoisebot_sd.ps1`
- `provisioning/scripts/inspect_tortoisebot_sd.ps1`
- `provisioning/config/tortoisebot-flash.example.ps1`

Do not use them for the normal provisioning path. They can write the FAT boot partition, but they cannot reliably configure Linux-side SSH users, ownership, permissions, and service files on the ext4 root partition.

## Manual Flashing Fallback

If you prefer Raspberry Pi Imager, flash Ubuntu Server 22.04 LTS 64-bit, enable SSH and Wi-Fi in OS customization, boot the Pi, SSH in, clone this repo, then run:

```bash
mkdir -p ~/tb_ws/src
cd ~/tb_ws/src
git clone --branch mcap-logging https://github.com/KarthiAru/tortoisebot.git
cd ~/tb_ws/src/tortoisebot
sudo bash provisioning/scripts/install_tortoisebot_humble.sh
cd ~/tb_ws
rosdep install --from-paths src --ignore-src -r -y --rosdistro humble
colcon build
```


