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
/usr/local/sbin/yari-service-placeholder
/usr/local/sbin/yari-service-manager
/etc/systemd/system/yari-onboarding.service
/etc/systemd/system/yari-agent.service
/etc/systemd/system/yari-mavlink-router.service
/etc/systemd/system/yari-autopilot-manager.service
/etc/systemd/system/yari-log-manager.service
/etc/systemd/system/yari-video.service
/etc/systemd/system/yari-ros.service
/opt/yari/onboarding/web/index.html
/var/lib/yari/onboarding/state.json
/etc/yari/onboarding.env
/etc/yari/mavlink-endpoints.json
/etc/yari/device-portal.json
/etc/yari/device-portal-secrets.json
```

## Branding and Themes

The portal follows the YARI Atlas design-system direction with semantic `atlas-*` CSS variables, neutral operational surfaces, monochrome controls, and reserved color only for semantic status. Red is reserved for brand artwork and destructive/error states. It ships the YARI OS SVG logo pair in the static web bundle:

```text
/opt/yari/onboarding/web/assets/yari-os-logo-dark.svg
/opt/yari/onboarding/web/assets/yari-os-logo-light.svg
```

The UI has a Light/Dark segmented toggle in the header. The selected theme is saved in browser `localStorage` as `yari-theme`; if unset, the page follows the client system preference.

## Web UI Stack Direction

The current portal is intentionally dependency-free static HTML/CSS/JS served by the local `yari-onboarding` Python service. That keeps first-boot networking robust: no Node runtime, no build artifacts needed on the robot, and fewer ways for the recovery UI to fail.

YARI OS should follow the Atlas design-system direction documented in `yari-atlas/docs/design-system.md` and implemented under `yari-atlas/frontend/components/design-system`:

- Keep the visual language compact, operational, border-led, and mostly neutral.
- Use neutral black/white action tokens for primary CTAs; do not use blue/cyan/red for normal actions.
- Reserve color for semantic status, brand artwork, and destructive/error/warning states.
- Prefer local editable primitives inspired by shadcn/Radix instead of adopting a large UI library wholesale.
- Use Lucide-style outline icons for controls, with accessible labels for icon-only actions.

Recommended evolution:

1. Keep the device runtime as static assets served by the local agent.
2. Move source development to a small Vite + React + TypeScript app when the UI outgrows one file.
3. Use Tailwind CSS for source development, but compile the result to static files for the device image.
4. Share Atlas/YARI design tokens as CSS variables or a small package consumed by Atlas, YARI OS, docs, and device portals.
5. Build a small YARI OS primitive set mirroring Atlas concepts: Button, IconButton, FormField, TextInput, Select, Tabs, StatusPill, AlertBanner, Dialog/Sheet, Table, and Toast.
6. Keep privileged operations behind the local backend API, not in browser code.
7. Consider a Rust single-binary backend later if packaging Python becomes painful across Raspberry Pi, Jetson, and generic Ubuntu edge computers.

## YARI OS Evolution Plan

YARI OS should evolve from this onboarding service into a self-serve robotics edge operating environment. The product model is closer to AuterionOS and BlueOS than a bare ROS workspace: users should flash a device, join a setup AP, configure networking and credentials in a browser, then manage robot/drone services, logs, updates, and integrations through a local GUI and Atlas.

Target first-run UX:

1. Flash a YARI OS image to the target device.
2. Power on the device.
3. If no valid network exists, the device starts `YARI-<device-id>` setup AP.
4. User opens `http://192.168.4.1`.
5. Web UI collects Wi-Fi, hostname, SSH access, Atlas/Foxglove tokens, and optional role/profile.
6. Device validates and persists configuration.
7. Device reboots or switches to client Wi-Fi.
8. If Wi-Fi fails later, fallback AP returns for recovery.

Platform phases:

