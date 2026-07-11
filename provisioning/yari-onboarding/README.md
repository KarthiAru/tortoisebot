# YARI Onboarding Service

Minimal first-boot Wi-Fi onboarding and local device portal for TortoiseBot/YARI OS devices.

The service starts after boot, checks whether the device already has network connectivity, and falls back to a local setup access point when no configured network is available. In normal client Wi-Fi mode it keeps serving the portal on the device IP, so the same UI can be used for diagnostics and maintenance.

## Current Scope

This implementation is the first YARI OS core portal slice:

- AP fallback using NetworkManager hotspot mode, with a `wpa_supplicant` plus `systemd-networkd` fallback for Ubuntu Server images.
- Local web UI for Wi-Fi SSID/password and hostname.
- Persistent Wi-Fi profile written to `/etc/NetworkManager/system-connections/yari-wifi.nmconnection` when NetworkManager is available.
- Netplan fallback writer for current Ubuntu Server compatibility.
- Device profile, network, service, log, MAVLink, ROS, video, data, app, OTA readiness, and recovery-policy API scaffolding.
- Allowlisted service actions only; no arbitrary shell or systemctl endpoint.
- Optional `YARI_PORTAL_API_TOKEN` protection for mutating local portal API calls in production images.

## Dependencies

Preferred runtime dependency:

```bash
sudo apt-get install -y network-manager avahi-daemon libnss-mdns
```

NetworkManager is preferred for YARI OS because it works across Raspberry Pi, Jetson Orin, mini PCs, and other Ubuntu edge devices. Avahi and `libnss-mdns` provide the advertised `http://<hostname>.local` portal address on typical LANs. On Ubuntu Server images without NetworkManager, the service falls back to `wpa_supplicant` AP mode and `systemd-networkd` DHCP when those tools are available.

## Installed Files

