# YARI OS Portal Source

Svelte source for the YARI OS device-local portal.

The robot does not need Node.js at runtime. This source tree builds static files into `dist/`, and `install-yari-onboarding` installs either `portal/dist` when present or the legacy `web/` bundle as a fallback.

## Stack

- Svelte
- TypeScript
- Vite
- Tailwind CSS with YARI/Atlas-neutral design tokens

The cloud YARI Atlas app can stay on Next.js/React. This portal is intentionally a small static embedded UI served by the Python YARI OS Core API.

Vite is the development/build tool, not a runtime dependency. Svelte defines the UI components and reactivity model; Vite provides fast local development, TypeScript compilation, Tailwind integration, bundling, minification, hashed asset names, and production static output. The device only receives the built `dist/` files. It does not run Vite, Node.js, or a browser shell.

## Development

```bash
cd provisioning/yari-onboarding/portal
npm install
npm run dev
```

Build static assets:

```bash
npm run build
```

Install on a device from the repo root:

```bash
sudo provisioning/yari-onboarding/scripts/install-yari-onboarding
```

## App Runtime UI

The Apps tab is the first operator-facing slice of the YARI OS app model. It shows profile-based recommendations, installed core/service/container apps, local registry manifests, local `.yariapp` packages, health state, declared services, ports, permissions, and direct start/stop/restart/log actions. Logs use `journalctl` for service apps and Docker/Podman logs for container apps. Installed app cards can apply a matching local registry update directly when the manifest digest changes. Local package cards expose trust state (`Unsigned`, `Signed metadata`, `Verified`, or `Blocked`) from the backend signature policy so production images can reject unverified packages without hiding why. Manual JSON manifest validation/install remains available for development and support, but normal operators should use the local registry and package cards first.

Use `yari-package-app` to create local packages from manifest JSON. It is installed to `/usr/local/bin` by `install-yari-onboarding` and can add checksum metadata plus an optional OpenSSL signature over `manifest.json`. Operators can upload a package from the Apps tab without SSH; the backend validates the archive before storing it in `/var/lib/yari/app-packages`. Package cards can install/apply the embedded manifest or remove the local package file; removal does not uninstall an already-applied app manifest.

## Runtime Contract

The built portal talks to the local Python API using relative URLs only. It must work from all device portal addresses:

- `http://192.168.4.1`
- `http://<hostname>.local`
- `http://<device-ip>`

Tabs are hash-linkable, for example `#status`, `#network`, `#ros`, `#video`, and `#apps`. If no hash is provided, the portal opens Setup while onboarding is incomplete and Status once the device is configured. App manifests can use `ui.path` with these hash links so app cards can jump to their built-in management surface.

The Setup page is organized as a first-run wizard surface. It shows readiness cards for Wi-Fi, hostname, SSH access, cloud pairing, and onboarding state; Wi-Fi scan results are rendered as a selectable table; and configuration is grouped into device identity, SSH access, and Atlas/Foxglove pairing sections.

The configured-device Status page is the operator landing dashboard. It summarizes network readiness, YARI services, installed apps, OTA engine availability, and device profile, with each readiness card linking to the relevant management tab. Raw device JSON remains available below the summary for support/debugging.

The Network page follows the same operator-first pattern: connectivity, configured Wi-Fi, setup AP fallback, route, and DNS are summarized up front; Wi-Fi scan results are shown as a table with a `Use SSID` action that jumps back to Setup with the selected network filled in.

The Services page uses allowlisted service cards rather than a raw systemd surface. Each card shows active/enabled state, YARI manager heartbeat details when present, logs, and guarded lifecycle actions.

The Video page is now an operator control surface rather than a raw camera JSON dump. It summarizes camera detection, preview readiness, RTSP streaming, Foxglove compressed image topics, Atlas WebRTC readiness, and video-manager health, while keeping raw status available for troubleshooting. Operators can select detected `/dev/video*` devices, refresh snapshots, and save stream/topic settings from the same page.

The Data page follows the same pattern for MCAP and autopilot logs. It summarizes recent MCAP storage, Atlas upload queue state, remote PX4/ArduPilot logs, queued downloads, and log-manager health; tables expose queue items and remote logs while destructive cleanup requires an explicit browser confirmation.

The Autopilot page is the first PX4/ArduPilot-focused operator surface. It summarizes heartbeat state, detected flight stack, MAVLink router health, enabled endpoints, serial devices, and autopilot-manager health; operators can inspect flight mode, armed state, battery/GPS/version data, select detected serial devices, and save MAVLink endpoint JSON without dropping to SSH.

The ROS 2 page now presents runtime readiness, launch profile cards, graph summary, topic tables, node lists, and MCAP recording controls. Topics can be added to the recording list from the table, active launch profiles can be stopped with confirmation, and raw ROS/topic payloads remain available for support.

The Maintenance page now focuses on lifecycle and update operations. It summarizes Mender/update-engine readiness, release channel, signing policy, local artifacts, install state, and planned Atlas rollouts; local `.mender`/`.yarios` artifacts are shown in a table with a `Use` action, and reboot/shutdown require explicit confirmation.

API responses are never cached. Static portal assets may be precompressed and cached.

## Embedded Constraints

- Keep the first useful page load small.
- Prefer manual refresh or tab-activation refresh over continuous polling.
- Do not render full logs or huge topic lists into the DOM without slicing or virtualizing.
- Keep privileged work behind the Python API; browser code never shells out.
- Keep normal actions neutral; reserve red for destructive/error states.

## Build Metadata

`scripts/build-portal.mjs` writes `dist/portal-version.json` with:

- `name`
- `version`
- `build_time`
- `git_commit`
- `frontend_stack`

`scripts/build-portal.mjs` also writes `dist/portal-assets.json` with asset paths, sizes, gzip flags, and SHA-256 hashes. The Python API summarizes this installed manifest at `/api/portal/version`, and support bundles include the full manifest so field devices can prove exactly which frontend artifacts are installed.

The Python API exposes the installed version metadata at `/api/portal/version` and includes it in `/api/device/status`.