1. **Minimal reliable onboarding**: AP fallback, Wi-Fi save, hostname, persistent state, reboot flow, and diagnostics. ROS remains independent.
2. **Device portal**: local GUI for network, services, logs, ROS topics, MAVLink endpoints, cameras, storage, Atlas pairing, Foxglove bridge, and troubleshooting.
3. **Platform abstraction**: NetworkManager-first adapters for Raspberry Pi, Jetson, and generic Ubuntu edge computers, with netplan/systemd-networkd only as compatibility fallbacks.
4. **Secure production posture**: unique AP credentials, signed configuration changes, secrets stored with `0600`, no arbitrary shell endpoint, disabled default SSH in production images, and physical/factory reset path.
5. **OTA and release management**: signed A/B rootfs updates, rollback, release channels, and Atlas-managed rollout status.
6. **App framework**: YARI apps packaged as containers or service bundles with manifests, install/start/stop/logs/update exposed through the local portal and Atlas. Apps may be C++, Python, Rust, ROS 2 packages, or containers depending on the job.

## OTA And Mender Direction

YARI OS requires over-the-air updates, but it should not depend on hosted Mender SaaS as the product control plane. Use Mender-compatible artifacts and client mechanics where useful, while Atlas owns the fleet UX and orchestration.

Auterion-style `.auterionos` OS images are Mender artifacts: a single distributable file containing metadata, scripts, checksums, and a root filesystem payload. YARI OS can use the same pattern for signed update artifacts without exposing Mender as the user-facing platform.

Recommended OTA architecture:

```text
YARI Atlas
  Device registry
  Device identity and entitlement
  Release channels: dev, beta, stable
  Artifact metadata
  Rollout policy and approvals
  Deployment status
  Failure diagnostics

Artifact storage
  yarios-rpi-v1.2.0.mender
  yarios-jetson-orin-v1.2.0.mender

YARI OS device agent
  Checks Atlas for assigned update
  Downloads signed artifact
  Verifies checksum/signature
  Calls the local OTA engine
  Reboots into the inactive rootfs slot
  Confirms healthy boot
  Reports success or rollback to Atlas
```

Mender should be treated as OTA plumbing, not the YARI OS product layer:

- Use Mender artifact format, client, A/B rootfs layout, boot integration, and rollback behavior where it fits.
- Do not require hosted Mender SaaS for normal YARI OS operation.
- Let Atlas provide device inventory, update channels, rollout campaigns, user approval, status, and audit history.
- Start with standalone/manual artifact installs, then add Atlas-driven downloads and staged rollouts.

OTA phases:

1. **Manual artifacts**: build signed `*.mender`/`*.yarios` artifacts and install them from local files for development.
2. **Local portal update**: user uploads or selects an artifact in the YARI OS UI, device verifies it, installs it, reboots, and reports result.
3. **Atlas-managed OTA**: device checks Atlas for assigned releases, downloads from object storage, installs, confirms, and reports.
4. **Fleet rollout**: Atlas supports release channels, staged percentage rollout, device groups, automatic rollback reporting, and update history.
5. **Production hardening**: secure boot, encrypted rootfs where hardware supports it, signed artifacts only, locked debug access, and no secrets baked into images.

## Packaging And IP Protection

A single YARI OS update file should be a signed OS/update artifact, not one monolithic executable containing Ubuntu, ROS, and all apps. The initial flash image and OTA artifacts can package a complete root filesystem with ROS, drivers, YARI services, and the web portal preinstalled.

IP protection should be layered:

- Keep proprietary YARI services closed source.
- Prefer compiled Rust/C++ binaries for sensitive production services.
- Strip symbols and avoid shipping source for proprietary components.
- Sign OTA artifacts and verify them on-device.
- Use encrypted rootfs and secure boot on supported hardware.
- Keep Ubuntu, Linux, ROS, and other open-source license obligations separate and compliant.

Physical access means perfect reverse-engineering prevention is not realistic. The goal is to make copying, tampering, and unauthorized redistribution difficult while preserving reliable field recovery and support.

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

## Phase 2 Runtime Dependencies

`yari-mavlink-router.service` uses `mavlink-routerd` when installed. If the binary is missing, the service still writes status and generated config so the portal can show the exact missing dependency instead of silently failing. `yari-autopilot-manager.service` uses optional `pymavlink` to probe enabled MAVLink endpoints for heartbeat, PX4/ArduPilot stack identity, mode, armed state, battery, GPS, and version messages; without `pymavlink`, the portal reports the dependency gap explicitly. `yari-video.service` uses optional `ffmpeg` to push a configured `/dev/video*` stream to an RTSP URL when `stream_enabled` is true; without `ffmpeg` or a camera device, the portal reports the exact stream state. `yari-log-manager.service` uses optional `pymavlink` MAVLink LOG messages to list remote PX4/ArduPilot logs and process queued log-download requests into `/var/lib/yari/flight-logs`.