```text
/usr/local/sbin/yari-onboarding
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

The device portal source now lives in `portal/` as a Svelte + TypeScript + Vite + Tailwind CSS project. The robot does not need Node.js at runtime: the built static files are installed into `/opt/yari/onboarding/web` and served by the local `yari-onboarding` Python service. If `portal/dist/index.html` is not present, the installer falls back to the legacy dependency-free `web/` bundle so recovery installs remain robust.

YARI OS should follow the Atlas design-system direction documented in `yari-atlas/docs/design-system.md` and implemented under `yari-atlas/frontend/components/design-system`:

- Keep the visual language compact, operational, border-led, and mostly neutral.
- Use neutral black/white action tokens for primary CTAs; do not use blue/cyan/red for normal actions.
- Reserve color for semantic status, brand artwork, and destructive/error/warning states.
- Prefer local editable primitives instead of adopting a large UI library wholesale.
- Use Lucide-style outline icons for controls, with accessible labels for icon-only actions.

Recommended evolution:

1. Keep the device runtime as static assets served by the local agent.
2. Use Svelte + TypeScript + Vite + Tailwind CSS for portal source development.
3. Use Tailwind CSS plus neutral YARI/Atlas design tokens for source development, but compile the result to static files for the device image.
4. Precompress generated HTML/CSS/JS/JSON/SVG assets with gzip during build/install.
5. Share Atlas/YARI design tokens as CSS variables or a small package consumed by Atlas, YARI OS, docs, and device portals.
6. Build a small YARI OS primitive set mirroring Atlas concepts: Button, IconButton, FormField, TextInput, Select, Tabs, StatusPill, AlertBanner, Dialog/Sheet, Table, and Toast.
7. Keep privileged operations behind the local backend API, not in browser code.
8. Consider a Rust single-binary backend later if packaging Python becomes painful across Raspberry Pi, Jetson, and generic Ubuntu edge computers.

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
6. **App framework**: YARI apps packaged as containers or service bundles with manifests, install/start/stop/logs/update exposed through the local portal and Atlas. The current first slice exposes an app catalog at `/api/apps` from built-in core manifests plus optional JSON manifests in `/etc/yari/apps.d`, with service-backed start/stop/restart/log actions for declared app services and Docker/Podman lifecycle/log actions for container apps. Apps may be C++, Python, Rust, ROS 2 packages, or containers depending on the job.

### YARI App Manifest v1

YARI app manifests are versioned JSON files. The schema lives at `apps/manifest.schema.json`, examples live under `apps/examples/`, and fresh installs copy both to `/opt/yari/onboarding/apps`. Locally installed app manifests live in `/etc/yari/apps.d/*.json`; the portal merges those with built-in core app manifests.

Manifest runtimes:

- `core-service`: YARI-owned systemd units baked into the base OS, such as Foxglove Bridge, Atlas Agent, MAVLink Router, ROS 2 Manager, Video Manager, and Log Manager.
- `service-bundle`: an app represented by one or more systemd units already installed on the device. The current backend can install/update their manifests, uninstall external manifests, start, stop, restart, and tail logs for declared services.
- `container`: a future YARI app runtime backed by Docker/Podman. The current backend can install/update and uninstall these manifests, detects Docker/Podman availability, shows container status, and can start/stop/restart a safe first subset of container apps from manifest metadata. Bundled local registry manifests under `/opt/yari/onboarding/apps/examples` can be installed from the portal; Atlas registry install/update orchestration is still planned. The Svelte portal presents this as an operator workflow with recommended apps, installed app cards, registry install/update cards, health metadata, and app logs, while keeping raw manifest JSON as a support/development path.

Minimal service-bundle manifest:

```json
{
  "schema_version": "1",
  "id": "rosbag-recorder",
  "name": "ROS 2 MCAP Recorder",
  "version": "0.1.0",
  "runtime": "service-bundle",
  "services": ["yari-ros"],
  "permissions": ["ros.read", "storage.write", "logs.write"],
  "ui": { "path": "#ros" }
}
```

Supported health checks:

- `service`: verifies a declared systemd service is active.
- `tcp`: opens a TCP connection to `host`/`port`, defaulting host to `127.0.0.1`.
- `http`: sends a GET request to an `http://` or `https://` URL and treats 2xx/3xx as passing.

Manifest-defined shell/command health checks are intentionally unsupported; app manifests should not become arbitrary command execution surfaces.

The Python backend enforces the same safety constraints used by the schema for container manifests: network mode must be `bridge`, `host`, or `none`; port protocols must be `tcp` or `udp`; and environment variable names must use shell-safe identifier syntax. Device mappings, host networking, privileged mode, Linux capabilities, and host volumes are also permission-gated so an app manifest is a declarative permission request rather than a raw container escape hatch.

Current container permission gates:

| Permission | Allows |
| --- | --- |
| `camera.read` | `/dev/video*` and `/dev/media*` device mappings. |
| `serial.read-write` | `/dev/ttyACM*`, `/dev/ttyUSB*`, `/dev/ttyAMA*`, and `/dev/serial/by-id/*` mappings. |
| `can.read-write` | `/dev/can*` mappings. |
| `gpu.access` | `/dev/dri/*`, `/dev/nvhost*`, and `/dev/nvmap` mappings. |
| `network.host` | Container host-network mode. |
| `storage.persistent` | App-scoped host volumes under `/var/lib/yari/apps/<app-id>/`, `/var/log/yari/apps/<app-id>/`, or `/run/yari/apps/<app-id>/`. |
| `system.capabilities` | A small allowlist of Linux capabilities such as `NET_ADMIN`, `NET_RAW`, `SYS_NICE`, and `SYS_TIME`. |
| `system.privileged` | Privileged containers for trusted first-party apps only. |

Local app packages:

- `.yariapp`, `.tar.gz`, and `.tgz` files placed in `/var/lib/yari/app-packages` are treated as local app packages.
- The current package format is intentionally minimal: a tar archive containing `manifest.json` or `app.json` at the root or one directory below it.
- Packages may also include `yari-package.json` with metadata such as `manifest_sha256`, `signed_by`, `signature_type`, and a base64 `signature` over the embedded manifest bytes.
- If `manifest_sha256` is present, the backend verifies it against the embedded manifest before installing anything.
- `/api/apps/packages` lists package filename, size, package SHA-256, manifest SHA-256, signature/verification status, embedded manifest metadata, installed version, and update status.
- `POST /api/apps/packages/upload` accepts a base64 `.yariapp`/tar upload, validates the archive and manifest, then stores it in `/var/lib/yari/app-packages`.
- `POST /api/apps/packages/<filename>/install` installs only the embedded manifest through the same validation path as registry/manual manifests; arbitrary package extraction is intentionally not supported yet.
- `POST /api/apps/packages/<filename>/delete` removes the local package file. It does not uninstall an already-applied app manifest or stop services.
- Development images allow unsigned packages. Production images can set `YARI_REQUIRE_SIGNED_APP_PACKAGES=1` so package install fails unless signature metadata is present.
- Images that include an app signing public key can set `YARI_APP_PACKAGE_PUBLIC_KEY_FILE=/etc/yari/app-package-public.pem`; when `openssl` is available, package signatures are verified with `openssl dgst -sha256 -verify`. Set `YARI_REQUIRE_VERIFIED_APP_PACKAGES=1` to reject packages whose manifest signature is missing, invalid, unverifiable, or signed with an unavailable key.
- Future signed YARI app bundles can extend this with container image references, detached signatures, provenance, Atlas registry metadata, and stronger signature formats without changing the local app-management surface.

Create a local development package from an app manifest:

```bash
yari-package-app app.json --output-dir /var/lib/yari/app-packages
```

From the portal, open Apps, choose the package file, upload it, then install or apply it from the Local Packages card.

Create and verify a signed package for stricter images:

```bash
openssl genrsa -out yari-app-private.pem 4096
openssl rsa -in yari-app-private.pem -pubout -out yari-app-public.pem
yari-package-app app.json \
  --output-dir /var/lib/yari/app-packages \
  --sign-key yari-app-private.pem \
  --signed-by "YARI Robotics"
sudo install -m 0644 yari-app-public.pem /etc/yari/app-package-public.pem
sudo systemctl restart yari-onboarding.service
```

Local registry update detection:

- `/api/apps/registry` compares each registry manifest with the installed manifest of the same app ID.
- The comparison uses a normalized SHA-256 manifest digest, not only the version string.
- Registry cards expose `installed_version`, `registry_version`, `manifest_digest`, `registry_digest`, and `update_available` so the portal and Atlas can show whether an app manifest should be applied.
- This is intentionally local-first; cloud registry metadata and signed app packages can build on the same fields later.

Minimal container manifest:

```json
{
  "schema_version": "1",
  "id": "camera-streamer",
  "name": "Camera Streamer",
  "version": "0.1.0",
  "runtime": "container",
  "ports": [{ "container": 8554, "host": 8554, "protocol": "tcp" }],
  "permissions": ["camera.read", "network.listen", "network.host", "storage.persistent"],
  "devices": ["/dev/video0"],
  "volumes": ["/var/lib/yari/apps/camera-streamer:/data"],
  "container": {
    "image": "registry.yari.io/yari/camera-streamer:0.1.0",
    "network": "host"
  }
}
```

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
- Start with standalone/manual artifact installs, then add Atlas-driven downloads and staged rollouts. The current portal exposes a guarded local OTA readiness slice: `GET /api/ota/status` reports Mender availability, local artifacts from `/var/lib/yari/ota-artifacts`, saved policy from `/etc/yari/ota.json`, and the last install state; `POST /api/ota/config` saves release-channel/update policy; `POST /api/ota/install` can install a confirmed `.mender` or `.yarios` artifact from that directory when the Mender client is installed.

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

`yari-mavlink-router.service` uses `mavlink-routerd` when installed. If the binary is missing, the service still writes status and generated config so the portal can show the exact missing dependency instead of silently failing. `yari-autopilot-manager.service` uses optional `pymavlink` to probe enabled MAVLink endpoints for heartbeat, PX4/ArduPilot stack identity, mode, armed state, battery, GPS, and version messages; without `pymavlink`, the portal reports the dependency gap explicitly. `yari-video.service` uses optional `ffmpeg` to push a configured `/dev/video*` stream to an RTSP URL when `stream_enabled` is true and the portal can capture an on-demand JPEG preview at `/api/video/snapshot`; without `ffmpeg` or a camera device, the portal reports the exact stream/preview state. The Video page also stores Foxglove and Atlas WebRTC camera topics, verifies that compressed ROS image topics are currently published, and reports Atlas WebRTC readiness from Atlas URL/token plus topic availability. `yari-log-manager.service` uses optional `pymavlink` MAVLink LOG messages to list remote PX4/ArduPilot logs and process queued log-download requests into `/var/lib/yari/flight-logs`.

`yari-agent.service` publishes lightweight device telemetry, Atlas/Foxglove remote-access readiness, and processes the local upload queue at `/var/lib/yari/upload-queue.json`. All YARI service units installed by this package run concrete `yari-service-manager` roles and are enabled by the installer so fresh images publish status on boot; the old placeholder service script has been removed. The Data page can enqueue discovered MCAP and flight-log files, retry failed items, and clear completed items. Uploads require an Atlas device token saved through the Setup page. By default, the agent posts multipart uploads to `<atlas_url>/logs/upload`; set `atlas_upload_url` in `/etc/yari/device-portal.json` or the Setup page when Atlas exposes a different ingestion endpoint. The multipart payload contains a `metadata` JSON field and a binary `file` field, authenticated with `Authorization: Bearer <atlas_token>`.

## Device Profile

YARI OS stores device role metadata in `/etc/yari/device-portal.json` under `device_profile`. The profile captures vehicle class, autopilot stack, compute target, ROS domain ID, and operator notes. This gives the portal, app runtime, and future Atlas orchestration a consistent way to select defaults for PX4/ArduPilot drones, ROS-only ground robots, Jetson companion computers, and generic edge deployments. The app catalog now includes profile-based recommendations so operators can see which core apps are expected for the selected role.

## Network Recovery Policy

YARI OS stores network recovery behavior in `/etc/yari/network-policy.json`. The policy controls whether the setup AP returns after client Wi-Fi failure, how long boot waits before fallback, whether maintenance AP should be forced on boot, and whether the portal should continue to serve on the normal client network. The Network page presents these settings with a readiness overview and a Wi-Fi scan table so operators can choose an SSID and jump back to Setup without using terminal commands. This keeps field recovery self-serve while allowing production devices to disable AP fallback where a deployment requires tighter network posture.

## Portal API Access

By default, development images keep the local portal API open on the device LAN/setup AP for a smooth first-boot flow. Production images can set `YARI_PORTAL_API_TOKEN` in the systemd environment or `/etc/yari/onboarding.env`; when set, all `POST` endpoints require either `X-YARI-Token: <token>` or `Authorization: Bearer <token>`. Read-only status endpoints remain available so operators can diagnose network/service state before entering the token. The Svelte portal shows an API token field only when `/api/portal/version` reports that a token is required, then stores the entered value in browser `localStorage` as `yari-api-token`.

## API Summary

| Endpoint | Purpose |
|---|---|
| `GET /api/device/status` | Device identity, OS, memory, storage, temperature, IPs, onboarding state, and portal version metadata. |
| `POST /api/device/regenerate-id` | Generate a new local YARI device ID override. |
| `POST /api/device/profile` | Save vehicle class, autopilot stack, compute target, ROS domain ID, and notes in `/etc/yari/device-portal.json`. |
| `GET /api/portal/version` | Installed portal build metadata and frontend stack. |
| `GET /api/setup/status` | SSH key count and redacted Atlas/Foxglove token status. |
| `POST /api/setup/config` | Save Wi-Fi, hostname, SSH key/password, Atlas URL/upload URL, Atlas token, and Foxglove token. |
| `GET /api/network/status` | NetworkManager state, interfaces, active connections, AP/client config, DNS, Ethernet, static IPv4 config, LTE placeholder. |
| `GET /api/network/diagnostics` | Connectivity checks, route/DNS probe, NetworkManager profile summaries, and recent NetworkManager failure clues. |
| `GET /api/network/wifi/scan` | Wi-Fi scan results. |
| `POST /api/network/wifi/save` | Save SSID/password/hostname and optionally reboot. |
| `POST /api/network/wifi/reconnect` | Drop setup AP if active and retry the saved `yari-wifi` client profile, returning diagnostics. |
| `POST /api/network/wifi/forget` | Remove the saved `yari-wifi` client profile and return to incomplete onboarding state. |
| `POST /api/network/ap/enable` | Start setup AP mode. |
| `POST /api/network/static-ip` | Save validated static IPv4 settings and apply them to a NetworkManager connection when available. |
| `POST /api/network/policy` | Save fallback AP, maintenance AP, fallback timeout, and client-network portal policy to `/etc/yari/network-policy.json`. |
| `POST /api/network/factory-reset` | Clear saved YARI network config and onboarding completion state. |
| `GET /api/services` | Status for known YARI services. |
| `POST /api/services/<name>/start` | Start service. Also supports `stop`, `restart`, `enable`, `disable`. |
| `GET /api/services/<name>/logs` | Tail journal logs for a known service. |
| `GET /api/apps` | YARI app catalog from built-in core manifests and `/etc/yari/apps.d/*.json`, including manifest schema version, runtime, service/container health, detected Docker/Podman runtime, permissions, ports, supported actions, device profile, and profile-based recommendations. |
| `GET /api/apps/registry` | Local app registry from `/opt/yari/onboarding/apps/examples`, with install state and validation errors. |
| `GET /api/apps/packages` | Local `.yariapp`/tar package inventory from `/var/lib/yari/app-packages`, including package SHA-256, manifest SHA-256, signature/verification status, embedded manifest, install state, and update status. |
| `POST /api/apps/registry/<id>/install` | Install or update one local registry app manifest into `/etc/yari/apps.d`. |
| `POST /api/apps/packages/upload` | Upload a base64 `.yariapp`/tar package into `/var/lib/yari/app-packages` after validating the package archive, manifest, checksum, and signature policy. |
| `POST /api/apps/packages/<filename>/install` | Install or update the embedded manifest from a local app package without extracting arbitrary payload files. |
| `POST /api/apps/packages/<filename>/delete` | Remove a local package file from `/var/lib/yari/app-packages`; installed app manifests are left unchanged. |
| `POST /api/apps/install` | Install or update a validated external YARI App Manifest v1 JSON file into `/etc/yari/apps.d`. Built-in app IDs cannot be replaced. |
| `POST /api/apps/<id>/uninstall` | Remove an external manifest from `/etc/yari/apps.d`; built-in apps cannot be removed. |
| `POST /api/apps/<id>/start` | Start services declared by an app manifest. Also supports `stop` and `restart`. Container lifecycle actions are enabled when Docker or Podman is installed and the manifest has a valid `container.image`. |
| `GET /api/apps/<id>/logs` | Tail journal logs for services declared by an app manifest. |
| `GET /api/logs` | Log source registry and support bundle endpoint. |
| `GET /api/logs/<source>` | Tail `onboarding`, `system`, `ros`, or `mavlink` logs. |
| `GET /api/logs/support-bundle` | Download a `.tar.gz` support bundle with status snapshots, sanitized YARI config files, app manifests, and logs. |
| `POST /api/reboot` | Reboot the device. |
| `POST /api/shutdown` | Power off the device. |
| `GET /api/autopilot/status` | PX4/ArduPilot companion-computer status scaffold, serial devices, MAVLink endpoints, firmware-upload placeholder. |
| `GET /api/mavlink/endpoints` | Read MAVLink routing endpoint config. |
| `POST /api/mavlink/endpoints` | Save serial/UDP/TCP MAVLink endpoints. |
| `GET /api/ros/status` | ROS 2 installation, node/topic status, launch profiles, launch state, MCAP recording state. |
| `GET /api/ros/topics` | ROS 2 topic/type list. |
| `POST /api/ros/recording/start` | Starts `ros2 bag record --storage mcap`; leave topics blank to record all topics. |
| `POST /api/ros/recording/stop` | Sends SIGINT to the active rosbag process and updates recording state. |
| `GET /api/video/status` | Camera/media device status, V4L2 discovery, stream profiles, RTSP/Foxglove/Atlas WebRTC target readiness, persisted stream settings, and ffmpeg RTSP process state. |
| `POST /api/video/settings` | Saves stream enablement, device, RTSP URL, frame size, FPS, encoding, bandwidth, Foxglove compressed topic, and Atlas WebRTC camera topic/fps settings. |
| `GET /api/data/status` | MCAP files, PX4/ArduPilot local/remote flight logs, download queue, upload queue, and storage cleanup status. |
| `GET /api/ota/status` | OTA engine readiness, Mender client status, saved update policy, local `.mender`/`.yarios` artifacts, and last install state. |
| `POST /api/ota/config` | Save release channel, auto-check/download/install flags, signed-artifact requirement, and Atlas assignment URL. |
| `POST /api/ota/install` | Installs a confirmed local OTA artifact from `/var/lib/yari/ota-artifacts` using Mender when available. |
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
- `yari-ros`: configurable launch profiles, topic discovery, lifecycle state, rosbag/MCAP recording controls.
- `yari-video`: camera selection, encoding profile, RTSP process supervision, Foxglove compressed-topic readiness, and Atlas WebRTC topic readiness.
- `yari-log-manager`: MCAP, `.ulg`, `.bin`, service log indexing, upload, and download.




