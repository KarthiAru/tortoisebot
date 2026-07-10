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


## Phase 1/2 Implementation Status

This repo now contains the first implementation slice for Phase 1 and Phase 2, but the manager services are intentionally still scaffolding until hardware-specific MAVLink, video, ROS launch, and upload workers are implemented.

Implemented Phase 1 pieces:

- Persistent local portal served by `yari-onboarding.service` after normal Wi-Fi join and during setup AP mode.
- NetworkManager-first Wi-Fi save path writing `/etc/NetworkManager/system-connections/yari-wifi.nmconnection`.
- Reboot-after-save behavior for single-radio devices.
- Setup fields for Wi-Fi, hostname, SSH key/password, Atlas token, and Foxglove token.
- Device status with OS, kernel, architecture, CPU, RAM, disk, temperature, IPs, uptime, and onboarding state.
- Network status with active connections, interfaces, AP/client state, DNS, static-IP placeholder, Ethernet, and LTE placeholder.
- Allowlisted service start/stop/restart/enable/disable/logs for YARI-managed services only.
- Logs page with onboarding, system journal, ROS log, MAVLink log views, and downloadable support bundle endpoint.
- Maintenance controls for reboot, shutdown, factory-reset network, and regenerate device ID.

Implemented Phase 2 foundation:

- Systemd unit templates for `yari-mavlink-router`, `yari-autopilot-manager`, `yari-log-manager`, `yari-video`, `yari-ros`, and `yari-agent`.
- Autopilot portal page with serial-device discovery, MAVLink endpoint config, PX4/ArduPilot status placeholders, and firmware-upload placeholder.
- ROS 2 portal page with ROS presence, node list, topic list, launch profile placeholders, and bag/MCAP recording placeholder endpoints.
- Video portal page with camera/media device discovery and stream profile placeholders.
- Data portal page with MCAP log discovery, flight-log discovery, upload queue placeholder, and cleanup placeholder.

Remaining Phase 2 implementation work:

- Replace placeholder systemd services with real service binaries/scripts.
- Implement MAVLink heartbeat parsing, PX4/ArduPilot detection, mode, arming state, GPS, battery, EKF, failsafe, and firmware metadata.
- Implement MAVLink router config generation and live reload.
- Implement ROS launch profile management and MCAP start/stop controls.
- Implement camera preview/stream controls for RTSP, WebRTC, and Foxglove-friendly compressed topics.
- Implement Atlas upload queue, log retention, storage cleanup, and retry/failure reporting.

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

## Core Portal v0.2

The onboarding service is now evolving into the always-on YARI device portal. It still handles first-boot Wi-Fi setup, but it also stays online after the device joins normal Wi-Fi so operators can inspect and manage the device from `http://<hostname>.local` or `http://<device-ip>`.

Current API surface:

| Area | Endpoint | Purpose |
|---|---|---|
| Device | `GET /api/device/status` | Hostname, identity, OS, kernel, CPU, memory, temperature, storage, IPs, onboarding state. |
| Network | `GET /api/network/status` | Interfaces, NetworkManager devices, active connections, AP/client state. |
| Network | `GET /api/network/wifi/scan` | Nearby SSIDs with signal/security/channel when NetworkManager is available. |
| Network | `POST /api/network/wifi/save` | Save Wi-Fi credentials and hostname using the same path as first boot setup. |
| Network | `POST /api/network/ap/enable` | Force setup AP mode for maintenance. |
| Network | `POST /api/network/factory-reset` | Remove saved YARI network config and clear onboarding completion state. |
| Services | `GET /api/services` | Status for allowlisted YARI services. |
| Services | `POST /api/services/<name>/start` | Start an allowlisted service. Also supports `stop`, `restart`, `enable`, and `disable`. |
| Services | `GET /api/services/<name>/logs` | Tail journal logs for an allowlisted service. |
| Autopilot | `GET /api/autopilot/status` | Companion-computer scaffold for serial devices and MAVLink manager state. |
| MAVLink | `GET /api/mavlink/endpoints` | Read configured MAVLink endpoints. |
| MAVLink | `POST /api/mavlink/endpoints` | Persist validated serial/UDP/TCP endpoint config to `/etc/yari/mavlink-endpoints.json`. |
| ROS 2 | `GET /api/ros/status` | ROS 2 presence and node list when ROS is installed. |
| ROS 2 | `GET /api/ros/topics` | ROS 2 topic/type list. |
| Video | `GET /api/video/status` | Camera/media device discovery and video service status. |
| Data | `GET /api/data/status` | Recent MCAP files and log-manager service status. |