`yari-agent.service` processes the local upload queue at `/var/lib/yari/upload-queue.json`. The Data page can enqueue discovered MCAP and flight-log files, retry failed items, and clear completed items. Uploads require an Atlas device token saved through the Setup page. By default, the agent posts multipart uploads to `<atlas_url>/logs/upload`; set `atlas_upload_url` in `/etc/yari/device-portal.json` or the Setup page when Atlas exposes a different ingestion endpoint. The multipart payload contains a `metadata` JSON field and a binary `file` field, authenticated with `Authorization: Bearer <atlas_token>`.

## API Summary

| Endpoint | Purpose |
|---|---|
| `GET /api/device/status` | Device identity, OS, memory, storage, temperature, IPs, onboarding state. |
| `POST /api/device/regenerate-id` | Generate a new local YARI device ID override. |
| `GET /api/setup/status` | SSH key count and redacted Atlas/Foxglove token status. |
| `POST /api/setup/config` | Save Wi-Fi, hostname, SSH key/password, Atlas URL/upload URL, Atlas token, and Foxglove token. |
| `GET /api/network/status` | NetworkManager state, interfaces, active connections, AP/client config, DNS, Ethernet, static-IP placeholder, LTE placeholder. |
| `GET /api/network/wifi/scan` | Wi-Fi scan results. |
| `POST /api/network/wifi/save` | Save SSID/password/hostname and optionally reboot. |
| `POST /api/network/ap/enable` | Start setup AP mode. |
| `POST /api/network/factory-reset` | Clear saved YARI network config and onboarding completion state. |
| `GET /api/services` | Status for known YARI services. |
| `POST /api/services/<name>/start` | Start service. Also supports `stop`, `restart`, `enable`, `disable`. |
| `GET /api/services/<name>/logs` | Tail journal logs for a known service. |
| `GET /api/logs` | Log source registry and support bundle endpoint. |
| `GET /api/logs/<source>` | Tail `onboarding`, `system`, `ros`, or `mavlink` logs. |
| `GET /api/logs/support-bundle` | Download a `.tar.gz` support bundle with status snapshots and logs. |
| `POST /api/reboot` | Reboot the device. |
| `POST /api/shutdown` | Power off the device. |
| `GET /api/autopilot/status` | PX4/ArduPilot companion-computer status scaffold, serial devices, MAVLink endpoints, firmware-upload placeholder. |
| `GET /api/mavlink/endpoints` | Read MAVLink routing endpoint config. |
| `POST /api/mavlink/endpoints` | Save serial/UDP/TCP MAVLink endpoints. |
| `GET /api/ros/status` | ROS 2 installation, node/topic status, launch profiles, MCAP recording state. |
| `GET /api/ros/topics` | ROS 2 topic/type list. |
| `POST /api/ros/recording/start` | Starts `ros2 bag record --storage mcap`; leave topics blank to record all topics. |
| `POST /api/ros/recording/stop` | Sends SIGINT to the active rosbag process and updates recording state. |
| `GET /api/video/status` | Camera/media device status, V4L2 discovery, stream profiles, persisted stream settings, and ffmpeg RTSP process state. |
| `POST /api/video/settings` | Saves stream enablement, device, RTSP URL, frame size, FPS, encoding, and bandwidth settings. |
| `GET /api/data/status` | MCAP files, PX4/ArduPilot local/remote flight logs, download queue, upload queue, and storage cleanup status. |
| `POST /api/data/flight-logs/download` | Queues a PX4/ArduPilot MAVLink LOG download by `log_id`. |
| `POST /api/data/flight-logs/retry` | Requeues failed/missing flight-log download requests. |
| `POST /api/data/uploads/enqueue` | Adds selected discovered MCAP/flight logs to the local Atlas upload queue. |
| `POST /api/data/uploads/retry` | Requeues failed/uploaded/missing upload items. |
| `POST /api/data/uploads/clear` | Clears completed upload queue items, keeping failed items by default. |
| `POST /api/data/cleanup` | Previews or deletes selected discovered MCAP/flight log files when `confirm` is true. |

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
