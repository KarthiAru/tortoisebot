# YARI Onboarding Service

Minimal first-boot Wi-Fi onboarding for TortoiseBot/YARI OS devices.

The service starts after boot, checks whether the device already has network
connectivity, and falls back to a local setup access point when no configured
network is available. The setup page is served at `http://192.168.4.1`.

## Current Scope

This is the simplest useful implementation:

- AP fallback using NetworkManager hotspot mode, with a `wpa_supplicant` plus `systemd-networkd` fallback for Ubuntu Server images. The AP is open by default for MVP testing unless `YARI_ONBOARDING_AP_PASSWORD` is set.
- Local web UI for Wi-Fi SSID/password and hostname.
- Persistent Wi-Fi profile written through NetworkManager when available.
- Netplan fallback writer for current Ubuntu Server TortoiseBot images.
- Reboot/apply action from the setup page.

## Dependencies

Preferred runtime dependency:

```bash
sudo apt-get install -y network-manager
```

NetworkManager is preferred for YARI OS because it works across Raspberry Pi,
Jetson Orin, mini PCs, and other Ubuntu edge devices. On Ubuntu Server images
without NetworkManager, the service falls back to `wpa_supplicant` AP mode and
`systemd-networkd` DHCP when those tools are available.

## Installed Files

```text
/usr/local/sbin/yari-onboarding
/etc/systemd/system/yari-onboarding.service
/opt/yari/onboarding/web/index.html
/var/lib/yari/onboarding/state.json
/etc/yari/onboarding.env
```
