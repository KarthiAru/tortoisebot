export type AnyRecord = Record<string, any>;

export interface PortalAssetSummary extends AnyRecord {
  available?: boolean;
  optimized?: boolean;
  optimization_state?: string;
  optimization_message?: string;
  asset_count?: number;
  total_bytes?: number;
  gzip_asset_count?: number;
  gzip_total_bytes?: number;
  gzip_original_bytes?: number;
  gzip_savings_bytes?: number;
  gzip_savings_percent?: number;
  generated_at?: string;
}

export interface PortalVersion extends AnyRecord {
  name: string;
  version: string;
  build_time: string;
  git_commit: string;
  frontend_stack: string;
  assets?: PortalAssetSummary;
}

export interface DeviceStatus extends AnyRecord {
  hostname: string;
  ip_addresses: string[];
  onboarding?: AnyRecord;
  portal?: PortalVersion;
}

export interface NetworkStatus extends AnyRecord {
  connected: boolean;
  wifi_iface: string;
  networkmanager: boolean;
  active_connections: AnyRecord[];
  devices: AnyRecord[];
  config: AnyRecord;
}

export interface NetworkDiagnostics extends AnyRecord {
  ok: boolean;
  checks: AnyRecord;
  connectivity: boolean;
  networkmanager: AnyRecord;
}

export interface ServiceStatus extends AnyRecord {
  name: string;
  unit: string;
  active: string;
  enabled: string;
}

export interface ServiceList {
  services: ServiceStatus[];
}