Service controls are intentionally allowlisted. The portal does not expose arbitrary `systemctl` access.

## YARI OS Evolution Roadmap

### Phase 1: Core Device Portal

Current implementation provides the first practical slice: persistent portal, Wi-Fi setup, network status, service status/logs, factory reset, and a single static web UI. The next hardening work is:

1. Bind setup-only actions to the AP interface or require a physical-access token.
2. Add per-device AP passwords for production images.
3. Add a captive portal redirect for phones and tablets.
4. Add downloadable support bundles with onboarding logs, NetworkManager logs, system info, and ROS status.
5. Add OTA-safe migration for `/etc/yari/*` and NetworkManager profile changes.

### Phase 2: Autopilot + Companion Computer Layer

The new autopilot, MAVLink, ROS, video, and data endpoints are scaffolding for the manager services that should follow. For PX4/ArduPilot companion computers, YARI OS should add:

1. `yari-autopilot-manager`: detect PX4/ArduPilot heartbeat, firmware type, vehicle type, system ID, component ID, arm state, flight mode, battery, GPS, EKF health, and failsafe state.
2. `yari-mavlink-router`: configure serial/UDP/TCP MAVLink routing for autopilot, ground station, Atlas, ROS bridge, and log capture.
3. `yari-ros`: manage ROS 2 launch profiles, topic discovery, lifecycle state, rosbag/MCAP recording, and common diagnostics.
4. `yari-video`: configure camera devices, encoders, ROS image topics, Foxglove bridge, and Atlas/WebRTC streams.
5. `yari-log-manager`: index `.ulg`, `.bin`, ROS bag, MCAP, and service logs for upload/download.

### Phase 3: Apps and Extensions

BlueOS-style self-service should come from an app model, not hand-editing system files. A future app package should declare:

```json
{
  "id": "example-app",
  "name": "Example App",
  "version": "1.0.0",
  "services": ["example-app.service"],
  "ports": [8080],
  "permissions": ["ros.read", "mavlink.read"],
  "ui": { "path": "/apps/example-app/" }
}
```

Portal requirements for apps:

1. Install/remove/start/stop apps from the UI.
2. Show app logs and health.
3. Support containerized apps later without requiring containers for the core portal.
4. Keep app permissions explicit so a payload-specific app cannot silently take over networking or vehicle control.

### Phase 4: Fleet Pairing and Remote Operations

YARI OS should make cloud pairing self-serve:

1. Atlas token entry and validation.
2. Foxglove remote access token entry and validation.
3. Live connection status for both agents.
4. Remote support mode with temporary tokens.
5. Offline-first operation where local portal remains useful without cloud access.

### Phase 5: Hardware Targets

Keep hardware-specific logic behind adapters:

| Target | Network | Autopilot | Video | Notes |
|---|---|---|---|---|
| Raspberry Pi | NetworkManager | USB/UART MAVLink | CSI/USB camera | Current TortoiseBot base. |
| Jetson Orin | NetworkManager | USB/UART/UDP MAVLink | CSI/GStreamer | Needs GPU video pipeline controls. |
| Generic Ubuntu mini PC | NetworkManager | UDP/serial MAVLink | USB/IP camera | Good for lab and industrial boxes. |

The core portal should stay ROS-independent and vehicle-independent. TortoiseBot, PX4 drones, ArduPilot rovers, and future edge devices should share the same onboarding, network, service, log, app, and token foundation.
