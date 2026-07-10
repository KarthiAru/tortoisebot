# YARI Onboarding Service

Minimal first-boot Wi-Fi onboarding and local device portal for TortoiseBot/YARI OS devices.

The service starts after boot, checks whether the device already has network connectivity, and falls back to a local setup access point when no configured network is available. In normal client Wi-Fi mode it keeps serving the portal on the device IP, so the same UI can be used for diagnostics and maintenance.

## Current Scope

This implementation is the first YARI OS core portal slice:

- AP fallback using NetworkManager hotspot mode, with a `wpa_supplicant` plus `systemd-networkd` fallback for Ubuntu Server images.
- Local web UI for Wi-Fi SSID/password and hostname.
- Persistent Wi-Fi profile written to `/etc/NetworkManager/system-connections/yari-wifi.nmconnection` when NetworkManager is available.
- Netplan fallback writer for current Ubuntu Server compatibility.
- Device, network, service, log, MAVLink, ROS, video, and data status API scaffolding.
- Allowlisted service actions only; no arbitrary shell or systemctl endpoint.

## Dependencies

Preferred runtime dependency:

```bash
sudo apt-get install -y network-manager
```

NetworkManager is preferred for YARI OS because it works across Raspberry Pi, Jetson Orin, mini PCs, and other Ubuntu edge devices. On Ubuntu Server images without NetworkManager, the service falls back to `wpa_supplicant` AP mode and `systemd-networkd` DHCP when those tools are available.

## Installed Files

```text
/usr/local/sbin/yari-onboarding
/etc/systemd/system/yari-onboarding.service
/opt/yari/onboarding/web/index.html
/var/lib/yari/onboarding/state.json
/etc/yari/onboarding.env
/etc/yari/mavlink-endpoints.json
```

## Portal URLs

In setup AP mode:

```text
http://192.168.4.1
```

After the device joins Wi-Fi:

```text
http://<device-ip>
http://<hostname>.local
```

The `.local` name depends on mDNS support on the client computer. Use the router-assigned IP if name resolution is unavailable.

## API Summary

| Endpoint | Purpose |
|---|---|
| `GET /api/device/status` | Device identity, OS, memory, storage, temperature, IPs, onboarding state. |
| `GET /api/network/status` | NetworkManager state, interfaces, active connections. |
| `GET /api/network/wifi/scan` | Wi-Fi scan results. |
| `POST /api/network/wifi/save` | Save SSID/password/hostname and optionally reboot. |
| `POST /api/network/ap/enable` | Start setup AP mode. |
| `POST /api/network/factory-reset` | Clear saved YARI network config and onboarding completion state. |
| `GET /api/services` | Status for known YARI services. |
| `POST /api/services/<name>/start` | Start service. Also supports `stop`, `restart`, `enable`, `disable`. |
| `GET /api/services/<name>/logs` | Tail journal logs for a known service. |
| `GET /api/autopilot/status` | PX4/ArduPilot companion-computer status scaffold. |
| `GET /api/mavlink/endpoints` | Read MAVLink routing endpoint config. |
| `POST /api/mavlink/endpoints` | Save serial/UDP/TCP MAVLink endpoints. |
| `GET /api/ros/status` | ROS 2 installation and node status. |
| `GET /api/ros/topics` | ROS 2 topic/type list. |
| `GET /api/video/status` | Camera/media device and video service status. |
| `GET /api/data/status` | Recent MCAP files and log-manager status. |

## Allowed Services

The portal can inspect and control only these service IDs:

```text
yari-onboarding
yari-agent
yari-mavlink-router
yari-autopilot-manager
yari-log-manager
yari-video
yari-ros
foxglove-bridge
```

Each ID maps to its matching `.service` unit. Additions should be deliberate and tested because this is a root-running local administration surface.

## Development Checks

Run syntax and unit checks from the repo root:

```bash
python3 -m py_compile provisioning/yari-onboarding/scripts/yari-onboarding
python3 provisioning/yari-onboarding/tests/test_yari_onboarding.py
```

The tests mock system commands and write to temporary directories so they are safe on a development machine.

## Next Platform Work

The current autopilot, MAVLink, ROS, video, and data endpoints are scaffolding. The next services should populate them with live state:

- `yari-autopilot-manager`: MAVLink heartbeat, firmware, vehicle type, mode, arm state, GPS, battery, EKF, failsafe.
- `yari-mavlink-router`: serial/UDP/TCP routing profiles for PX4, ArduPilot, Atlas, Foxglove, and ground stations.
- `yari-ros`: launch profiles, topic discovery, lifecycle state, rosbag/MCAP recording controls.
- `yari-video`: camera selection, encoding profile, ROS image topic publishing, Foxglove/Atlas streaming.
- `yari-log-manager`: MCAP, `.ulg`, `.bin`, service log indexing, upload, and download.
