<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import './app.css';
  import RecommendationCard from './RecommendationCard.svelte';
  import type { AnyRecord, DeviceStatus, NetworkDiagnostics, NetworkStatus, PortalVersion, ServiceList } from './types';

  type Tab = 'setup' | 'status' | 'network' | 'services' | 'logs' | 'maintenance' | 'autopilot' | 'ros' | 'video' | 'data' | 'apps';

  const tabs: Array<{ id: Tab; label: string }> = [
    { id: 'setup', label: 'Setup' },
    { id: 'status', label: 'Status' },
    { id: 'network', label: 'Network' },
    { id: 'services', label: 'Services' },
    { id: 'logs', label: 'Logs' },
    { id: 'maintenance', label: 'Maintenance' },
    { id: 'autopilot', label: 'Autopilot' },
    { id: 'ros', label: 'ROS 2' },
    { id: 'video', label: 'Video' },
    { id: 'data', label: 'Data' },
    { id: 'apps', label: 'Apps' },
  ];

  let activeTab: Tab = 'setup';
  let initialTabResolved = false;
  let loading = false;
  let error = '';
  let theme = 'dark';
  let apiToken = '';
  let device: DeviceStatus | null = null;
  let portalVersion: PortalVersion | null = null;
  let network: NetworkStatus | null = null;
  let diagnostics: NetworkDiagnostics | null = null;
  let services: ServiceList | null = null;
  let logOutput = 'Select a log source.';
  let logsStatus: AnyRecord | null = null;
  let setupState: AnyRecord | null = null;
  let wifiScan: AnyRecord | null = null;
  let autopilot: AnyRecord | null = null;
  let mavlink: AnyRecord | null = null;
  let ros: AnyRecord | null = null;
  let rosTopics: AnyRecord | null = null;
  let video: AnyRecord | null = null;
  let dataStatus: AnyRecord | null = null;
  let otaStatus: AnyRecord | null = null;
  let apps: AnyRecord | null = null;
  let appRegistry: AnyRecord | null = null;
  let appPackages: AnyRecord | null = null;
  let profileRecommendations: AnyRecord | null = null;
  let profilePresets: Array<AnyRecord> = [];
  let appPackageFile: File | null = null;
  let appPackageReplace = true;
  let appOutput: unknown = { message: 'Select an app action.' };
  let actionOutput: unknown = { message: 'Ready.' };
  let previewUrl = '';
  let previewState = 'Preview not loaded.';
  let mavlinkConfigText = '{}';
  let setupForm = { ssid: '', password: '', hostname: '', ssh_key: '', ssh_password: '', atlas_url: '', atlas_upload_url: '', atlas_token: '', foxglove_token: '' };
  let deviceProfileForm = { profile_preset: 'tortoisebot_rover', vehicle_class: 'ground_rover', autopilot_stack: 'ros_only', compute_target: 'raspberry_pi', ros_domain_id: 0, notes: '' };
  let rosRecordForm = { name: '', topics: '' };
  let selectedRosProfile = '';
  let videoForm = { stream_enabled: false, device: '', rtsp_url: 'rtsp://127.0.0.1:8554/yari-video', size: '640x480', fps: 15, encoding: 'mjpeg', bandwidth_kbps: '', foxglove_topic: '/camera/image_raw/compressed', atlas_webrtc_enabled: false, atlas_camera_topic: '/camera/image_raw/compressed', atlas_max_video_fps: 15 };
  let flightLogForm = { log_id: '', endpoint_name: '' };
  let networkPolicyForm = { fallback_ap_enabled: true, fallback_timeout_sec: 45, maintenance_ap_enabled: false, serve_portal_on_client_network: true };
  let otaForm = { path: '', confirm: false };
  let otaConfigForm = { release_channel: 'stable', auto_check: true, auto_download: false, auto_install: false, require_signed_artifacts: true, atlas_assignment_url: '' };
  let configImportFile: File | null = null;
  let configImportPreview: AnyRecord = { message: 'Select a redacted YARI config export to validate.' };
  let appManifestText = JSON.stringify({
    schema_version: '1',
    id: 'camera-streamer',
    name: 'Camera Streamer',
    version: '0.1.0',
    runtime: 'container',
    description: 'Camera streaming workload managed by YARI OS.',
    ports: [{ container: 8554, host: 8554, protocol: 'tcp' }],
    permissions: ['camera.read', 'network.listen', 'network.host', 'storage.persistent'],
    devices: ['/dev/video0'],
    container: { image: 'registry.yari.io/yari/camera-streamer:0.1.0', network: 'host' },
    ui: { path: '#video' },
  }, null, 2);

  function authHeaders(extra?: HeadersInit) {
    const headers = new Headers(extra || {});
    if (apiToken.trim()) headers.set('x-yari-token', apiToken.trim());
    return headers;
  }

  async function api<T>(path: string, init?: RequestInit): Promise<T> {
    const headers = authHeaders(init?.headers);
    const response = await fetch(path, { ...init, headers });
    const contentType = response.headers.get('content-type') || '';
    const data = contentType.includes('application/json') ? await response.json() : await response.text();
    if (!response.ok) throw new Error((data as AnyRecord).error || response.statusText);
    return data as T;
  }

  async function post<T>(path: string, body: AnyRecord = {}): Promise<T> {
    return api<T>(path, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  }

  function pretty(value: unknown) {
    return JSON.stringify(value, null, 2);
  }

  function setTheme(nextTheme: string) {
    theme = nextTheme;
    document.documentElement.dataset.theme = nextTheme;
    localStorage.setItem('yari-theme', nextTheme);
  }

  function setApiToken(value: string) {
    apiToken = value;
    localStorage.setItem('yari-api-token', value);
  }

  function setAction(value: unknown) {
    actionOutput = value;
  }

  function tabFromHash(): Tab | null {
    const candidate = location.hash.replace(/^#/, '') as Tab;
    return tabs.some((tab) => tab.id === candidate) ? candidate : null;
  }

  function selectTab(tab: Tab, updateHash = true) {
    activeTab = tab;
    if (updateHash && location.hash !== `#${tab}`) history.pushState(null, '', `#${tab}`);
  }

  function resolveInitialTab() {
    const hashTab = tabFromHash();
    if (hashTab) {
      activeTab = hashTab;
      initialTabResolved = true;
      return;
    }
    if (initialTabResolved) return;
    const state = setupState || device?.onboarding || {};
    const complete = Boolean(state.complete);
    const mode = String(state.mode || '');
    const nextTab: Tab = complete || mode === 'client' ? 'status' : 'setup';
    activeTab = nextTab;
    history.replaceState(null, '', `#${nextTab}`);
    initialTabResolved = true;
  }

  function openUiPath(path: unknown) {
    if (typeof path !== 'string') return;
    if (!path.startsWith('#')) return;
    const target = path.slice(1) as Tab;
    if (tabs.some((tab) => tab.id === target)) selectTab(target);
  }

  function formatPort(port: unknown) {
    if (typeof port === 'object' && port !== null) {
      const item = port as AnyRecord;
      const protocol = item.protocol ? `/${item.protocol}` : '';
      return item.host ? `${item.host}:${item.container}${protocol}` : `${item.container}${protocol}`;
    }
    return String(port);
  }

  function listText(items: unknown, fallback = 'none') {
    return Array.isArray(items) && items.length > 0 ? items.join(', ') : fallback;
  }

  function formatBytes(value: unknown) {
    const bytes = Number(value || 0);
    if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
  }

  function portalBuildTime() {
    const value = portalVersion?.build_time;
    if (!value) return 'unknown';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
  }

  function portalAssetSummaryItems() {
    const assets = portalVersion?.assets || {};
    return [
      { label: 'Assets', value: assets.available ? String(assets.asset_count ?? 0) : 'unavailable' },
      { label: 'Compressed', value: assets.available ? String(assets.gzip_asset_count ?? 0) : 'unavailable' },
      { label: 'Raw bytes', value: formatBytes(assets.total_bytes) },
      { label: 'Gzip bytes', value: formatBytes(assets.gzip_total_bytes) },
      { label: 'Saved', value: assets.available ? formatBytes(assets.gzip_savings_bytes) + ' / ' + String(assets.gzip_savings_percent ?? 0) + '%' : 'unavailable' },
      { label: 'Optimization', value: assets.optimization_state || 'unknown' },
    ];
  }

  function arrayBufferToBase64(buffer: ArrayBuffer) {
    const bytes = new Uint8Array(buffer);
    const chunkSize = 0x8000;
    let binary = '';
    for (let index = 0; index < bytes.length; index += chunkSize) {
      binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
    }
    return btoa(binary);
  }

  function formatTime(value: unknown) {
    const seconds = Number(value || 0);
    if (!Number.isFinite(seconds) || seconds <= 0) return 'unknown';
    return new Date(seconds * 1000).toLocaleString();
  }

  function runtimeLabel(app: AnyRecord) {
    const runtime = app.runtime || app.kind || 'unknown';
    if (runtime === 'core-service') return 'Core service';
    if (runtime === 'service-bundle') return 'Service bundle';
    if (runtime === 'container') return 'Container';
    return String(runtime);
  }

  function healthClass(health: unknown) {
    const value = String(health || '').toLowerCase();
    if (['ok', 'active', 'healthy', 'running'].includes(value)) return 'ok';
    if (['warning', 'degraded', 'unknown', 'inactive'].includes(value)) return 'warn';
    if (['error', 'failed', 'unhealthy'].includes(value)) return 'bad';
    return '';
  }

  function permissionReview(app: AnyRecord | undefined) {
    return app?.permission_review || { risk: 'low', items: [] };
  }

  function permissionRiskClass(app: AnyRecord | undefined) {
    const risk = String(permissionReview(app).risk || 'low').toLowerCase();
    if (risk === 'high') return 'bad';
    if (risk === 'medium') return 'warn';
    return 'ok';
  }

  function permissionRiskLabel(app: AnyRecord | undefined) {
    const risk = String(permissionReview(app).risk || 'low').toLowerCase();
    if (risk === 'high') return 'High risk';
    if (risk === 'medium') return 'Medium risk';
    return 'Low risk';
  }

  function permissionReviewText(app: AnyRecord | undefined) {
    const items = permissionReview(app).items;
    if (!Array.isArray(items) || items.length === 0) return 'No elevated permissions declared.';
    return items.map((item: AnyRecord) => String(item.permission) + ': ' + String(item.reason || item.risk)).join(', ');
  }

  function registryActionLabel(app: AnyRecord) {
    const actions = app.actions || {};
    if (actions.update) return 'Apply update';
    if (actions.install) return 'Install manifest';
    if (app.installed_source === 'builtin') return 'Managed by base image';
    if (app.installed) return 'Up to date';
    return 'Install manifest';
  }

  function installedAppById(appId: string) {
    return (apps?.apps || []).find((app: AnyRecord) => app.id === appId);
  }

  function registryAppById(appId: string) {
    return (appRegistry?.apps || []).find((app: AnyRecord) => app.id === appId);
  }

  function recommendationApp(item: AnyRecord) {
    return installedAppById(String(item.id || '')) || registryAppById(String(item.id || '')) || item;
  }

  function recommendationStatus(item: AnyRecord) {
    const app = recommendationApp(item);
    if (app.update?.update_available) return 'Update available';
    if (app.installed) return 'Installed';
    if (registryAppById(String(item.id || ''))) return 'Available';
    return 'Recommended';
  }

  function recommendationStatusClass(item: AnyRecord) {
    const app = recommendationApp(item);
    if (app.update?.update_available) return 'warn';
    if (app.installed) return 'ok';
    return '';
  }

  function packageTrust(pkg: AnyRecord) {
    const signature = pkg.signature || {};
    const status = String(signature.status || 'missing');
    const verificationRequired = Boolean(signature.verification_required || appPackages?.signature_verification_required);
    const signatureRequired = Boolean(signature.required || appPackages?.signature_required);
    if (signature.verified) {
      return { className: 'ok', label: 'Verified', detail: `Signed by ${signature.signed_by || 'configured key'}` };
    }
    if (verificationRequired) {
      return { className: 'bad', label: 'Blocked', detail: `Verification required: ${status}` };
    }
    if (signatureRequired && !signature.present) {
      return { className: 'bad', label: 'Unsigned', detail: 'Signature metadata is required by this image.' };
    }
    if (signature.present) {
      if (status === 'public-key-missing') return { className: 'warn', label: 'Signed metadata', detail: 'Public key not installed, so signature is not verified.' };
      if (status === 'openssl-missing') return { className: 'warn', label: 'Signed metadata', detail: 'OpenSSL is unavailable, so signature is not verified.' };
      if (status === 'invalid-signature-encoding' || status === 'verification-failed') return { className: 'bad', label: 'Invalid signature', detail: status };
      return { className: 'warn', label: 'Signed metadata', detail: status };
    }
    return { className: 'warn', label: 'Unsigned', detail: 'Allowed for development images only.' };
  }

  function packageTrustSummary() {
    const signed = appPackages?.signature_required ? 'signature required' : 'unsigned packages allowed';
    const verified = appPackages?.signature_verification_required ? 'verification required' : 'verification optional';
    return `${signed}; ${verified}`;
  }

  function recommendationSummary(item: AnyRecord) {
    const reasons = Array.isArray(item.reasons) ? item.reasons.join(', ') : item.reason || '';
    return reasons || item.description || 'Recommended for this device profile.';
  }

  function profileRecommendationItems() {
    return profileRecommendations?.recommendations || apps?.recommendations || [];
  }

  function applyProfilePreset(preset: AnyRecord) {
    deviceProfileForm = { ...deviceProfileForm, ...preset.values };
    refreshProfileRecommendations();
  }

  function serviceItems() {
    return services?.services || [];
  }

  function serviceActiveCount() {
    return serviceItems().filter((service: AnyRecord) => service.active === 'active').length;
  }

  function serviceLabel(name: string) {
    return name.replace(/^yari-/, '').replace(/-/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
  }

  function serviceStateClass(service: AnyRecord) {
    if (service.active === 'active') return 'ok';
    if (service.active === 'failed') return 'bad';
    return 'warn';
  }

  function serviceManagerDetail(service: AnyRecord) {
    const state = service.manager_state || {};
    if (!state.available) return state.message || 'No manager heartbeat yet';
    const age = Number(state.age_seconds ?? 0);
    const message = state.message || state.state || state.status || 'manager heartbeat available';
    return `${message} (${age}s ago)`;
  }

  function autopilotItems() {
    const manager = autopilot?.manager_state || {};
    const router = autopilot?.router_state || {};
    const serialDevices = autopilot?.serial_devices || [];
    const endpoints = autopilot?.endpoints || mavlink?.endpoints || [];
    return [
      {
        label: 'Autopilot Link',
        state: autopilot?.connected || autopilot?.heartbeat ? 'ok' : 'warn',
        detail: autopilot?.heartbeat ? 'heartbeat received' : autopilot?.connected ? 'serial device detected' : 'no heartbeat yet',
      },
      {
        label: 'Flight Stack',
        state: autopilot?.flight_stack && autopilot.flight_stack !== 'unknown' ? 'ok' : 'warn',
        detail: autopilot?.flight_stack || 'unknown',
      },
      {
        label: 'MAVLink Router',
        state: autopilot?.mavlink_router?.active === 'active' || router.available ? 'ok' : 'warn',
        detail: router.message || autopilot?.mavlink_router?.active || 'router not active',
      },
      {
        label: 'Endpoints',
        state: endpoints.some((endpoint: AnyRecord) => endpoint.enabled) ? 'ok' : 'warn',
        detail: `${endpoints.filter((endpoint: AnyRecord) => endpoint.enabled).length}/${endpoints.length} enabled`,
      },
      {
        label: 'Serial Devices',
        state: serialDevices.length > 0 ? 'ok' : 'warn',
        detail: serialDevices.length > 0 ? `${serialDevices.length} detected` : 'none detected',
      },
      {
        label: 'Manager',
        state: manager.available || autopilot?.manager?.active === 'active' ? 'ok' : 'warn',
        detail: manager.message || autopilot?.manager?.active || 'manager heartbeat unavailable',
      },
    ];
  }

  function mavlinkEndpoints() {
    return mavlink?.endpoints || autopilot?.endpoints || [];
  }

  function serialDevices() {
    return autopilot?.serial_devices || [];
  }

  function useSerialDevice(devicePath: unknown) {
    const device = String(devicePath || '');
    if (!device) return;
    const endpoints = mavlinkEndpoints();
    const next = endpoints.length > 0 ? endpoints.map((endpoint: AnyRecord, index: number) => index === 0 ? { ...endpoint, type: 'serial', device, enabled: true } : endpoint) : [{ name: 'autopilot-serial', type: 'serial', device, baud: 57600, enabled: true }];
    mavlinkConfigText = pretty({ endpoints: next });
  }

  function rosTopicItems() {
    return rosTopics?.topics || ros?.topics || [];
  }

  function rosNodes() {
    return ros?.nodes || [];
  }

  function rosLaunchProfiles() {
    return ros?.launch_profiles || [];
  }

  function rosItems() {
    const nodes = ros?.nodes || [];
    const topics = rosTopicItems();
    const recording = ros?.recording || {};
    const launch = ros?.launch || {};
    const manager = ros?.manager_state || {};
    return [
      {
        label: 'ROS 2',
        state: ros?.installed ? 'ok' : 'bad',
        detail: ros?.installed ? `${ros?.ros_distro || 'humble'} available` : ros?.error || 'ros2 command not found',
      },
      {
        label: 'Graph',
        state: nodes.length > 0 || topics.length > 0 ? 'ok' : 'warn',
        detail: `${nodes.length} nodes, ${topics.length} topics`,
      },
      {
        label: 'Launch',
        state: launch.active || launch.running ? 'ok' : rosLaunchProfiles().length > 0 ? 'warn' : 'bad',
        detail: launch.active || launch.running ? launch.profile || launch.name || 'profile running' : `${rosLaunchProfiles().length} profiles available`,
      },
      {
        label: 'MCAP Recording',
        state: recording.active ? 'ok' : 'warn',
        detail: recording.active ? recording.output_dir || `pid ${recording.pid}` : recording.message || 'not recording',
      },
      {
        label: 'Manager',
        state: manager.available || ros?.service?.active === 'active' ? 'ok' : 'warn',
        detail: manager.message || ros?.service?.active || 'manager heartbeat unavailable',
      },
    ];
  }

  function topicTypeClass(type: unknown) {
    const value = String(type || '');
    if (value.includes('sensor_msgs/msg/Image') || value.includes('sensor_msgs/msg/CompressedImage')) return 'camera';
    if (value.includes('sensor_msgs/msg/LaserScan') || value.includes('PointCloud')) return 'perception';
    if (value.includes('nav_msgs/') || value.includes('geometry_msgs/msg/Twist') || value.includes('tf2_msgs/')) return 'navigation';
    return 'system';
  }

  function topicTypeLabel(type: unknown) {
    const category = topicTypeClass(type);
    if (category === 'camera') return 'Camera';
    if (category === 'perception') return 'Perception';
    if (category === 'navigation') return 'Navigation';
    return 'System';
  }

  function useTopicForRecording(topic: string) {
    const existing = rosRecordForm.topics.split(/\s+/).filter(Boolean);
    if (!existing.includes(topic)) existing.push(topic);
    rosRecordForm.topics = existing.join('\n');
  }

  function videoItems() {
    const settings = video?.settings || {};
    const preview = video?.preview || {};
    const targets = video?.stream_targets || {};
    const service = video?.service || {};
    const manager = video?.manager_state || {};
    const devices = video?.devices || [];
    return [
      {
        label: 'Camera',
        state: devices.length > 0 ? 'ok' : 'warn',
        detail: devices.length > 0 ? `${devices.length} device${devices.length === 1 ? '' : 's'} detected` : 'no /dev/video devices detected',
      },
      {
        label: 'Preview',
        state: preview.available ? 'ok' : 'warn',
        detail: preview.available ? 'snapshot endpoint ready' : preview.message || 'preview unavailable',
      },
      {
        label: 'RTSP',
        state: settings.stream_enabled || service.active === 'active' ? 'ok' : 'warn',
        detail: settings.stream_enabled ? settings.rtsp_url || 'stream enabled' : 'stream disabled',
      },
      {
        label: 'Foxglove',
        state: settings.foxglove_topic ? 'ok' : 'warn',
        detail: settings.foxglove_topic || targets.foxglove?.topic || 'compressed topic not configured',
      },
      {
        label: 'Atlas WebRTC',
        state: settings.atlas_webrtc_enabled ? 'ok' : 'warn',
        detail: settings.atlas_webrtc_enabled ? settings.atlas_camera_topic || 'enabled' : 'disabled',
      },
      {
        label: 'Manager',
        state: manager.available || service.active === 'active' ? 'ok' : 'warn',
        detail: manager.message || service.active || 'manager heartbeat unavailable',
      },
    ];
  }

  function videoDevices() {
    return video?.devices || [];
  }

  function streamTargets() {
    return Object.entries(video?.stream_targets || {}) as Array<[string, AnyRecord]>;
  }

  function useVideoDevice(devicePath: unknown) {
    if (typeof devicePath === 'string' && devicePath) videoForm.device = devicePath;
  }

  function dataItems() {
    const mcap = dataStatus?.mcap_logs || [];
    const uploads = dataStatus?.upload_queue || [];
    const downloads = dataStatus?.flight_log_downloads?.items || dataStatus?.flight_log_downloads || [];
    const remote = dataStatus?.remote_flight_logs || {};
    const service = dataStatus?.service || {};
    const manager = dataStatus?.manager_state || {};
    const failedUploads = uploads.filter((item: AnyRecord) => ['failed', 'error'].includes(String(item.state || item.status || '').toLowerCase())).length;
    const pendingUploads = uploads.filter((item: AnyRecord) => ['pending', 'queued', 'retry'].includes(String(item.state || item.status || '').toLowerCase())).length;
    return [
      {
        label: 'MCAP Logs',
        state: mcap.length > 0 ? 'ok' : 'warn',
        detail: mcap.length > 0 ? `${mcap.length} recent logs, ${formatBytes(mcap.reduce((total: number, item: AnyRecord) => total + Number(item.bytes || 0), 0))}` : 'no MCAP logs found',
      },
      {
        label: 'Upload Queue',
        state: failedUploads > 0 ? 'bad' : pendingUploads > 0 ? 'warn' : uploads.length > 0 ? 'ok' : 'warn',
        detail: uploads.length > 0 ? `${uploads.length} items, ${pendingUploads} pending, ${failedUploads} failed` : 'queue is empty',
      },
      {
        label: 'Remote Flight Logs',
        state: remote.ok || (remote.logs || []).length > 0 ? 'ok' : 'warn',
        detail: (remote.logs || []).length > 0 ? `${remote.logs.length} logs reported by autopilot` : remote.state || remote.message || 'not available',
      },
      {
        label: 'Downloads',
        state: downloads.length > 0 ? 'ok' : 'warn',
        detail: downloads.length > 0 ? `${downloads.length} queued/completed requests` : 'no flight-log downloads queued',
      },
      {
        label: 'Log Manager',
        state: manager.available || service.active === 'active' ? 'ok' : 'warn',
        detail: manager.message || service.active || 'manager heartbeat unavailable',
      },
    ];
  }

  function mcapLogs() {
    return dataStatus?.mcap_logs || [];
  }

  function uploadQueue() {
    return dataStatus?.upload_queue || [];
  }

  function remoteFlightLogs() {
    return dataStatus?.remote_flight_logs?.logs || [];
  }

  function flightLogDownloads() {
    const downloads = dataStatus?.flight_log_downloads || {};
    return Array.isArray(downloads) ? downloads : downloads.items || [];
  }

  function queueRemoteFlightLog(log: AnyRecord) {
    flightLogForm.log_id = String(log.id ?? log.num ?? log.log_id ?? '');
    flightLogForm.endpoint_name = log.endpoint_name || flightLogForm.endpoint_name;
  }

  function networkItems() {
    const checks = diagnostics?.checks || {};
    const configuredSsid = network?.config?.client_wifi?.configured_ssid || 'not configured';
    const apMode = network?.config?.ap_mode || {};
    const policy = network?.config?.policy || {};
    return [
      {
        label: 'Connectivity',
        state: network?.connected || diagnostics?.connectivity ? 'ok' : 'bad',
        detail: network?.connected || diagnostics?.connectivity ? 'LAN/internet reachable' : 'no confirmed connectivity',
      },
      {
        label: 'Configured Wi-Fi',
        state: configuredSsid === 'not configured' ? 'warn' : 'ok',
        detail: configuredSsid,
      },
      {
        label: 'Setup AP',
        state: policy.fallback_ap_enabled === false ? 'warn' : 'ok',
        detail: `${apMode.ssid || 'YARI setup AP'} / ${apMode.security || 'open'}`,
      },
      {
        label: 'Default route',
        state: checks.default_route ? 'ok' : 'warn',
        detail: checks.default_route ? 'present' : 'missing',
      },
      {
        label: 'DNS',
        state: checks.dns_servers ? 'ok' : 'warn',
        detail: listText(diagnostics?.dns?.servers, 'no DNS servers'),
      },
    ];
  }

  function wifiNetworks() {
    return wifiScan?.networks || [];
  }

  function otaItems() {
    const mender = otaStatus?.mender || {};
    const config = otaStatus?.config || {};
    const state = otaStatus?.state || {};
    const artifacts = otaStatus?.artifacts || [];
    return [
      {
        label: 'Update Engine',
        state: mender.available ? 'ok' : 'warn',
        detail: mender.available ? mender.version || 'mender available' : mender.error || 'mender not installed',
      },
      {
        label: 'Channel',
        state: config.release_channel ? 'ok' : 'warn',
        detail: config.release_channel || 'stable',
      },
      {
        label: 'Signing',
        state: config.require_signed_artifacts ? 'ok' : 'warn',
        detail: config.require_signed_artifacts ? 'signed artifacts required' : 'unsigned artifacts allowed',
      },
      {
        label: 'Artifacts',
        state: artifacts.length > 0 ? 'ok' : 'warn',
        detail: artifacts.length > 0 ? `${artifacts.length} local artifacts` : 'no local artifacts found',
      },
      {
        label: 'State',
        state: String(state.state || 'idle').includes('failed') ? 'bad' : String(state.state || 'idle').includes('installed') ? 'ok' : 'warn',
        detail: state.state || 'idle',
      },
      {
        label: 'Atlas Rollouts',
        state: otaStatus?.atlas_managed?.planned ? 'warn' : 'ok',
        detail: otaStatus?.atlas_managed?.message || 'not configured',
      },
    ];
  }

  function otaArtifacts() {
    return otaStatus?.artifacts || [];
  }

  function useOtaArtifact(artifact: AnyRecord) {
    otaForm.path = artifact.name || artifact.path || '';
  }

  function setupItems() {
    const state = setupState?.state || setupState || device?.onboarding || {};
    const configuredSsid = network?.config?.client_wifi?.configured_ssid || setupForm.ssid || 'not set';
    const sshConfigured = Boolean(setupState?.ssh?.authorized_keys || setupState?.ssh?.password_enabled || setupForm.ssh_key || setupForm.ssh_password);
    const tokensConfigured = Boolean(setupState?.tokens?.atlas || setupState?.tokens?.foxglove || setupForm.atlas_token || setupForm.foxglove_token);
    return [
      {
        label: 'Wi-Fi',
        state: configuredSsid !== 'not set' ? 'ok' : 'warn',
        detail: configuredSsid,
      },
      {
        label: 'Hostname',
        state: setupForm.hostname || device?.hostname ? 'ok' : 'warn',
        detail: setupForm.hostname || device?.hostname || 'not set',
      },
      {
        label: 'SSH Access',
        state: sshConfigured ? 'ok' : 'warn',
        detail: sshConfigured ? 'key/password provided' : 'no setup credential in form',
      },
      {
        label: 'Cloud Pairing',
        state: tokensConfigured ? 'ok' : 'warn',
        detail: tokensConfigured ? 'tokens provided' : 'Atlas/Foxglove tokens optional',
      },
      {
        label: 'State',
        state: state.complete || state.mode === 'client' || state.mode === 'configured' ? 'ok' : 'warn',
        detail: state.mode || 'setup',
      },
    ];
  }

  function wifiSecurityLabel(network: AnyRecord) {
    return network.security || network.security_flags || network.encryption || 'unknown';
  }

  function useWifiNetwork(ssid: string) {
    setupForm.ssid = ssid;
    selectTab('setup');
  }

  function readinessItems() {
    const serviceItems = services?.services || [];
    const activeServices = serviceItems.filter((service: AnyRecord) => service.active === 'active').length;
    const installedApps = apps?.apps || [];
    const unhealthyApps = installedApps.filter((app: AnyRecord) => ['bad', 'error', 'failed', 'unhealthy'].includes(healthClass(app.health))).length;
    const profile = device?.profile || apps?.device_profile || {};
    const otaReady = Boolean(otaStatus?.mender?.available || otaStatus?.mender_available || otaStatus?.available);
    const portalAssets = portalVersion?.assets || {};
    const portalOptimized = Boolean(portalAssets.optimized);
    return [
      {
        label: 'Network',
        state: network?.connected || Boolean(device?.ip_addresses?.length) ? 'ok' : 'bad',
        detail: network?.connected ? 'client network connected' : device?.ip_addresses?.length ? device.ip_addresses.join(' ') : 'no IP address reported',
        tab: 'network' as Tab,
      },
      {
        label: 'Services',
        state: serviceItems.length === 0 ? 'warn' : activeServices === serviceItems.length ? 'ok' : 'warn',
        detail: serviceItems.length === 0 ? 'service inventory unavailable' : `${activeServices}/${serviceItems.length} active`,
        tab: 'services' as Tab,
      },
      {
        label: 'Portal',
        state: portalOptimized ? 'ok' : 'warn',
        detail: portalAssets.optimization_message || (portalOptimized ? String(portalAssets.gzip_asset_count ?? 0) + ' compressed assets, ' + String(portalAssets.gzip_savings_percent ?? 0) + '% saved' : 'build optimization metadata missing'),
        tab: 'status' as Tab,
      },
      {
        label: 'Apps',
        state: unhealthyApps > 0 ? 'bad' : installedApps.length > 0 ? 'ok' : 'warn',
        detail: installedApps.length > 0 ? `${installedApps.length} installed, ${unhealthyApps} unhealthy` : 'no app catalog loaded',
        tab: 'apps' as Tab,
      },
      {
        label: 'OTA',
        state: otaReady ? 'ok' : 'warn',
        detail: otaReady ? 'Mender/update engine available' : 'OTA engine not detected yet',
        tab: 'maintenance' as Tab,
      },
      {
        label: 'Profile',
        state: profile.vehicle_class ? 'ok' : 'warn',
        detail: profile.vehicle_class ? `${profile.vehicle_class} / ${profile.autopilot_stack || 'none'}` : 'device role not set',
        tab: 'status' as Tab,
      },
    ];
  }

  function logSourceEntries() {
    return Object.entries(logsStatus?.sources || {}) as Array<[string, AnyRecord]>;
  }

  function logSourceLabel(source: string) {
    return source.replace(/[-_]/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
  }

  async function refreshDevice() {
    device = await api<DeviceStatus>('/api/device/status');
    portalVersion = await api<PortalVersion>('/api/portal/version');
    setupState = await api<AnyRecord>('/api/setup/status');
    const presetCatalog = await api<AnyRecord>('/api/device/profile/presets');
    profilePresets = presetCatalog.presets || [];
    setupForm.hostname = device.hostname || setupForm.hostname || 'tortoisebot';
    const profile = device.profile || {};
    deviceProfileForm = {
      profile_preset: profile.profile_preset || 'custom',
      vehicle_class: profile.vehicle_class || 'ground_rover',
      autopilot_stack: profile.autopilot_stack || 'ros_only',
      compute_target: profile.compute_target || 'raspberry_pi',
      ros_domain_id: Number(profile.ros_domain_id ?? 0),
      notes: profile.notes || '',
    };
    await refreshProfileRecommendations();
  }

  async function refreshNetwork() {
    network = await api<NetworkStatus>('/api/network/status');
    diagnostics = await api<NetworkDiagnostics>('/api/network/diagnostics');
    const policy = network.config?.policy || {};
    networkPolicyForm = {
      fallback_ap_enabled: Boolean(policy.fallback_ap_enabled ?? true),
      fallback_timeout_sec: Number(policy.fallback_timeout_sec ?? 45),
      maintenance_ap_enabled: Boolean(policy.maintenance_ap_enabled),
      serve_portal_on_client_network: Boolean(policy.serve_portal_on_client_network ?? true),
    };
  }

  async function refreshServices() {
    services = await api<ServiceList>('/api/services');
  }

  async function refreshLogs() {
    logsStatus = await api<AnyRecord>('/api/logs');
  }

  async function refreshAutopilot() {
    autopilot = await api<AnyRecord>('/api/autopilot/status');
    mavlink = await api<AnyRecord>('/api/mavlink/endpoints');
    mavlinkConfigText = pretty(mavlink);
  }

  async function saveMavlinkConfig() {
    try {
      setAction(await post('/api/mavlink/endpoints', JSON.parse(mavlinkConfigText)));
      await refreshAutopilot();
    } catch (err) {
      setAction({ ok: false, error: err instanceof Error ? err.message : String(err) });
    }
  }

  async function refreshRos() {
    ros = await api<AnyRecord>('/api/ros/status');
    rosTopics = await api<AnyRecord>('/api/ros/topics');
    const profiles = ros.launch_profiles || [];
    if (!selectedRosProfile && profiles.length > 0) selectedRosProfile = profiles[0].name;
  }

  async function refreshVideo() {
    video = await api<AnyRecord>('/api/video/status');
    const settings = video.settings || {};
    videoForm = {
      stream_enabled: Boolean(settings.stream_enabled),
      device: settings.device || '',
      rtsp_url: settings.rtsp_url || 'rtsp://127.0.0.1:8554/yari-video',
      size: settings.size || '640x480',
      fps: Number(settings.fps ?? 15),
      encoding: settings.encoding || 'mjpeg',
      bandwidth_kbps: settings.bandwidth_kbps ?? '',
      foxglove_topic: settings.foxglove_topic || '/camera/image_raw/compressed',
      atlas_webrtc_enabled: Boolean(settings.atlas_webrtc_enabled),
      atlas_camera_topic: settings.atlas_camera_topic || '/camera/image_raw/compressed',
      atlas_max_video_fps: Number(settings.atlas_max_video_fps ?? settings.fps ?? 15),
    };
  }

  async function refreshData() {
    dataStatus = await api<AnyRecord>('/api/data/status');
  }

  async function refreshOta() {
    otaStatus = await api<AnyRecord>('/api/ota/status');
    const firstArtifact = otaStatus?.artifacts?.[0]?.name;
    if (!otaForm.path && firstArtifact) otaForm.path = firstArtifact;
    const config = otaStatus?.config || {};
    otaConfigForm = {
      release_channel: config.release_channel || 'stable',
      auto_check: Boolean(config.auto_check ?? true),
      auto_download: Boolean(config.auto_download),
      auto_install: Boolean(config.auto_install),
      require_signed_artifacts: Boolean(config.require_signed_artifacts ?? true),
      atlas_assignment_url: config.atlas_assignment_url || '',
    };
  }

  async function refreshApps() {
    apps = await api<AnyRecord>('/api/apps');
    appRegistry = await api<AnyRecord>('/api/apps/registry');
    appPackages = await api<AnyRecord>('/api/apps/packages');
  }


  async function refreshProfileRecommendations() {
    profileRecommendations = await post<AnyRecord>('/api/apps/recommendations', { device_profile: deviceProfileForm });
  }

  async function refreshAll() {
    loading = true;
    error = '';
    try {
      await Promise.allSettled([refreshDevice(), refreshNetwork(), refreshServices(), refreshLogs(), refreshAutopilot(), refreshRos(), refreshVideo(), refreshData(), refreshOta(), refreshApps()]);
      resolveInitialTab();
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    } finally {
      loading = false;
    }
  }

  async function scanWifi() {
    wifiScan = await api<AnyRecord>('/api/network/wifi/scan');
  }

  async function saveSetup() {
    setupState = await post('/api/setup/config', { ...setupForm, device_profile: deviceProfileForm });
    setAction(setupState);
    await Promise.allSettled([refreshDevice(), refreshNetwork(), refreshApps(), refreshProfileRecommendations()]);
  }

  async function enableAp() {
    setAction(await post('/api/network/ap/enable'));
    await refreshNetwork();
  }

  async function reconnectWifi() {
    diagnostics = await post('/api/network/wifi/reconnect');
  }

  async function forgetWifi() {
    if (!confirm('Forget saved Wi-Fi profile? The setup AP may be needed to reconnect.')) return;
    diagnostics = await post('/api/network/wifi/forget');
    await refreshNetwork();
  }

  async function saveNetworkPolicy() {
    setAction(await post('/api/network/policy', networkPolicyForm));
    await refreshNetwork();
  }

  async function serviceAction(name: string, action: string) {
    logOutput = pretty(await post(`/api/services/${encodeURIComponent(name)}/${action}`));
    await refreshServices();
  }

  async function serviceLogs(name: string) {
    logOutput = pretty(await api(`/api/services/${encodeURIComponent(name)}/logs?lines=160`));
  }

  async function loadLog(source: string) {
    const result = await api<AnyRecord>(`/api/logs/${source}?lines=220`);
    logOutput = result.logs || pretty(result);
  }

  function filenameFromDisposition(disposition: string | null, fallback = 'yari-support-bundle.tar.gz') {
    const match = disposition?.match(/filename="?([^";]+)"?/i);
    return match?.[1] || fallback;
  }

  async function downloadBlob(endpoint: string, fallbackName: string, messagePrefix: string) {
    const response = await fetch(endpoint, { headers: authHeaders() });
    if (!response.ok) {
      const errorText = await response.text();
      setAction({ ok: false, error: errorText || response.statusText });
      return;
    }
    const blob = await response.blob();
    const filename = filenameFromDisposition(response.headers.get('content-disposition'), fallbackName);
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setAction({ ok: true, message: `${messagePrefix} ${filename}` });
  }

  async function downloadSupportBundle() {
    const endpoint = logsStatus?.support_bundle_endpoint || '/api/logs/support-bundle';
    await downloadBlob(endpoint, 'yari-support-bundle.tar.gz', 'Downloaded');
  }

  async function downloadConfigExport() {
    await downloadBlob('/api/config/export', 'yari-config-export.json', 'Downloaded');
  }

  function selectConfigImportFile(event: Event) {
    const input = event.target as HTMLInputElement;
    configImportFile = input.files?.[0] || null;
  }

  async function validateConfigImport() {
    if (!configImportFile) {
      configImportPreview = { ok: false, error: 'Choose a YARI config export JSON file first.' };
      return;
    }
    try {
      const text = await configImportFile.text();
      const parsed = JSON.parse(text);
      configImportPreview = await post('/api/config/import/validate', { export: parsed });
    } catch (err) {
      configImportPreview = { ok: false, error: err instanceof Error ? err.message : String(err) };
    }
  }

  async function reboot() {
    if (!confirm('Reboot this device now?')) return;
    setAction(await post('/api/reboot'));
  }

  async function shutdown() {
    if (!confirm('Shut down this device now? Physical access may be required to power it back on.')) return;
    setAction(await post('/api/shutdown'));
  }

  async function regenerateDeviceId() {
    setAction(await post('/api/device/regenerate-id'));
    await refreshDevice();
  }

  async function saveDeviceProfile() {
    setAction(await post('/api/device/profile', deviceProfileForm));
    await refreshDevice();
  }

  async function factoryResetNetwork() {
    if (!confirm('Factory reset saved network configuration?')) return;
    setAction(await post('/api/network/factory-reset', { reboot: false }));
    await refreshNetwork();
    await refreshDevice();
  }

  async function factoryResetNetworkAndReboot() {
    if (!confirm('Clear saved Wi-Fi and reboot into setup AP recovery mode?')) return;
    setAction(await post('/api/network/factory-reset', { reboot: true }));
  }

  async function saveMavlink() {
    try {
      setAction(await post('/api/mavlink/endpoints', JSON.parse(mavlinkConfigText)));
      await refreshAutopilot();
    } catch (err) {
      setAction({ ok: false, error: err instanceof Error ? err.message : String(err) });
    }
  }

  async function startRosProfile() {
    setAction(await post('/api/ros/launch-profile', { action: 'start', profile: selectedRosProfile }));
    await refreshRos();
  }

  async function stopRosProfile() {
    if (!confirm('Stop the active ROS launch profile?')) return;
    setAction(await post('/api/ros/launch-profile', { action: 'stop' }));
    await refreshRos();
  }

  async function startRosRecording() {
    const topics = rosRecordForm.topics.split(/\s+/).filter(Boolean);
    setAction(await post('/api/ros/recording/start', { name: rosRecordForm.name, topics }));
    await refreshRos();
  }

  async function stopRosRecording() {
    setAction(await post('/api/ros/recording/stop'));
    await refreshRos();
  }

  function clearPreviewUrl() {
    if (previewUrl.startsWith('blob:')) URL.revokeObjectURL(previewUrl);
    previewUrl = '';
  }

  async function refreshPreview() {
    previewState = 'Refreshing preview...';
    clearPreviewUrl();
    try {
      const response = await fetch(`/api/video/snapshot?ts=${Date.now()}`, { headers: authHeaders() });
      if (!response.ok) throw new Error(await response.text() || response.statusText);
      previewUrl = URL.createObjectURL(await response.blob());
      previewState = 'Preview updated.';
    } catch (err) {
      previewState = `Preview unavailable. ${err instanceof Error ? err.message : String(err)}`;
    }
  }

  async function saveVideoSettings() {
    setAction(await post('/api/video/settings', videoForm));
    await refreshVideo();
  }

  async function queueFlightLogDownload() {
    setAction(await post('/api/data/flight-logs/download', flightLogForm));
    await refreshData();
  }

  async function dataAction(path: string, body: AnyRecord = {}) {
    setAction(await post(path, body));
    await refreshData();
  }


  async function deleteListedLogs() {
    if (!confirm('Delete the logs listed by the cleanup preview? This cannot be undone.')) return;
    await dataAction('/api/data/cleanup', { confirm: true });
  }

  async function saveOtaConfig() {
    setAction(await post('/api/ota/config', otaConfigForm));
    await refreshOta();
  }

  async function installOtaArtifact() {
    setAction(await post('/api/ota/install', otaForm));
    otaForm.confirm = false;
    await refreshOta();
  }

  async function appAction(appId: string, action: string) {
    appOutput = await post(`/api/apps/${encodeURIComponent(appId)}/${action}`);
    await refreshApps();
  }

  async function appLogs(appId: string) {
    appOutput = await api(`/api/apps/${encodeURIComponent(appId)}/logs?lines=160`);
  }

  async function installAppManifest() {
    try {
      appOutput = await post('/api/apps/install', { manifest: JSON.parse(appManifestText), replace: true });
      await refreshApps();
    } catch (err) {
      appOutput = { ok: false, error: err instanceof Error ? err.message : String(err) };
    }
  }

  async function validateAppManifest() {
    try {
      appOutput = await post('/api/apps/validate', { manifest: JSON.parse(appManifestText), replace: true });
    } catch (err) {
      appOutput = { ok: false, error: err instanceof Error ? err.message : String(err) };
    }
  }

  async function uninstallApp(appId: string) {
    if (!confirm(`Uninstall app manifest ${appId}? Services and containers are not removed.`)) return;
    appOutput = await post(`/api/apps/${encodeURIComponent(appId)}/uninstall`);
    await refreshApps();
  }

  async function updateInstalledApp(appId: string) {
    appOutput = await post(`/api/apps/${encodeURIComponent(appId)}/update`);
    await refreshApps();
  }

  async function installRegistryApp(appId: string) {
    appOutput = await post(`/api/apps/registry/${encodeURIComponent(appId)}/install`, { replace: true });
    await refreshApps();
  }

  async function installAppPackage(name: string) {
    appOutput = await post(`/api/apps/packages/${encodeURIComponent(name)}/install`, { replace: true });
    await refreshApps();
  }

  async function deleteAppPackage(name: string) {
    if (!confirm(`Remove local package ${name}? Installed app manifests are not removed.`)) return;
    appOutput = await post(`/api/apps/packages/${encodeURIComponent(name)}/delete`);
    await refreshApps();
  }

  async function uploadAppPackage() {
    if (!appPackageFile) {
      appOutput = { ok: false, error: 'Select a .yariapp package first.' };
      return;
    }
    try {
      const content = arrayBufferToBase64(await appPackageFile.arrayBuffer());
      appOutput = await post('/api/apps/packages/upload', {
        name: appPackageFile.name,
        content_base64: content,
        replace: appPackageReplace,
      });
      appPackageFile = null;
      await refreshApps();
    } catch (err) {
      appOutput = { ok: false, error: err instanceof Error ? err.message : String(err) };
    }
  }

  onDestroy(clearPreviewUrl);

  onMount(() => {
    const saved = localStorage.getItem('yari-theme');
    apiToken = localStorage.getItem('yari-api-token') || '';
    const hashTab = tabFromHash();
    if (hashTab) activeTab = hashTab;
    setTheme(saved || (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'));
    const onHashChange = () => {
      const nextTab = tabFromHash();
      if (nextTab) selectTab(nextTab, false);
    };
    addEventListener('hashchange', onHashChange);
    refreshAll();
    return () => removeEventListener('hashchange', onHashChange);
  });
</script>

<svelte:head>
  <title>YARI OS Device Portal</title>
</svelte:head>

<header class="topbar">
  <div class="brand">
    <strong>YARI OS</strong>
    <div>
      <h1>Device Portal</h1>
      <p>Local setup, diagnostics, and companion-computer controls</p>
      <div class="pills">
        <span>{device?.hostname || 'device'}</span>
        <span class:ok={Boolean(device?.ip_addresses?.length)}>{device?.ip_addresses?.join(' ') || 'no IP'}</span>
        <span>{device?.onboarding?.mode || 'unknown'}</span>
      </div>
    </div>
  </div>
  <div class="actions">
    {#if portalVersion?.api_token_required}
      <input class="token-input" type="password" value={apiToken} placeholder="API token" aria-label="YARI portal API token" on:input={(event) => setApiToken(event.currentTarget.value)} />
    {/if}
    <div class="segmented" aria-label="Theme">
      <button class:active={theme === 'light'} on:click={() => setTheme('light')}>Light</button>
      <button class:active={theme === 'dark'} on:click={() => setTheme('dark')}>Dark</button>
    </div>
    <button class="secondary" on:click={refreshAll}>Refresh</button>
  </div>
</header>

<main>
  {#if error}<div class="alert">{error}</div>{/if}
  {#if loading}<div class="notice">Refreshing device state...</div>{/if}

  <nav class="tabs" aria-label="Portal sections">
    {#each tabs as tab}
      <button class:active={activeTab === tab.id} on:click={() => selectTab(tab.id)}>{tab.label}</button>
    {/each}
  </nav>

  {#if activeTab === 'setup'}
    <section class="grid">
      <div class="section-block wide">
        <div class="section-heading">
          <div>
            <h2>First-Run Setup</h2>
            <p>Connect this device to Wi-Fi, name it, configure SSH access, and pair it with Atlas or Foxglove.</p>
          </div>
          <button class="secondary" on:click={refreshAll}>Refresh setup</button>
        </div>
        <div class="readiness-grid">
          {#each setupItems() as item}
            <button class={`readiness-card ${item.state}`} type="button">
              <small>{item.label}</small>
              <strong>{item.state === 'ok' ? 'Ready' : item.state === 'bad' ? 'Error' : 'Check'}</strong>
              <span>{item.detail}</span>
            </button>
          {/each}
        </div>
      </div>

      <div class="card wide">
        <h2>Wi-Fi Network</h2>
        <div class="row"><button class="secondary" on:click={scanWifi}>Scan networks</button></div>
        {#if wifiNetworks().length > 0}
          <table>
            <thead><tr><th>SSID</th><th>Signal</th><th>Security</th><th>Channel</th><th></th></tr></thead>
            <tbody>
              {#each wifiNetworks() as network}
                <tr>
                  <td>{network.ssid || network.name}</td>
                  <td>{network.signal || network.strength || 'unknown'}</td>
                  <td>{wifiSecurityLabel(network)}</td>
                  <td>{network.channel || network.chan || ''}</td>
                  <td><button class="secondary" on:click={() => useWifiNetwork(network.ssid || network.name)}>Use</button></td>
                </tr>
              {/each}
            </tbody>
          </table>
        {:else}
          <div class="empty-state">Scan to list nearby Wi-Fi networks.</div>
        {/if}
      </div>

      <div class="card wide">
        <h2>Device Identity</h2>
        <form on:submit|preventDefault={saveSetup}>
          <label>Wi-Fi SSID<input bind:value={setupForm.ssid} placeholder="Network name" /></label>
          <label>Wi-Fi password<input type="password" bind:value={setupForm.password} placeholder="Leave blank only for open networks" /></label>
          <label>Hostname<input bind:value={setupForm.hostname} placeholder="yari-device" /></label>
          <button type="submit">Save setup</button>
        </form>
      </div>

      <div class="card wide">
        <h2>Device Role</h2>
        <div class="preset-grid">
          {#each profilePresets as preset}
            <button class:active={deviceProfileForm.profile_preset === preset.id} class="preset-card secondary" type="button" on:click={() => applyProfilePreset(preset)}>
              <strong>{preset.label}</strong>
              <small>{preset.description}</small>
            </button>
          {/each}
        </div>
        <form on:submit|preventDefault={saveSetup}>
          <label>Profile preset<select bind:value={deviceProfileForm.profile_preset} on:change={refreshProfileRecommendations}>{#each profilePresets as preset}<option value={preset.id}>{preset.label}</option>{/each}</select></label>
          <label>Vehicle class<select bind:value={deviceProfileForm.vehicle_class} on:change={refreshProfileRecommendations}><option value="ground_rover">Ground rover</option><option value="multirotor">Multirotor</option><option value="fixed_wing">Fixed wing</option><option value="vtol">VTOL</option><option value="boat">Boat</option><option value="sub">Sub</option><option value="generic_edge">Generic edge</option></select></label>
          <label>Autopilot stack<select bind:value={deviceProfileForm.autopilot_stack} on:change={refreshProfileRecommendations}><option value="none">None</option><option value="px4">PX4</option><option value="ardupilot">ArduPilot</option><option value="ros_only">ROS only</option><option value="custom">Custom</option></select></label>
          <label>Compute target<select bind:value={deviceProfileForm.compute_target} on:change={refreshProfileRecommendations}><option value="raspberry_pi">Raspberry Pi</option><option value="jetson_orin">Jetson Orin</option><option value="jetson_nano">Jetson Nano</option><option value="x86_ubuntu">x86 Ubuntu</option><option value="custom">Custom</option></select></label>
          <label>ROS domain ID<input bind:value={deviceProfileForm.ros_domain_id} type="number" min="0" max="232" on:change={refreshProfileRecommendations} /></label>
          <button type="submit">Save device role</button>
        </form>
        <div class="mini-section">
          <h3>Recommended apps</h3>
          <div class="app-grid compact-grid">
            {#each profileRecommendationItems() as item}
              {@const app = recommendationApp(item)}
              {@const registryApp = registryAppById(item.id)}
              <RecommendationCard
                {item}
                {app}
                {registryApp}
                statusLabel={recommendationStatus(item)}
                statusClass={recommendationStatusClass(item)}
                {registryActionLabel}
                onOpen={openUiPath}
                onInstall={installRegistryApp}
              />
            {/each}
          </div>
        </div>
      </div>

      <div class="card">
        <h2>SSH Access</h2>
        <form on:submit|preventDefault={saveSetup}>
          <label>SSH public key<textarea rows="5" bind:value={setupForm.ssh_key} placeholder="ssh-ed25519 AAAA..."></textarea></label>
          <label>SSH password<input type="password" bind:value={setupForm.ssh_password} placeholder="Optional fallback password" /></label>
          <button type="submit">Save SSH access</button>
        </form>
      </div>

      <div class="card">
        <h2>Cloud Pairing</h2>
        <form on:submit|preventDefault={saveSetup}>
          <label>Atlas URL<input bind:value={setupForm.atlas_url} placeholder="https://atlas.yari.io/api/v1" /></label>
          <label>Atlas upload URL<input bind:value={setupForm.atlas_upload_url} placeholder="Optional: https://atlas.yari.io/api/v1/logs/upload" /></label>
          <label>Atlas device token<input type="password" bind:value={setupForm.atlas_token} /></label>
          <label>Foxglove token<input type="password" bind:value={setupForm.foxglove_token} /></label>
          <button type="submit">Save pairing</button>
        </form>
      </div>

      <div class="card wide">
        <h2>Current State</h2>
        <pre>{pretty({ onboarding: device?.onboarding, setup: setupState, network: network?.config?.client_wifi })}</pre>
      </div>
      <div class="card wide"><h2>Last Result</h2><pre>{pretty(actionOutput)}</pre></div>
    </section>
  {:else if activeTab === 'status'}
    <section class="grid">
      <div class="section-block wide">
        <div class="section-heading">
          <div>
            <h2>Device Readiness</h2>
            <p>At-a-glance state for common operator checks after boot.</p>
          </div>
          <button class="secondary" on:click={refreshAll}>Refresh status</button>
        </div>
        <div class="readiness-grid">
          {#each readinessItems() as item}
            <button class={`readiness-card ${item.state}`} on:click={() => selectTab(item.tab)}>
              <span>{item.label}</span>
              <strong>{item.state}</strong>
              <small>{item.detail}</small>
            </button>
          {/each}
        </div>
      </div>
      <div class="card">
        <h2>Device Summary</h2>
        <dl class="meta-list">
          <div><dt>Hostname</dt><dd>{device?.hostname || 'unknown'}</dd></div>
          <div><dt>Address</dt><dd>{listText(device?.ip_addresses, 'no IP')}</dd></div>
          <div><dt>Mode</dt><dd>{device?.onboarding?.mode || 'unknown'}</dd></div>
          <div><dt>Kernel</dt><dd>{device?.kernel || device?.os?.kernel || 'unknown'}</dd></div>
          <div><dt>Portal</dt><dd>{portalVersion?.version || 'dev'} / {portalVersion?.git_commit || 'unknown'}</dd></div>
        </dl>
      </div>
      <div class="card">
        <h2>Portal Build</h2>
        <dl class="meta-list">
          <div><dt>Version</dt><dd>{portalVersion?.version || 'dev'}</dd></div>
          <div><dt>Commit</dt><dd>{portalVersion?.git_commit || 'unknown'}</dd></div>
          <div><dt>Stack</dt><dd>{portalVersion?.frontend_stack || 'svelte-typescript-vite-tailwind'}</dd></div>
          <div><dt>Built</dt><dd>{portalBuildTime()}</dd></div>
        </dl>
        <div class="summary-grid compact">
          {#each portalAssetSummaryItems() as item}
            <div><small>{item.label}</small><strong>{item.value}</strong></div>
          {/each}
        </div>
      </div>
      <div class="card">
        <h2>Device Profile</h2>
        <div class="preset-grid">
          {#each profilePresets as preset}
            <button class:active={deviceProfileForm.profile_preset === preset.id} class="preset-card secondary" type="button" on:click={() => applyProfilePreset(preset)}>
              <strong>{preset.label}</strong>
              <small>{preset.description}</small>
            </button>
          {/each}
        </div>
        <form on:submit|preventDefault={saveDeviceProfile}>
          <label>Profile preset<select bind:value={deviceProfileForm.profile_preset} on:change={refreshProfileRecommendations}>{#each profilePresets as preset}<option value={preset.id}>{preset.label}</option>{/each}</select></label>
          <label>Vehicle class<select bind:value={deviceProfileForm.vehicle_class} on:change={refreshProfileRecommendations}><option value="ground_rover">Ground rover</option><option value="multirotor">Multirotor</option><option value="fixed_wing">Fixed wing</option><option value="vtol">VTOL</option><option value="boat">Boat</option><option value="sub">Sub</option><option value="generic_edge">Generic edge</option></select></label>
          <label>Autopilot stack<select bind:value={deviceProfileForm.autopilot_stack} on:change={refreshProfileRecommendations}><option value="none">None</option><option value="px4">PX4</option><option value="ardupilot">ArduPilot</option><option value="ros_only">ROS only</option><option value="custom">Custom</option></select></label>
          <label>Compute target<select bind:value={deviceProfileForm.compute_target} on:change={refreshProfileRecommendations}><option value="raspberry_pi">Raspberry Pi</option><option value="jetson_orin">Jetson Orin</option><option value="jetson_nano">Jetson Nano</option><option value="x86_ubuntu">x86 Ubuntu</option><option value="custom">Custom</option></select></label>
          <label>ROS domain ID<input bind:value={deviceProfileForm.ros_domain_id} type="number" min="0" max="232" on:change={refreshProfileRecommendations} /></label>
          <label>Notes<textarea rows="4" bind:value={deviceProfileForm.notes}></textarea></label>
          <button type="submit">Save device profile</button>
        </form>
        <div class="mini-section">
          <h3>Recommended apps</h3>
          <div class="app-grid compact-grid">
            {#each profileRecommendationItems() as item}
              {@const app = recommendationApp(item)}
              {@const registryApp = registryAppById(item.id)}
              <RecommendationCard
                {item}
                {app}
                {registryApp}
                statusLabel={recommendationStatus(item)}
                statusClass={recommendationStatusClass(item)}
                {registryActionLabel}
                onOpen={openUiPath}
                onInstall={installRegistryApp}
              />
            {/each}
          </div>
        </div>
      </div>
      <div class="card wide"><h2>Raw Device Status</h2><pre>{pretty({ device, portal: portalVersion })}</pre></div>
    </section>
  {:else if activeTab === 'network'}
    <section class="grid">
      <div class="section-block wide">
        <div class="section-heading">
          <div>
            <h2>Network Overview</h2>
            <p>Client Wi-Fi, setup AP fallback, DNS, and route state.</p>
          </div>
          <div class="row">
            <button on:click={scanWifi}>Scan Wi-Fi</button>
            <button class="secondary" on:click={reconnectWifi}>Reconnect Wi-Fi</button>
          </div>
        </div>
        <div class="readiness-grid">
          {#each networkItems() as item}
            <div class={`readiness-card ${item.state}`}>
              <span>{item.label}</span>
              <strong>{item.state}</strong>
              <small>{item.detail}</small>
            </div>
          {/each}
        </div>
      </div>

      <div class="card">
        <h2>Network Controls</h2>
        <div class="row">
          <button on:click={scanWifi}>Scan Wi-Fi</button>
          <button class="secondary" on:click={enableAp}>Enable AP</button>
          <button class="secondary" on:click={reconnectWifi}>Reconnect Wi-Fi</button>
          <button class="danger" on:click={forgetWifi}>Forget Wi-Fi</button>
        </div>
      </div>

      <div class="card">
        <h2>Recovery Policy</h2>
        <form on:submit|preventDefault={saveNetworkPolicy}>
          <label><input bind:checked={networkPolicyForm.fallback_ap_enabled} type="checkbox" /> Enable fallback setup AP</label>
          <label>Fallback timeout seconds<input bind:value={networkPolicyForm.fallback_timeout_sec} type="number" min="5" max="600" /></label>
          <label><input bind:checked={networkPolicyForm.maintenance_ap_enabled} type="checkbox" /> Force maintenance AP on boot</label>
          <label><input bind:checked={networkPolicyForm.serve_portal_on_client_network} type="checkbox" /> Serve portal on client network</label>
          <button type="submit">Save recovery policy</button>
        </form>
      </div>

      <div class="card wide">
        <h2>Wi-Fi Networks</h2>
        {#if wifiNetworks().length > 0}
          <table>
            <thead><tr><th>SSID</th><th>Signal</th><th>Security</th><th>Channel</th><th>Action</th></tr></thead>
            <tbody>
              {#each wifiNetworks() as item}
                <tr>
                  <td><strong>{item.ssid}</strong><br /><small>{item.bssid}</small></td>
                  <td>{item.signal}</td>
                  <td>{item.security || 'open'}</td>
                  <td>{item.channel}</td>
                  <td><button class="secondary" on:click={() => useWifiNetwork(item.ssid)}>Use SSID</button></td>
                </tr>
              {/each}
            </tbody>
          </table>
        {:else}
          <p>Scan Wi-Fi to list nearby networks.</p>
        {/if}
      </div>

      <div class="card wide">
        <h2>Network Diagnostics</h2>
        <dl class="meta-list">
          <div><dt>Interface</dt><dd>{diagnostics?.wifi_iface || network?.wifi_iface || 'unknown'}</dd></div>
          <div><dt>Active</dt><dd>{listText((network?.active_connections || []).map((item: AnyRecord) => item.name || item.connection || item.device), 'none')}</dd></div>
          <div><dt>Recent clues</dt><dd>{listText(diagnostics?.networkmanager?.recent_clues, 'none')}</dd></div>
        </dl>
      </div>

      <div class="card wide"><h2>Raw Network Status</h2><pre>{pretty({ network, diagnostics, wifiScan })}</pre></div>
    </section>
  {:else if activeTab === 'services'}
    <section class="grid">
      <div class="section-block wide">
        <div class="section-heading">
          <div>
            <h2>YARI Services</h2>
            <p>Allowlisted system services and YARI manager heartbeats.</p>
          </div>
          <button class="secondary" on:click={refreshServices}>Refresh services</button>
        </div>
        <div class="summary-grid">
          <div><small>Total</small><strong>{serviceItems().length}</strong></div>
          <div><small>Active</small><strong>{serviceActiveCount()}</strong></div>
          <div><small>Inactive</small><strong>{Math.max(0, serviceItems().length - serviceActiveCount())}</strong></div>
        </div>
      </div>

      <div class="section-block wide">
        <div class="app-grid">
          {#each serviceItems() as service}
            <article class="app-card">
              <div class="app-card-title">
                <div>
                  <strong>{serviceLabel(service.name)}</strong>
                  <small>{service.unit}</small>
                </div>
                <span class={`status-pill ${serviceStateClass(service)}`}>{service.active || 'unknown'}</span>
              </div>
              <dl class="meta-list">
                <div><dt>Enabled</dt><dd>{service.enabled || 'unknown'}</dd></div>
                <div><dt>Available</dt><dd>{service.available === false ? 'no' : 'yes'}</dd></div>
                <div><dt>Manager</dt><dd>{serviceManagerDetail(service)}</dd></div>
              </dl>
              <div class="row compact">
                <button class="secondary" on:click={() => serviceAction(service.name, 'start')}>Start</button>
                <button class="secondary" on:click={() => serviceAction(service.name, 'stop')}>Stop</button>
                <button class="secondary" on:click={() => serviceAction(service.name, 'restart')}>Restart</button>
                <button class="secondary" on:click={() => serviceAction(service.name, 'enable')}>Enable</button>
                <button class="secondary" on:click={() => serviceAction(service.name, 'disable')}>Disable</button>
                <button class="secondary" on:click={() => serviceLogs(service.name)}>Logs</button>
              </div>
            </article>
          {/each}
        </div>
      </div>
    </section>
  {:else if activeTab === 'logs'}
    <section class="grid">
      <div class="section-block wide">
        <div class="section-heading">
          <div>
            <h2>Support Bundle</h2>
            <p>Collect device diagnostics for support without using SSH.</p>
          </div>
          <div class="row">
            <button class="secondary" on:click={refreshLogs}>Refresh sources</button>
            <button type="button" on:click={downloadSupportBundle}>Download bundle</button>
          </div>
        </div>
        <div class="summary-grid">
          <div><small>Format</small><strong>{logsStatus?.support_bundle?.format || 'tar.gz'}</strong></div>
          <div><small>Sources</small><strong>{logSourceEntries().length}</strong></div>
          <div><small>Redaction</small><strong>{logsStatus?.support_bundle?.redaction ? 'enabled' : 'unknown'}</strong></div>
        </div>
        <ul class="plain-list">
          {#each logsStatus?.support_bundle?.includes || [] as item}
            <li>{item}</li>
          {/each}
        </ul>
        {#if logsStatus?.support_bundle?.redaction}<p>{logsStatus.support_bundle.redaction}</p>{/if}
      </div>

      <div class="card wide">
        <h2>Log Sources</h2>
        <table>
          <thead><tr><th>Source</th><th>Kind</th><th>Details</th><th>Action</th></tr></thead>
          <tbody>
            {#each logSourceEntries() as [source, info]}
              <tr>
                <td><strong>{logSourceLabel(source)}</strong><br /><small>{source}</small></td>
                <td>{info.kind || 'unknown'}</td>
                <td>{info.service || listText(info.paths, 'device journal')}</td>
                <td><button class="secondary" on:click={() => loadLog(source)}>View logs</button></td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <div class="card wide"><h2>Output</h2><pre>{logOutput}</pre></div>
    </section>
  {:else if activeTab === 'maintenance'}
    <section class="grid">
      <div class="section-block wide">
        <div class="section-heading">
          <div>
            <h2>Maintenance and Updates</h2>
            <p>Manage device lifecycle actions, local OTA artifacts, and future Atlas-assigned Mender rollouts.</p>
          </div>
          <button class="secondary" on:click={refreshOta}>Refresh updates</button>
        </div>
        <div class="readiness-grid">
          {#each otaItems() as item}
            <button class={`readiness-card ${item.state}`} type="button">
              <small>{item.label}</small>
              <strong>{item.state === 'ok' ? 'Ready' : item.state === 'bad' ? 'Error' : 'Check'}</strong>
              <span>{item.detail}</span>
            </button>
          {/each}
        </div>
      </div>

      <div class="card wide">
        <h2>Device Actions</h2>
        <p>Export config downloads a redacted JSON snapshot for migration or support. Re-enter Wi-Fi passwords, SSH secrets, Atlas tokens, Foxglove tokens, and app secrets on restore.</p>
        <div class="row">
          <button class="secondary" on:click={reboot}>Reboot</button>
          <button class="secondary" on:click={regenerateDeviceId}>Regenerate device ID</button>
          <button class="secondary" on:click={downloadConfigExport}>Export config</button>
          <button class="danger" on:click={factoryResetNetwork}>Factory reset network</button>
          <button class="danger" on:click={factoryResetNetworkAndReboot}>Reset Wi-Fi and reboot to setup</button>
          <button class="danger" on:click={shutdown}>Shutdown</button>
        </div>
      </div>

      <div class="card wide">
        <h2>Config Import Dry Run</h2>
        <p>Validate a redacted YARI config export before migration. This does not apply settings or restore secrets.</p>
        <div class="row">
          <input accept="application/json,.json" type="file" on:change={selectConfigImportFile} />
          <button class="secondary" on:click={validateConfigImport}>Validate export</button>
        </div>
        {#if configImportPreview?.summary}
          <div class="summary-grid compact">
            <div><small>Sections</small><strong>{configImportPreview.summary.section_count}</strong></div>
            <div><small>Restorable now</small><strong>{configImportPreview.summary.restorable_now}</strong></div>
            <div><small>Future only</small><strong>{configImportPreview.summary.future_only}</strong></div>
            <div><small>Secrets needed</small><strong>{configImportPreview.summary.missing_secret_count}</strong></div>
          </div>
        {/if}
        {#if configImportPreview?.restore_plan?.length}
          <table>
            <thead><tr><th>Section</th><th>Status</th><th>Endpoint</th><th>Note</th></tr></thead>
            <tbody>
              {#each configImportPreview.restore_plan as item}
                <tr>
                  <td>{item.name}<br /><small>{item.source}</small></td>
                  <td><span class={`pill ${item.restore_supported ? 'ok' : 'warn'}`}>{item.restore_supported ? 'Ready' : 'Future'}</span></td>
                  <td><code>{item.apply_endpoint}</code></td>
                  <td>{item.note}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
        <pre>{pretty(configImportPreview)}</pre>
      </div>

      <div class="card wide">
        <h2>Local OTA Artifacts</h2>
        <p>{otaStatus?.artifact_dir || '/var/lib/yari/ota-artifacts'}</p>
        {#if otaArtifacts().length > 0}
          <table>
            <thead><tr><th>Artifact</th><th>Size</th><th>Modified</th><th></th></tr></thead>
            <tbody>
              {#each otaArtifacts() as artifact}
                <tr>
                  <td>{artifact.name || String(artifact.path || '').split('/').pop()}</td>
                  <td>{formatBytes(artifact.bytes)}</td>
                  <td>{formatTime(artifact.modified)}</td>
                  <td><button class="secondary" on:click={() => useOtaArtifact(artifact)}>Use</button></td>
                </tr>
              {/each}
            </tbody>
          </table>
        {:else}
          <div class="empty-state">No `.mender` or `.yarios` artifacts found in the local artifact directory.</div>
        {/if}
      </div>

      <div class="card">
        <h2>OTA Policy</h2>
        <form on:submit|preventDefault={saveOtaConfig}>
          <label>Release channel<select bind:value={otaConfigForm.release_channel}><option value="stable">Stable</option><option value="beta">Beta</option><option value="dev">Dev</option></select></label>
          <label><input bind:checked={otaConfigForm.auto_check} type="checkbox" /> Check for assigned updates</label>
          <label><input bind:checked={otaConfigForm.auto_download} type="checkbox" /> Auto-download assigned artifacts</label>
          <label><input bind:checked={otaConfigForm.auto_install} type="checkbox" /> Auto-install after download</label>
          <label><input bind:checked={otaConfigForm.require_signed_artifacts} type="checkbox" /> Require signed artifacts</label>
          <label>Atlas assignment URL<input bind:value={otaConfigForm.atlas_assignment_url} placeholder="https://atlas.yari.io/api/v1/updates/assignment" /></label>
          <button type="submit">Save OTA policy</button>
        </form>
      </div>

      <div class="card">
        <h2>Manual OTA Install</h2>
        <p>Manual install is for local validation. Atlas-managed signed rollouts are the production path.</p>
        <form on:submit|preventDefault={installOtaArtifact}>
          <label>Artifact file<input bind:value={otaForm.path} placeholder="update.mender" /></label>
          <label><input bind:checked={otaForm.confirm} type="checkbox" /> Confirm install and reboot requirement</label>
          <button type="submit" disabled={!otaStatus?.mender?.available || !otaForm.confirm}>Install artifact</button>
        </form>
      </div>

      <div class="card wide">
        <h2>MAVLink Endpoints</h2>
        <textarea rows="14" bind:value={mavlinkConfigText}></textarea>
        <div class="row"><button on:click={saveMavlink}>Save endpoints</button></div>
      </div>

      <div class="card wide"><h2>Last Result</h2><pre>{pretty(actionOutput)}</pre></div>
      <div class="card wide"><h2>Raw OTA Status</h2><pre>{pretty(otaStatus)}</pre></div>
    </section>
  {:else if activeTab === 'autopilot'}
    <section class="grid">
      <div class="section-block wide">
        <div class="section-heading">
          <div>
            <h2>PX4 / ArduPilot</h2>
            <p>Monitor autopilot heartbeat, MAVLink routing, serial devices, and flight-stack state for companion-computer deployments.</p>
          </div>
          <button class="secondary" on:click={refreshAutopilot}>Refresh autopilot</button>
        </div>
        <div class="readiness-grid">
          {#each autopilotItems() as item}
            <button class={`readiness-card ${item.state}`} type="button">
              <small>{item.label}</small>
              <strong>{item.state === 'ok' ? 'Ready' : item.state === 'bad' ? 'Error' : 'Check'}</strong>
              <span>{item.detail}</span>
            </button>
          {/each}
        </div>
      </div>

      <div class="card wide">
        <h2>Flight State</h2>
        <div class="summary-grid">
          <div><small>Stack</small><strong>{autopilot?.flight_stack || 'unknown'}</strong></div>
          <div><small>Mode</small><strong>{autopilot?.mode || 'unknown'}</strong></div>
          <div><small>Armed</small><strong>{autopilot?.armed === true ? 'yes' : autopilot?.armed === false ? 'no' : 'unknown'}</strong></div>
          <div><small>Heartbeat</small><strong>{autopilot?.heartbeat ? 'received' : 'none'}</strong></div>
        </div>
        <div class="summary-grid">
          <div><small>Battery</small><strong>{autopilot?.battery?.voltage_v ? `${autopilot.battery.voltage_v} V` : autopilot?.battery?.remaining ? `${autopilot.battery.remaining}%` : 'unknown'}</strong></div>
          <div><small>GPS</small><strong>{autopilot?.gps?.fix_type || autopilot?.gps?.state || 'unknown'}</strong></div>
          <div><small>Version</small><strong>{autopilot?.version?.flight_sw_version || autopilot?.version || 'unknown'}</strong></div>
          <div><small>Firmware UI</small><strong>{autopilot?.firmware_upload?.supported ? 'available' : 'planned'}</strong></div>
        </div>
        {#if autopilot?.firmware_upload?.message}<p>{autopilot.firmware_upload.message}</p>{/if}
      </div>

      <div class="card wide">
        <h2>MAVLink Endpoints</h2>
        {#if mavlinkEndpoints().length > 0}
          <table>
            <thead><tr><th>Name</th><th>Type</th><th>Target</th><th>Enabled</th></tr></thead>
            <tbody>
              {#each mavlinkEndpoints() as endpoint}
                <tr>
                  <td>{endpoint.name || 'endpoint'}</td>
                  <td>{endpoint.type}</td>
                  <td>{endpoint.type === 'serial' ? `${endpoint.device || 'device'} @ ${endpoint.baud || 57600}` : `${endpoint.host || '127.0.0.1'}:${endpoint.port || 14550}`}</td>
                  <td><span class={`pill ${endpoint.enabled ? 'ok' : 'warn'}`}>{endpoint.enabled ? 'enabled' : 'disabled'}</span></td>
                </tr>
              {/each}
            </tbody>
          </table>
        {:else}
          <div class="empty-state">No MAVLink endpoints configured.</div>
        {/if}
      </div>

      <div class="card">
        <h2>Serial Devices</h2>
        {#if serialDevices().length > 0}
          <table>
            <thead><tr><th>Device</th><th></th></tr></thead>
            <tbody>
              {#each serialDevices() as devicePath}
                <tr><td>{devicePath}</td><td><button class="secondary" on:click={() => useSerialDevice(devicePath)}>Use</button></td></tr>
              {/each}
            </tbody>
          </table>
        {:else}
          <div class="empty-state">No serial autopilot devices detected.</div>
        {/if}
      </div>

      <div class="card">
        <h2>Endpoint Config</h2>
        <form on:submit|preventDefault={saveMavlinkConfig}>
          <label>JSON<textarea rows="12" bind:value={mavlinkConfigText}></textarea></label>
          <button type="submit">Save MAVLink endpoints</button>
        </form>
      </div>

      <div class="card wide"><h2>Raw Autopilot Status</h2><pre>{pretty(autopilot)}</pre></div>
      <div class="card wide"><h2>Raw MAVLink Config</h2><pre>{pretty(mavlink)}</pre></div>
      <div class="card wide"><h2>Last Result</h2><pre>{pretty(actionOutput)}</pre></div>
    </section>
  {:else if activeTab === 'ros'}
    <section class="grid">
      <div class="section-block wide">
        <div class="section-heading">
          <div>
            <h2>ROS 2 Runtime</h2>
            <p>Operate ROS launch profiles, topic discovery, graph health, and MCAP recording without terminal commands.</p>
          </div>
          <button class="secondary" on:click={refreshRos}>Refresh ROS</button>
        </div>
        <div class="readiness-grid">
          {#each rosItems() as item}
            <button class={`readiness-card ${item.state}`} type="button">
              <small>{item.label}</small>
              <strong>{item.state === 'ok' ? 'Ready' : item.state === 'bad' ? 'Error' : 'Check'}</strong>
              <span>{item.detail}</span>
            </button>
          {/each}
        </div>
      </div>

      <div class="card wide">
        <h2>Launch Profiles</h2>
        {#if rosLaunchProfiles().length > 0}
          <div class="app-grid">
            {#each rosLaunchProfiles() as profile}
              <article class="app-card">
                <div class="app-card-title">
                  <div><strong>{profile.label || profile.name}</strong><br /><small>{profile.name}</small></div>
                  <span class={`pill ${profile.enabled === false ? 'warn' : 'ok'}`}>{profile.enabled === false ? 'disabled' : 'enabled'}</span>
                </div>
                <p>{profile.command || 'No command configured.'}</p>
                <small>{profile.cwd || 'default cwd'}</small>
                <div class="row">
                  <button on:click={() => { selectedRosProfile = profile.name; startRosProfile(); }} disabled={profile.enabled === false}>Start</button>
                  <button class="secondary" on:click={stopRosProfile}>Stop active</button>
                </div>
              </article>
            {/each}
          </div>
        {:else}
          <div class="empty-state">No ROS launch profiles configured.</div>
        {/if}
      </div>

      <div class="card wide">
        <h2>ROS Graph</h2>
        <div class="summary-grid">
          <div><small>Distro</small><strong>{ros?.ros_distro || 'unknown'}</strong></div>
          <div><small>Nodes</small><strong>{rosNodes().length || 0}</strong></div>
          <div><small>Topics</small><strong>{rosTopicItems().length}</strong></div>
          <div><small>Service</small><strong>{ros?.service?.active || 'unknown'}</strong></div>
        </div>
        {#if ros?.error}<pre>{ros.error}</pre>{/if}
      </div>

      <div class="card wide">
        <h2>Topics</h2>
        {#if rosTopicItems().length > 0}
          <table>
            <thead><tr><th>Topic</th><th>Type</th><th>Category</th><th></th></tr></thead>
            <tbody>
              {#each rosTopicItems() as topic}
                <tr>
                  <td>{topic.name || topic}</td>
                  <td>{topic.type || 'unknown'}</td>
                  <td><span class={`pill ${topicTypeClass(topic.type)}`}>{topicTypeLabel(topic.type)}</span></td>
                  <td><button class="secondary" on:click={() => useTopicForRecording(topic.name || topic)}>Record</button></td>
                </tr>
              {/each}
            </tbody>
          </table>
        {:else}
          <div class="empty-state">No ROS topics discovered yet.</div>
        {/if}
      </div>

      <div class="card">
        <h2>MCAP Recording</h2>
        <div class="summary-grid">
          <div><small>Status</small><strong>{ros?.recording?.active ? 'recording' : 'stopped'}</strong></div>
          <div><small>PID</small><strong>{ros?.recording?.pid || 'none'}</strong></div>
        </div>
        {#if ros?.recording?.output_dir}<p>{ros.recording.output_dir}</p>{/if}
        <form on:submit|preventDefault={startRosRecording}>
          <label>Bag name<input bind:value={rosRecordForm.name} placeholder="yari_ros_YYYYMMDD_HHMMSS" /></label>
          <label>Topics<textarea rows="6" bind:value={rosRecordForm.topics} placeholder="Leave blank to record all topics"></textarea></label>
          <div class="row"><button type="submit">Start MCAP</button><button class="secondary" type="button" on:click={stopRosRecording}>Stop MCAP</button></div>
        </form>
      </div>

      <div class="card">
        <h2>Nodes</h2>
        {#if rosNodes().length > 0}
          <ul class="plain-list">{#each rosNodes() as node}<li>{node}</li>{/each}</ul>
        {:else}
          <div class="empty-state">No ROS nodes discovered yet.</div>
        {/if}
      </div>

      <div class="card wide"><h2>Raw ROS Status</h2><pre>{pretty(ros)}</pre></div>
      <div class="card wide"><h2>Raw Topic Status</h2><pre>{pretty(rosTopics)}</pre></div>
      <div class="card wide"><h2>Last Result</h2><pre>{pretty(actionOutput)}</pre></div>
    </section>
  {:else if activeTab === 'video'}
    <section class="grid">
      <div class="section-block wide">
        <div class="section-heading">
          <div>
            <h2>Video Pipeline</h2>
            <p>Operate camera preview, Foxglove compressed topics, Atlas WebRTC readiness, and RTSP streaming from one place.</p>
          </div>
          <button class="secondary" on:click={refreshVideo}>Refresh video</button>
        </div>
        <div class="readiness-grid">
          {#each videoItems() as item}
            <button class={`readiness-card ${item.state}`} type="button">
              <small>{item.label}</small>
              <strong>{item.state === 'ok' ? 'Ready' : item.state === 'bad' ? 'Error' : 'Check'}</strong>
              <span>{item.detail}</span>
            </button>
          {/each}
        </div>
      </div>

      <div class="card">
        <h2>Preview</h2>
        <div class="row"><button class="secondary" on:click={refreshPreview}>Refresh preview</button></div>
        {#if previewUrl}
          <img src={previewUrl} alt="Camera preview" />
        {:else}
          <div class="empty-state">No preview loaded yet.</div>
        {/if}
        <pre>{previewState}</pre>
      </div>

      <div class="card">
        <h2>Camera Devices</h2>
        {#if videoDevices().length > 0}
          <table>
            <thead><tr><th>Device</th><th>Driver</th><th>Card</th><th></th></tr></thead>
            <tbody>
              {#each videoDevices() as camera}
                <tr>
                  <td>{camera.path || camera.device || 'unknown'}</td>
                  <td>{camera.driver || camera.bus_info || 'unknown'}</td>
                  <td>{camera.card || camera.name || 'camera'}</td>
                  <td><button class="secondary" on:click={() => useVideoDevice(camera.path || camera.device)}>Use</button></td>
                </tr>
              {/each}
            </tbody>
          </table>
        {:else}
          <div class="empty-state">No camera devices reported by the video manager.</div>
        {/if}
      </div>

      <div class="card wide">
        <h2>Stream Targets</h2>
        {#if streamTargets().length > 0}
          <table>
            <thead><tr><th>Target</th><th>Status</th><th>Topic / URL</th><th>Details</th></tr></thead>
            <tbody>
              {#each streamTargets() as [name, target]}
                <tr>
                  <td>{name}</td>
                  <td><span class={`pill ${healthClass(target.state || target.status || target.health)}`}>{target.state || target.status || target.health || 'configured'}</span></td>
                  <td>{target.topic || target.url || target.endpoint || 'not configured'}</td>
                  <td>{target.message || target.encoding || target.transport || ''}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        {:else}
          <div class="empty-state">No stream target metadata available yet.</div>
        {/if}
      </div>

      <div class="card wide">
        <h2>Stream Settings</h2>
        <form on:submit|preventDefault={saveVideoSettings}>
          <label><input bind:checked={videoForm.stream_enabled} type="checkbox" /> Enable RTSP stream</label>
          <label>Camera device<input bind:value={videoForm.device} placeholder="/dev/video0" /></label>
          <label>RTSP URL<input bind:value={videoForm.rtsp_url} /></label>
          <label>Frame size<input bind:value={videoForm.size} placeholder="640x480" /></label>
          <label>FPS<input bind:value={videoForm.fps} type="number" min="1" max="60" /></label>
          <label>Encoding<select bind:value={videoForm.encoding}><option value="mjpeg">MJPEG</option><option value="h264">H.264</option><option value="h265">H.265</option><option value="bgr8">BGR8</option><option value="mono8">Mono8</option></select></label>
          <label>Bandwidth kbps<input bind:value={videoForm.bandwidth_kbps} type="number" min="64" placeholder="auto" /></label>
          <label>Foxglove compressed topic<input bind:value={videoForm.foxglove_topic} /></label>
          <label><input bind:checked={videoForm.atlas_webrtc_enabled} type="checkbox" /> Enable Atlas WebRTC readiness</label>
          <label>Atlas camera topic<input bind:value={videoForm.atlas_camera_topic} /></label>
          <label>Atlas max video FPS<input bind:value={videoForm.atlas_max_video_fps} type="number" min="1" max="60" /></label>
          <button type="submit">Save stream settings</button>
        </form>
      </div>

      <div class="card wide"><h2>Raw Video Status</h2><pre>{pretty(video)}</pre></div>
    </section>
  {:else if activeTab === 'data'}
    <section class="grid">
      <div class="section-block wide">
        <div class="section-heading">
          <div>
            <h2>Data and Logs</h2>
            <p>Manage MCAP recordings, Atlas upload queue, PX4/ArduPilot flight-log downloads, and storage cleanup.</p>
          </div>
          <button class="secondary" on:click={refreshData}>Refresh data</button>
        </div>
        <div class="readiness-grid">
          {#each dataItems() as item}
            <button class={`readiness-card ${item.state}`} type="button">
              <small>{item.label}</small>
              <strong>{item.state === 'ok' ? 'Ready' : item.state === 'bad' ? 'Error' : 'Check'}</strong>
              <span>{item.detail}</span>
            </button>
          {/each}
        </div>
      </div>

      <div class="card wide">
        <h2>Recent MCAP Logs</h2>
        {#if mcapLogs().length > 0}
          <table>
            <thead><tr><th>File</th><th>Size</th><th>Modified</th></tr></thead>
            <tbody>
              {#each mcapLogs() as log}
                <tr>
                  <td>{log.name || String(log.path || '').split('/').pop() || log.path}</td>
                  <td>{formatBytes(log.bytes)}</td>
                  <td>{formatTime(log.modified)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        {:else}
          <div class="empty-state">No MCAP files found in {dataStatus?.mcap_dir || 'the configured log directory'}.</div>
        {/if}
      </div>

      <div class="card wide">
        <h2>Upload Queue</h2>
        <div class="row">
          <button on:click={() => dataAction('/api/data/uploads/enqueue')}>Queue uploads</button>
          <button class="secondary" on:click={() => dataAction('/api/data/uploads/retry')}>Retry queue</button>
          <button class="secondary" on:click={() => dataAction('/api/data/uploads/clear', { keep_failed: true })}>Clear completed</button>
        </div>
        {#if uploadQueue().length > 0}
          <table>
            <thead><tr><th>Item</th><th>Status</th><th>Size</th><th>Updated</th></tr></thead>
            <tbody>
              {#each uploadQueue() as item}
                <tr>
                  <td>{item.name || String(item.path || '').split('/').pop() || item.path || item.id}</td>
                  <td><span class={`pill ${healthClass(item.state || item.status)}`}>{item.state || item.status || 'queued'}</span></td>
                  <td>{formatBytes(item.bytes || item.size)}</td>
                  <td>{formatTime(item.updated || item.modified)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        {:else}
          <div class="empty-state">Upload queue is empty.</div>
        {/if}
      </div>

      <div class="card">
        <h2>Flight Log Download</h2>
        <form on:submit|preventDefault={queueFlightLogDownload}>
          <label>Autopilot log ID<input bind:value={flightLogForm.log_id} type="number" min="0" placeholder="0" /></label>
          <label>Endpoint name<input bind:value={flightLogForm.endpoint_name} placeholder="optional" /></label>
          <div class="row"><button type="submit">Queue download</button><button class="secondary" type="button" on:click={() => dataAction('/api/data/flight-logs/retry')}>Retry downloads</button></div>
        </form>
      </div>

      <div class="card">
        <h2>Storage Cleanup</h2>
        <p>{dataStatus?.storage_cleanup?.message || 'Preview cleanup before deleting logs.'}</p>
        <div class="row">
          <button class="secondary" on:click={() => dataAction('/api/data/cleanup', { confirm: false })}>Preview cleanup</button>
          <button class="danger" on:click={deleteListedLogs}>Delete listed logs</button>
        </div>
      </div>

      <div class="card wide">
        <h2>Remote Autopilot Logs</h2>
        {#if remoteFlightLogs().length > 0}
          <table>
            <thead><tr><th>ID</th><th>Date</th><th>Size</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {#each remoteFlightLogs() as log}
                <tr>
                  <td>{log.id ?? log.num ?? log.log_id}</td>
                  <td>{formatTime(log.time_utc || log.modified || log.timestamp)}</td>
                  <td>{formatBytes(log.size || log.bytes)}</td>
                  <td>{log.status || log.state || 'available'}</td>
                  <td><button class="secondary" on:click={() => queueRemoteFlightLog(log)}>Use</button></td>
                </tr>
              {/each}
            </tbody>
          </table>
        {:else}
          <div class="empty-state">{dataStatus?.remote_flight_logs?.message || dataStatus?.remote_flight_logs?.state || 'No remote flight logs reported yet.'}</div>
        {/if}
      </div>

      <div class="card wide">
        <h2>Flight Log Downloads</h2>
        {#if flightLogDownloads().length > 0}
          <table>
            <thead><tr><th>Log ID</th><th>Endpoint</th><th>Status</th><th>Output</th></tr></thead>
            <tbody>
              {#each flightLogDownloads() as item}
                <tr>
                  <td>{item.log_id || item.id}</td>
                  <td>{item.endpoint_name || 'default'}</td>
                  <td><span class={`pill ${healthClass(item.state || item.status)}`}>{item.state || item.status || 'queued'}</span></td>
                  <td>{item.path || item.message || ''}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        {:else}
          <div class="empty-state">No flight-log download requests yet.</div>
        {/if}
      </div>

      <div class="card wide"><h2>Last Result</h2><pre>{pretty(actionOutput)}</pre></div>
      <div class="card wide"><h2>Raw Data Status</h2><pre>{pretty(dataStatus)}</pre></div>
    </section>
  {:else if activeTab === 'apps'}
    <section class="grid">
      <div class="section-block wide">
        <div class="section-heading">
          <div>
            <h2>App Runtime</h2>
            <p>Install and operate YARI core services, service bundles, and container apps from a local manifest registry.</p>
          </div>
          <button class="secondary" on:click={refreshApps}>Refresh apps</button>
        </div>
        <div class="summary-grid">
          <div><small>Profile</small><strong>{apps?.device_profile?.vehicle_class || 'not set'}</strong></div>
          <div><small>Autopilot</small><strong>{apps?.device_profile?.autopilot_stack || 'none'}</strong></div>
          <div><small>Runtime</small><strong>{apps?.container_runtime?.available ? apps?.container_runtime?.name : 'service-only'}</strong></div>
          <div><small>Manifests</small><strong>{apps?.apps?.length || 0}</strong></div>
        </div>
      </div>

      <div class="section-block wide">
        <h2>Recommended For This Device</h2>
        <div class="app-grid">
          {#each apps?.recommendations || [] as item}
            {@const app = recommendationApp(item)}
            {@const registryApp = registryAppById(item.id)}
            <article class="app-card">
              <div class="app-card-title">
                <div>
                  <strong>{app.name || item.name || item.id}</strong>
                  <small>{item.id} / {app.runtime ? runtimeLabel(app) : 'profile recommendation'}</small>
                </div>
                <span class={`status-pill ${recommendationStatusClass(item)}`}>{recommendationStatus(item)}</span>
              </div>
              <p>{recommendationSummary({ ...app, ...item })}</p>
              <dl class="meta-list">
                <div><dt>Reason</dt><dd>{item.reason || 'Recommended for this device profile.'}</dd></div>
                <div><dt>Readiness</dt><dd>{app.readiness?.message || registryApp?.readiness?.message || 'Ready to evaluate'}</dd></div>
                <div><dt>Source</dt><dd>{app.source === 'builtin' ? 'Base image' : registryApp ? 'Local registry' : app.source || 'Profile'}</dd></div>
              </dl>
              <div class="row compact">
                {#if app.ui?.path}<button class="secondary" on:click={() => openUiPath(app.ui.path)}>Open UI</button>{/if}
                {#if registryApp && !app.installed}<button class="secondary" disabled={!registryApp.actions?.apply} title={registryApp.actions?.reason || ''} on:click={() => installRegistryApp(registryApp.id)}>{registryActionLabel(registryApp)}</button>{/if}
                {#if registryApp && app.installed && registryApp.actions?.update}<button class="secondary" on:click={() => installRegistryApp(registryApp.id)}>Apply update</button>{/if}
              </div>
            </article>
          {/each}
        </div>
      </div>

      <div class="section-block wide">
        <h2>Installed Apps</h2>
        <div class="app-grid">
          {#each apps?.apps || [] as app}
            <article class="app-card">
              <div class="app-card-title">
                <div>
                  <strong>{app.name}</strong>
                  <small>{app.id} / {app.version}</small>
                </div>
                <span class={`status-pill ${healthClass(app.health)}`}>{app.health || 'unknown'}</span>
              </div>
              {#if app.update?.update_available}
                <p class="inline-note">Update available: {app.version} -> {app.update.registry_version}</p>
              {/if}
              <p>{app.description || 'No description provided.'}</p>
              <dl class="meta-list">
                <div><dt>Runtime</dt><dd>{runtimeLabel(app)}</dd></div>
                <div><dt>Readiness</dt><dd>{app.readiness?.message || 'unknown'}</dd></div>
                <div><dt>Healthcheck</dt><dd>{app.healthcheck_status?.state || 'not configured'}</dd></div>
                <div><dt>Services</dt><dd>{listText(app.services)}</dd></div>
                <div><dt>Ports</dt><dd>{listText((app.ports || []).map(formatPort))}</dd></div>
                <div><dt>Permission risk</dt><dd><span class={`status-pill ${permissionRiskClass(app)}`}>{permissionRiskLabel(app)}</span></dd></div>
                <div><dt>Permissions</dt><dd>{listText(app.permissions)}</dd></div>
                <div><dt>Review</dt><dd>{permissionReviewText(app)}</dd></div>
                {#if app.container_status?.active}
                  <div><dt>Container</dt><dd>{app.container_status.active}</dd></div>
                {/if}
              </dl>
              <div class="row compact">
                {#if app.ui?.path}<button class="secondary" on:click={() => openUiPath(app.ui.path)}>Open UI</button>{/if}
                <button class="secondary" disabled={!app.actions?.start} on:click={() => appAction(app.id, 'start')}>Start</button>
                <button class="secondary" disabled={!app.actions?.stop} on:click={() => appAction(app.id, 'stop')}>Stop</button>
                <button class="secondary" disabled={!app.actions?.restart} on:click={() => appAction(app.id, 'restart')}>Restart</button>
                <button class="secondary" disabled={!app.actions?.logs} on:click={() => appLogs(app.id)}>Logs</button>
                {#if app.update?.update_available}<button class="secondary" disabled={!app.actions?.update} on:click={() => updateInstalledApp(app.id)}>Apply update</button>{/if}
                <button class="secondary" disabled={!app.actions?.uninstall} on:click={() => uninstallApp(app.id)}>Uninstall</button>
              </div>
            </article>
          {/each}
        </div>
      </div>

      <div class="section-block wide">
        <h2>Local Registry</h2>
        <div class="app-grid">
          {#each appRegistry?.apps || [] as app}
            <article class="app-card">
              <div class="app-card-title">
                <div>
                  <strong>{app.name}</strong>
                  <small>{app.id} / {app.version}</small>
                </div>
                <span class:ok={app.installed && !app.update?.update_available} class:warn={app.update?.update_available} class="status-pill">{app.update?.update_available ? 'Update available' : app.installed ? 'Installed' : 'Available'}</span>
              </div>
              {#if app.installed}
                <p class="inline-note">Installed {app.installed_version || 'unknown'} / Registry {app.version}</p>
              {/if}
              <p>{app.description || 'Local manifest available on this device.'}</p>
              <dl class="meta-list">
                <div><dt>Runtime</dt><dd>{runtimeLabel(app)}</dd></div>
                <div><dt>Readiness</dt><dd>{app.readiness?.message || 'unknown'}</dd></div>
                <div><dt>Services</dt><dd>{listText(app.services)}</dd></div>
                <div><dt>Permission risk</dt><dd><span class={`status-pill ${permissionRiskClass(app)}`}>{permissionRiskLabel(app)}</span></dd></div>
                <div><dt>Permissions</dt><dd>{listText(app.permissions)}</dd></div>
                <div><dt>Review</dt><dd>{permissionReviewText(app)}</dd></div>
              </dl>
              <div class="row compact">
                {#if app.ui?.path}<button class="secondary" on:click={() => openUiPath(app.ui.path)}>Open UI</button>{/if}
                <button class="secondary" disabled={!app.actions?.apply} title={app.actions?.reason || ''} on:click={() => installRegistryApp(app.id)}>{registryActionLabel(app)}</button>
              </div>
            </article>
          {/each}
        </div>
        <pre>{pretty({ registry_dir: appRegistry?.registry_dir, errors: appRegistry?.errors })}</pre>
      </div>

      <div class="section-block wide">
        <div class="section-heading">
          <div>
            <h2>Local Packages</h2>
            <p class="inline-note">{packageTrustSummary()}</p>
          </div>
          {#if appPackages?.signature_public_key_file}
            <span class="status-pill">Key: {appPackages.signature_public_key_file}</span>
          {/if}
        </div>
        <div class="package-upload">
          <label>Package file<input accept=".yariapp,.tar.gz,.tgz" type="file" on:change={(event) => { const input = event.currentTarget as HTMLInputElement; appPackageFile = input.files?.[0] || null; }} /></label>
          <label class="checkbox-line"><input bind:checked={appPackageReplace} type="checkbox" /> Replace existing package with the same name</label>
          <button class="secondary" disabled={!appPackageFile} on:click={uploadAppPackage}>Upload package</button>
          {#if appPackageFile}<span class="inline-note">{appPackageFile.name} / {formatBytes(appPackageFile.size)}</span>{/if}
        </div>
        <div class="app-grid">
          {#each appPackages?.packages || [] as pkg}
            {@const trust = packageTrust(pkg)}
            <article class="app-card">
              <div class="app-card-title">
                <div>
                  <strong>{pkg.app?.name || pkg.name}</strong>
                  <small>{pkg.name} / {formatBytes(pkg.bytes)}</small>
                </div>
                <span class:ok={pkg.installed && !pkg.update?.update_available} class:warn={pkg.update?.update_available} class="status-pill">{pkg.update?.update_available ? 'Package update' : pkg.installed ? 'Installed' : 'Package'}</span>
              </div>
              <div class="trust-row">
                <span class={`status-pill ${trust.className}`}>{trust.label}</span>
                <span>{trust.detail}</span>
              </div>
              {#if pkg.installed}
                <p class="inline-note">Installed {pkg.installed_version || 'unknown'} / Package {pkg.app?.version || 'unknown'}</p>
              {/if}
              <p>{pkg.app?.description || 'Installable local YARI app package.'}</p>
              <dl class="meta-list">
                <div><dt>Runtime</dt><dd>{runtimeLabel(pkg.app || {})}</dd></div>
                <div><dt>SHA-256</dt><dd>{pkg.sha256?.slice(0, 16)}...</dd></div>
                <div><dt>Manifest</dt><dd>{pkg.manifest_sha256?.slice(0, 16)}...</dd></div>
                <div><dt>Signature</dt><dd>{pkg.signature?.status || 'unknown'}</dd></div>
                <div><dt>Signer</dt><dd>{pkg.signature?.signed_by || 'unknown'}</dd></div>
                <div><dt>Algorithm</dt><dd>{pkg.signature?.signature_type || 'unknown'}</dd></div>
                <div><dt>Permission risk</dt><dd><span class={`status-pill ${permissionRiskClass(pkg.app)}`}>{permissionRiskLabel(pkg.app)}</span></dd></div>
                <div><dt>Permissions</dt><dd>{listText(pkg.app?.permissions)}</dd></div>
                <div><dt>Review</dt><dd>{permissionReviewText(pkg.app)}</dd></div>
              </dl>
              <div class="row compact">
                {#if pkg.app?.ui?.path}<button class="secondary" on:click={() => openUiPath(pkg.app.ui.path)}>Open UI</button>{/if}
                <button class="secondary" disabled={trust.className === 'bad' && appPackages?.signature_verification_required} on:click={() => installAppPackage(pkg.name)}>{pkg.update?.update_available ? 'Apply package' : pkg.installed ? 'Reinstall package' : 'Install package'}</button>
                <button class="secondary danger-text" on:click={() => deleteAppPackage(pkg.name)}>Remove package</button>
              </div>
            </article>
          {/each}
        </div>
        <pre>{pretty({ package_dir: appPackages?.package_dir, supported_extensions: appPackages?.supported_extensions, signature_required: appPackages?.signature_required, signature_verification_required: appPackages?.signature_verification_required, signature_public_key_file: appPackages?.signature_public_key_file, errors: appPackages?.errors })}</pre>
      </div>

      <div class="card"><h2>Install Manifest</h2><textarea bind:value={appManifestText} rows="14"></textarea><div class="row compact"><button class="secondary" on:click={validateAppManifest}>Validate manifest</button><button on:click={installAppManifest}>Install / update manifest</button></div></div>
      <div class="card"><h2>Manifest Directory</h2><pre>{pretty({ schema_version: apps?.schema_version, manifest_dir: apps?.manifest_dir, errors: apps?.errors })}</pre></div>
      <div class="card wide"><h2>App Output</h2><pre>{pretty(appOutput)}</pre></div>
    </section>
  {/if}
</main>

<footer>
  <span>{portalVersion?.frontend_stack || 'svelte-typescript-vite-tailwind'}</span>
  <span>{portalVersion?.git_commit || 'dev'}</span>
</footer>


