# YARI OS Device Onboarding

This is the target onboarding experience for TortoiseBot and future YARI OS edge devices such as Raspberry Pi and Jetson Orin.

## User Experience

1. Flash the SD card or device image.
2. Power on the robot.
3. If the device has no working Wi-Fi profile, it starts a setup access point: `YARI-<device-id>`.
4. The operator connects a phone or laptop to that access point.
5. The operator opens `http://192.168.4.1`.
6. A local setup page lets the operator configure Wi-Fi credentials, hostname, SSH access, Atlas/Foxglove tokens, and optional static IP settings.
7. The device validates and stores the configuration.
8. The operator clicks reboot.
9. On the next boot, the device connects to the configured Wi-Fi network.
10. If Wi-Fi fails for a configurable timeout, the setup access point comes back.

This avoids baking private Wi-Fi credentials into images and makes one image usable across many robots and customer sites.

## Architecture

The onboarding stack should be a small system service independent of ROS 2. ROS should be allowed to fail, rebuild, or restart without breaking Wi-Fi.

```text
boot
  |
  v
network onboarding service
  |
  +-- known network works ------> normal client Wi-Fi mode
  |
  +-- no network / timeout -----> setup AP mode
                                  |
                                  +-- DHCP + DNS captive portal
                                  +-- local web setup UI
                                  +-- writes persistent network profile
                                  +-- reboot or network restart
```

Recommended Linux components:

- `NetworkManager` for cross-device Wi-Fi management.
- `hostapd` only if NetworkManager AP mode is not sufficient on a target image.
- `dnsmasq` or NetworkManager shared mode for DHCP on the setup AP.
- A small local HTTP service bound to the setup interface.
- `systemd` units to manage onboarding before ROS services start.

For Ubuntu Server Raspberry Pi images, this means moving away from cloud-init owning Wi-Fi after first boot. Cloud-init may still seed the first user, but runtime Wi-Fi should be managed by the YARI onboarding service.

## Persistent Files

Device identity and state:

```text
/etc/yari/device.json
/var/lib/yari/onboarding/state.json
```

Wi-Fi credentials:

```text
/etc/NetworkManager/system-connections/yari-wifi.nmconnection
```

or, for the current Ubuntu/netplan interim path:

```text
/etc/netplan/01-yari-wifi.yaml
```

Cloud-init network ownership should be disabled after image provisioning:

```text
/etc/cloud/cloud.cfg.d/99-yari-disable-network-config.cfg
```

with:

```yaml
network: {config: disabled}
```

If the device no longer needs cloud-init at all after first boot:

```text
/etc/cloud/cloud-init.disabled
```

## Setup AP Defaults

Default setup network:

| Setting | Value |
|---|---|
| SSID | `YARI-<device-id>` |
| Gateway | `192.168.4.1` |
| DHCP range | `192.168.4.20` - `192.168.4.200` |
| Setup URL | `http://192.168.4.1` |

For the MVP, the setup AP may be open when `YARI_ONBOARDING_AP_PASSWORD` is blank. For production images, set a unique AP password printed on a device label, derived from a device secret, or shown once on a local console. Do not use one universal password for all devices.

## Security Rules

- The setup web service binds only to the setup AP interface.
- The setup API requires the AP password or a short-lived physical-access token.
- Wi-Fi passwords and device tokens are written with `0600` permissions.
- The setup AP is disabled once the device successfully joins a configured network, unless the operator explicitly enables maintenance mode.
- A hardware reset path should clear network credentials and re-enable setup AP.

## TortoiseBot Interim Plan

The current TortoiseBot image builder still writes Wi-Fi at image-build time. That is useful for development, but it should be treated as an interim path.

Short-term:

1. Keep `/etc/netplan/01-tortoisebot-wifi.yaml` as the single persistent Wi-Fi profile.
2. Disable cloud-init network rewrites.
3. Do not let ROS workspace rebuilds modify `/etc/netplan`.
4. Document recovery commands for monitor/keyboard access.

MVP implemented in this repo:

1. `provisioning/yari-onboarding/` contains `yari-onboarding.service`, a setup AP/web server script, and the local setup web UI.
2. `build_tortoisebot_image.sh` installs those files into the image and enables the service.
3. `WIFI_SSID` and `WIFI_PASSWORD` are optional in the image config.
4. If no Wi-Fi credentials are provided, first boot attempts setup AP mode.
5. If credentials are provided but fail after a timeout, the service attempts setup AP fallback.

Next hardening step:

1. Test AP mode on Raspberry Pi and Jetson hardware.
2. Add a Wi-Fi scan endpoint and SSID picker to the UI.
3. Add per-device AP passwords or a physical-access setup token.
4. Add factory-reset/maintenance-mode controls.

## Recovery Commands

When connected by monitor/keyboard, verify who owns networking:

```bash
ls -l /etc/netplan
cat /etc/cloud/cloud.cfg.d/99-yari-disable-network-config.cfg 2>/dev/null || true
networkctl status wlan0 || true
nmcli device status || true
```

For the current netplan-based TortoiseBot image, keep exactly one Wi-Fi file:

```bash
sudo rm -f /etc/netplan/50-cloud-init.yaml
sudo rm -f /etc/netplan/99-tortoisebot-wifi.yaml
sudo nano /etc/netplan/01-tortoisebot-wifi.yaml
sudo chmod 600 /etc/netplan/01-tortoisebot-wifi.yaml
sudo netplan generate
sudo netplan apply
```

Then reboot and confirm `wlan0` has an address:

```bash
ip addr show wlan0
ping -c 3 8.8.8.8
```
