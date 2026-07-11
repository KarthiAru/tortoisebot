#!/usr/bin/env python3
import base64
import gzip
import http.client
import importlib.machinery
import importlib.util
import json
import os
import tarfile
import tempfile
import threading
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "yari-onboarding"


def load_module():
    loader = importlib.machinery.SourceFileLoader("yari_onboarding", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class YariOnboardingTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.module.STATE_DIR = root / "state"
        self.module.STATE_FILE = self.module.STATE_DIR / "state.json"
        self.module.COMPLETE_FILE = self.module.STATE_DIR / "complete"
        self.module.NM_CONNECTION_DIR = root / "nm"
        self.module.NETPLAN_DIR = root / "netplan"
        self.module.MAVLINK_CONFIG_FILE = root / "mavlink.json"
        self.module.PORTAL_SECRETS_FILE = root / "secrets.json"
        self.module.PORTAL_CONFIG_FILE = root / "portal.json"
        self.module.STATIC_NETWORK_CONFIG_FILE = root / "static-network.json"
        self.module.NETWORK_POLICY_CONFIG_FILE = root / "network-policy.json"
        self.module.VIDEO_CONFIG_FILE = root / "video.json"
        self.module.ROS_RECORDING_CONFIG_FILE = root / "ros-recording.json"
        self.module.ROS_RECORDING_PID_FILE = root / "ros-record.pid"
        self.module.ROS_RECORDING_LOG_FILE = root / "ros-record.log"
        self.module.ROS_LAUNCH_CONFIG_FILE = root / "ros-launch-profiles.json"
        self.module.ROS_LAUNCH_PID_FILE = root / "ros-launch.pid"
        self.module.ROS_LAUNCH_LOG_FILE = root / "ros-launch.log"
        self.module.ROS_LAUNCH_STATE_FILE = root / "ros-launch.json"
        self.module.MCAP_DIR = root / "mcap"
        self.module.UPLOAD_QUEUE_FILE = root / "upload-queue.json"
        self.module.OTA_STATE_FILE = root / "ota-state.json"
        self.module.OTA_CONFIG_FILE = root / "ota.json"
        self.module.OTA_ARTIFACT_DIR = root / "ota-artifacts"
        self.module.FLIGHT_LOG_DOWNLOADS_FILE = root / "flight-log-downloads.json"
        self.module.DEVICE_ID_FILE = root / "device-id"
        self.module.SETUP_AP_CREDENTIAL_FILE = root / "setup-ap-credentials.json"
        self.module.HOSTNAME_FILE = root / "hostname"
        self.module.DEVICE_MODEL_PATHS = [root / "device-model"]
        self.module.SUPPORT_BUNDLE_DIR = root / "bundles"
        self.module.SERVICE_STATE_DIR = root / "services"
        self.module.APP_MANIFEST_DIR = root / "apps.d"
        self.module.APP_REGISTRY_DIR = root / "registry"
        self.module.APP_PACKAGE_DIR = root / "packages"
        self.module.APP_PACKAGE_PUBLIC_KEY_FILE = root / "app-package-public.pem"
        self.module.APP_REQUIRE_SIGNED_PACKAGES = False
        self.module.APP_REQUIRE_VERIFIED_PACKAGES = False
        self.module.WEB_DIR = root / "web"
        self.module.PORTAL_VERSION_FILE = self.module.WEB_DIR / "portal-version.json"
        self.module.PORTAL_ASSETS_FILE = self.module.WEB_DIR / "portal-assets.json"
        self.module.WEB_DIR.mkdir(parents=True, exist_ok=True)
        self.module.APPLY_NETWORK = False
        self.commands = []
        self.module.run = self.fake_run
        self.module.command_output = self.fake_command_output
        self.module.has_command = lambda name: name == "nmcli"
        self.module.os.chown = lambda path, uid, gid: None

    def fake_run(self, args, check=False, capture=True):
        self.commands.append(args)
        class Result:
            returncode = 0
            stdout = ""
            stderr = ""
        return Result()

    def fake_command_output(self, args, timeout=8):
        self.commands.append(args)
        command = " ".join(args)
        stdout = ""
        if args[:2] == ["lsblk", "-J"]:
            stdout = '{"blockdevices": []}'
        elif args[:3] == ["ip", "-j", "addr"]:
            stdout = "[]"
        elif args[:3] == ["ip", "route", "get"]:
            stdout = "1.1.1.1 via 192.168.0.1 dev wlan0"
        elif "nmcli -t -f DEVICE,TYPE,STATE,CONNECTION device status" in command:
            stdout = "wlan0:wifi:connected:yari-wifi"
        elif "nmcli -t -f NAME,UUID,TYPE,DEVICE connection show --active" in command:
            stdout = "yari-wifi:uuid:wifi:wlan0"
        elif "802-11-wireless.ssid" in command:
            stdout = "802-11-wireless.ssid:Brindavan\n802-11-wireless-security.key-mgmt:wpa-psk"
        elif "journalctl -u NetworkManager" in command:
            stdout = "device (wlan0): Activation: successful"
        return {"ok": True, "stdout": stdout, "stderr": "", "returncode": 0}

    def test_normalize_form_value_strips_accidental_wrapping_quotes(self):
        self.assertEqual(self.module.normalize_form_value('"Brindavan"'), "Brindavan")
        self.assertEqual(self.module.normalize_form_value("'secret'"), "secret")
        self.assertEqual(self.module.normalize_form_value('pa"ss'), 'pa"ss')

    def test_setup_ap_password_modes_are_sanitized_and_persistent(self):
        self.module.AP_PASSWORD = ""
        open_status = self.module.setup_ap_status()
        self.assertEqual(open_status["security"], "open")
        self.assertFalse(open_status["password_configured"])
        self.assertFalse(self.module.SETUP_AP_CREDENTIAL_FILE.exists())

        self.module.AP_PASSWORD = "staticpass123"
        static_status = self.module.setup_ap_status()
        self.assertEqual(static_status["security"], "wpa-psk")
        self.assertEqual(static_status["password_source"], "configured")
        self.assertEqual(static_status["credential_file"], "")
        self.assertEqual(self.module.setup_ap_password(), "staticpass123")
        self.assertFalse(self.module.SETUP_AP_CREDENTIAL_FILE.exists())

        self.module.AP_PASSWORD = "auto"
        generated = self.module.setup_ap_password()
        self.assertGreaterEqual(len(generated), 8)
        self.assertEqual(self.module.setup_ap_password(), generated)
        self.assertEqual(oct(self.module.SETUP_AP_CREDENTIAL_FILE.stat().st_mode & 0o777), "0o600")
        saved = json.loads(self.module.SETUP_AP_CREDENTIAL_FILE.read_text())
        self.assertEqual(saved["password"], generated)
        generated_status = self.module.setup_ap_status()
        self.assertEqual(generated_status["security"], "wpa-psk")
        self.assertEqual(generated_status["password_source"], "generated")
        self.assertEqual(generated_status["credential_file"], str(self.module.SETUP_AP_CREDENTIAL_FILE))
        self.assertNotIn("password", generated_status)

    def test_setup_ap_password_rejects_short_values(self):
        self.module.AP_PASSWORD = "short"
        with self.assertRaises(ValueError):
            self.module.setup_ap_password()

    def test_portal_version_includes_asset_summary(self):
        self.module.PORTAL_VERSION_FILE.write_text(json.dumps({
            "name": "yari-os-device-portal",
            "version": "0.1.0",
            "build_time": "2026-07-11T00:00:00Z",
            "git_commit": "abc1234",
            "frontend_stack": "svelte-typescript-vite-tailwind",
        }))
        self.module.PORTAL_ASSETS_FILE.write_text(json.dumps({
            "generated_at": "2026-07-11T00:00:01Z",
            "asset_count": 2,
            "total_bytes": 120,
            "assets": [
                {"path": "index.html", "bytes": 100, "sha256": "a", "gzip": False},
                {"path": "index.html.gz", "bytes": 20, "sha256": "b", "gzip": True},
            ],
        }))
        version = self.module.portal_version()
        self.assertEqual(version["version"], "0.1.0")
        self.assertEqual(version["assets"]["asset_count"], 2)
        self.assertEqual(version["assets"]["gzip_asset_count"], 1)
        self.assertEqual(version["assets"]["gzip_total_bytes"], 20)
        self.assertEqual(version["assets"]["gzip_original_bytes"], 100)
        self.assertEqual(version["assets"]["gzip_savings_bytes"], 80)
        self.assertEqual(version["assets"]["gzip_savings_percent"], 80.0)
        self.assertTrue(version["assets"]["available"])
        self.assertTrue(version["assets"]["optimized"])
        self.assertEqual(version["assets"]["optimization_state"], "optimized")
        self.assertEqual(version["assets"]["optimization_message"], "1 compressed assets, 80.0% saved")

    def test_config_export_redacts_secrets_and_includes_portable_state(self):
        self.module.PORTAL_CONFIG_FILE.write_text(json.dumps({
            "device_profile": {"vehicle_class": "ground_rover"},
            "atlas_url": "https://atlas.example/api/v1",
        }))
        self.module.PORTAL_SECRETS_FILE.write_text(json.dumps({
            "wifi_password": "super-secret-wifi",
            "atlas_token": "atlas-secret-token",
        }))
        self.module.VIDEO_CONFIG_FILE.write_text(json.dumps({"foxglove_token": "foxglove-secret"}))
        self.module.APP_MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
        (self.module.APP_MANIFEST_DIR / "test-app.json").write_text(json.dumps({
            "schema_version": "1",
            "id": "test-app",
            "name": "Test App",
            "version": "1.0.0",
            "runtime": "container",
            "services": ["yari-ros"],
            "permissions": ["network.client"],
            "container": {"image": "registry.example/test-app:1.0.0", "environment": {"API_TOKEN": "app-token-secret"}},
        }))

        export = self.module.config_export()
        encoded = json.dumps(export)

        self.assertEqual(export["kind"], "yari-device-config-export")
        self.assertIn("restore_note", export)
        self.assertEqual(export["config"]["device-portal-config.json"]["device_profile"]["vehicle_class"], "ground_rover")
        self.assertIn("test-app.json", export["apps"])
        self.assertNotIn("super-secret-wifi", encoded)
        self.assertNotIn("atlas-secret-token", encoded)
        self.assertNotIn("foxglove-secret", encoded)
        self.assertNotIn("app-token-secret", encoded)
        self.assertTrue(export["apps"]["test-app.json"]["container"]["environment"]["API_TOKEN"]["configured"])

    def test_config_import_validation_is_dry_run_and_reports_restore_gaps(self):
        export = {
            "schema_version": "1",
            "kind": "yari-device-config-export",
            "device_id": "device-a",
            "hostname": "yari-a",
            "generated_at": "2026-07-11T00:00:00Z",
            "redaction": "secrets redacted",
            "device": {"profile": {"vehicle_class": "ground_rover", "compute_target": "raspberry_pi"}},
            "config": {"network-policy.json": {"fallback_ap_enabled": True}},
            "apps": {"camera-streamer.json": {"schema_version": "1", "id": "camera-streamer", "name": "Camera Streamer", "version": "1.0.0", "runtime": "service-bundle", "services": ["yari-video"], "permissions": ["camera.read"]}},
            "restore_note": "redacted",
        }

        result = self.module.validate_config_import({"export": export})

        self.assertTrue(result["ok"])
        self.assertTrue(result["dry_run"])
        self.assertTrue(result["restore_supported"])
        self.assertEqual(result["source_device_id"], "device-a")
        self.assertIn("camera-streamer.json", result["apps"])
        self.assertIn("App secrets and environment tokens", result["missing_secrets"])
        self.assertIn("device_profile", [section["name"] for section in result["sections"]])
        self.assertEqual(result["summary"]["section_count"], 3)
        self.assertEqual(result["summary"]["restorable_now"], 3)
        self.assertEqual(result["summary"]["future_only"], 0)
        self.assertEqual(result["app_manifest_import"]["valid"][0]["app"]["id"], "camera-streamer")
        app_plan = next(section for section in result["restore_plan"] if section["name"] == "app_manifests")
        self.assertTrue(app_plan["restore_supported"])
        self.assertEqual(app_plan["apply_endpoint"], "/api/apps/install")

    def test_config_import_validation_rejects_wrong_kind(self):
        with self.assertRaises(ValueError):
            self.module.validate_config_import({"schema_version": "1", "kind": "not-yari"})
    def test_config_import_apply_requires_acknowledgement_and_supported_sections(self):
        export = {
            "schema_version": "1",
            "kind": "yari-device-config-export",
            "device_id": "device-a",
            "hostname": "yari-a",
            "redaction": "secrets redacted",
            "device": {"profile": {"profile_preset": "ros_ground_robot", "vehicle_class": "ground_rover", "autopilot_stack": "ros_only", "compute_target": "raspberry_pi", "ros_domain_id": 7}},
            "config": {
                "network-policy.json": {"fallback_ap_enabled": True, "fallback_timeout_sec": 60, "maintenance_ap_enabled": False, "serve_portal_on_client_network": True},
                "static-network.json": {"enabled": False, "connection_name": "yari-wifi", "address_cidr": "", "gateway": "", "dns": []},
                "mavlink-endpoints.json": {"endpoints": [{"name": "autopilot", "type": "serial", "device": "/dev/ttyACM0", "baud": 57600, "enabled": True}]},
                "ota-config.json": {"release_channel": "beta", "auto_check": True, "auto_download": False, "auto_install": False, "require_signed_artifacts": True, "atlas_assignment_url": "https://atlas.example/api/v1/updates/assignment"},
            },
            "apps": {"camera-streamer.json": {"schema_version": "1", "id": "camera-streamer", "name": "Camera Streamer", "version": "1.0.0", "runtime": "service-bundle", "services": ["yari-video"], "permissions": ["camera.read"]}},
        }

        with self.assertRaises(ValueError):
            self.module.apply_config_import({"export": export, "apply_sections": ["device_profile"]})
        result_apps = self.module.apply_config_import({"export": export, "apply_sections": ["app_manifests"], "acknowledge_apply": True})
        self.assertEqual(result_apps["results"]["app_manifests"]["installed"][0]["id"], "camera-streamer")
        self.assertTrue((self.module.APP_MANIFEST_DIR / "camera-streamer.json").exists())

        result = self.module.apply_config_import({
            "export": export,
            "apply_sections": ["device_profile", "network_policy", "static_network", "mavlink_endpoints", "ota_policy"],
            "acknowledge_apply": True,
        })

        self.assertTrue(result["ok"])
        self.assertEqual(result["source_device_id"], "device-a")
        self.assertEqual(result["applied"], ["device_profile", "network_policy", "static_network", "mavlink_endpoints", "ota_policy"])
        self.assertIn("App secrets and environment tokens", result["missing_secrets"])
        self.assertEqual(self.module.read_device_profile()["ros_domain_id"], 7)
        self.assertEqual(self.module.read_network_policy()["fallback_timeout_sec"], 60)
        self.assertFalse(self.module.read_static_ip_config()["enabled"])
        self.assertTrue(self.module.read_mavlink_endpoints()["endpoints"][0]["enabled"])
        self.assertEqual(self.module.read_ota_config()["release_channel"], "beta")
        self.assertTrue((self.module.APP_MANIFEST_DIR / "camera-streamer.json").exists())

    def test_config_import_app_manifest_restore_skips_builtins_and_rejects_invalid(self):
        export = {
            "schema_version": "1",
            "kind": "yari-device-config-export",
            "device_id": "device-a",
            "redaction": "secrets redacted",
            "apps": {
                "foxglove-bridge.json": {"schema_version": "1", "id": "foxglove-bridge", "source": "builtin"},
                "camera-streamer.json": {
                    "schema_version": "1",
                    "id": "camera-streamer",
                    "name": "Camera Streamer",
                    "version": "1.0.0",
                    "runtime": "container",
                    "container": {"image": "registry.yari.io/camera:1", "environment": {"ATLAS_TOKEN": {"configured": True}}},
                    "permissions": ["network.client"],
                },
            },
        }

        preview = self.module.validate_config_import(export)
        self.assertEqual(preview["summary"]["restorable_now"], 1)
        self.assertEqual(preview["app_manifest_import"]["valid"][0]["app"]["id"], "camera-streamer")
        self.assertIn("foxglove-bridge", [item["id"] for item in preview["app_manifest_import"]["skipped"]])

        result = self.module.apply_config_import({"export": export, "apply_sections": ["app_manifests"], "acknowledge_apply": True})
        self.assertEqual(result["results"]["app_manifests"]["installed"][0]["id"], "camera-streamer")
        restored = json.loads((self.module.APP_MANIFEST_DIR / "camera-streamer.json").read_text())
        self.assertNotIn("environment", restored["container"])

        export["apps"]["bad.json"] = {"schema_version": "1", "id": "bad app"}
        preview = self.module.validate_config_import(export)
        self.assertFalse(next(section for section in preview["sections"] if section["name"] == "app_manifests")["restore_supported"])
        self.assertTrue(preview["app_manifest_import"]["errors"])
        with self.assertRaises(ValueError):
            self.module.apply_config_import({"export": export, "apply_sections": ["app_manifests"], "acknowledge_apply": True})

    def test_config_export_includes_mavlink_endpoints_for_migration(self):
        self.module.write_mavlink_endpoints({"endpoints": [{"name": "udp", "type": "udp", "host": "0.0.0.0", "port": 14550, "enabled": True}]})
        export = self.module.config_export()
        self.assertIn("mavlink-endpoints.json", export["config"])
        self.assertEqual(export["config"]["mavlink-endpoints.json"]["endpoints"][0]["name"], "udp")

    def test_static_portal_serves_precompressed_assets_when_browser_accepts_gzip(self):
        body = b"console.log('yari-os');\n"
        asset = self.module.WEB_DIR / "assets" / "app.js"
        asset.parent.mkdir(parents=True, exist_ok=True)
        asset.write_bytes(body)
        asset.with_suffix(asset.suffix + ".gz").write_bytes(gzip.compress(body, compresslevel=9))

        server = self.module.ThreadingHTTPServer(("127.0.0.1", 0), self.module.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        self.addCleanup(conn.close)
        conn.request("GET", "/assets/app.js", headers={"Accept-Encoding": "gzip"})
        response = conn.getresponse()
        compressed = response.read()

        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("content-encoding"), "gzip")
        self.assertEqual(response.getheader("vary"), "Accept-Encoding")
        self.assertIn("javascript", response.getheader("content-type"))
        self.assertEqual(gzip.decompress(compressed), body)

        conn.request("GET", "/assets/app.js")
        response = conn.getresponse()
        raw = response.read()

        self.assertEqual(response.status, 200)
        self.assertIsNone(response.getheader("content-encoding"))
        self.assertEqual(raw, body)

    def test_nm_keyfile_value_escapes_semicolons_and_rejects_newlines(self):
        self.assertEqual(self.module.nm_keyfile_value("ab;c\\d"), "ab\\;c\\\\d")
        with self.assertRaises(ValueError):
            self.module.nm_keyfile_value("bad\nvalue")

    def test_write_networkmanager_wifi_writes_secret_keyfile(self):
        self.module.write_networkmanager_wifi("Brindavan", "pass;word")
        path = self.module.NM_CONNECTION_DIR / "yari-wifi.nmconnection"
        self.assertTrue(path.exists())
        content = path.read_text()
        self.assertIn("ssid=Brindavan", content)
        self.assertIn("psk=pass\\;word", content)
        self.assertEqual(oct(path.stat().st_mode & 0o777), "0o600")
        self.assertIn(["nmcli", "connection", "reload"], self.commands)

    def test_parse_kv_lines_handles_nmcli_escaped_colons(self):
        rows = self.module.parse_kv_lines("Brindavan:00\\:5F\\:67\\:DB\\:25\\:97:8:WPA2")
        self.assertEqual(rows[0], ["Brindavan", "00:5F:67:DB:25:97", "8", "WPA2"])


    def test_services_status_includes_manager_state(self):
        self.module.SERVICE_STATE_DIR.mkdir(parents=True, exist_ok=True)
        (self.module.SERVICE_STATE_DIR / "agent.json").write_text('{"role":"agent","remote_access":{"atlas":{"ready":true}},"updated":1}')
        status = self.module.services_status()
        agent = next(item for item in status["services"] if item["name"] == "yari-agent")
        self.assertTrue(agent["manager_state"]["available"])
        self.assertTrue(agent["manager_state"]["remote_access"]["atlas"]["ready"])

    def test_app_catalog_includes_builtin_core_apps_with_health(self):
        catalog = self.module.app_catalog()
        app_ids = {app["id"] for app in catalog["apps"]}
        self.assertEqual(catalog["schema_version"], "1")
        self.assertIn("ros2-manager", app_ids)
        ros_app = next(app for app in catalog["apps"] if app["id"] == "ros2-manager")
        self.assertEqual(ros_app["source"], "builtin")
        self.assertEqual(ros_app["schema_version"], "1")
        self.assertEqual(ros_app["runtime"], "core-service")
        self.assertEqual(ros_app["kind"], "core-service")
        self.assertTrue(ros_app["installed"])
        self.assertTrue(ros_app["actions"]["start"])
        self.assertIn("service_status", ros_app)
        self.assertIn("recommendations", catalog)
        self.assertIn("device_profile", catalog)

    def test_app_recommendation_preview_uses_unsaved_profile(self):
        preview = self.module.app_recommendation_preview({
            "profile_preset": "px4_companion",
            "vehicle_class": "multirotor",
            "autopilot_stack": "px4",
            "compute_target": "jetson_orin",
            "ros_domain_id": 3,
        })
        ids = {item["id"] for item in preview["recommendations"]}
        self.assertEqual(preview["device_profile"]["profile_preset"], "px4_companion")
        self.assertIn("mavlink-router", ids)
        self.assertIn("autopilot-log-downloader", ids)
        self.assertIn("video-manager", ids)
        self.assertTrue(all("installed" in item for item in preview["recommendations"]))
        self.assertTrue(all("action" in item for item in preview["recommendations"]))
        self.assertIn("kind", preview["recommendations"][0]["action"])

    def test_app_recommendation_actions_cover_open_install_and_missing(self):
        self.module.APP_REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
        (self.module.APP_REGISTRY_DIR / "autopilot-log-downloader.json").write_text(json.dumps({
            "schema_version": "1",
            "id": "autopilot-log-downloader",
            "name": "Autopilot Log Downloader",
            "version": "0.1.0",
            "runtime": "service-bundle",
            "services": ["yari-log-manager"],
            "permissions": ["logs.read", "storage.write"],
            "ui": {"path": "#data"},
        }))
        preview = self.module.app_recommendation_preview({
            "profile_preset": "px4_companion",
            "vehicle_class": "multirotor",
            "autopilot_stack": "px4",
            "compute_target": "jetson_orin",
            "ros_domain_id": 0,
        })
        by_id = {item["id"]: item for item in preview["recommendations"]}
        self.assertEqual(by_id["mavlink-router"]["action"]["kind"], "open")
        self.assertEqual(by_id["autopilot-log-downloader"]["action"]["kind"], "install")

        missing_preview = self.module.app_recommendation_preview({
            "profile_preset": "ros_ground_robot",
            "vehicle_class": "ground_rover",
            "autopilot_stack": "ros_only",
            "compute_target": "raspberry_pi",
            "ros_domain_id": 0,
        })
        missing_by_id = {item["id"]: item for item in missing_preview["recommendations"]}
        self.assertEqual(missing_by_id["ground-slam-mapping"]["action"]["kind"], "missing")

    def test_builtin_recommendation_does_not_offer_registry_update(self):
        self.module.APP_REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
        (self.module.APP_REGISTRY_DIR / "ros2-manager.json").write_text(json.dumps({
            "schema_version": "1",
            "id": "ros2-manager",
            "name": "ROS 2 Manager",
            "version": "99.0.0",
            "runtime": "service-bundle",
            "services": ["yari-ros"],
            "permissions": ["ros.read"],
            "ui": {"path": "#ros"},
        }))
        preview = self.module.app_recommendation_preview({
            "profile_preset": "ros_ground_robot",
            "vehicle_class": "ground_rover",
            "autopilot_stack": "ros_only",
            "compute_target": "raspberry_pi",
            "ros_domain_id": 0,
        })
        ros2 = next(item for item in preview["recommendations"] if item["id"] == "ros2-manager")
        self.assertEqual(ros2["source"], "builtin")
        self.assertEqual(ros2["action"]["kind"], "open")

    def test_app_recommendations_follow_device_profile(self):
        ground = self.module.recommended_apps_for_profile({"vehicle_class": "ground_rover", "autopilot_stack": "ros_only"})
        ground_ids = {item["id"] for item in ground}
        self.assertIn("ros2-manager", ground_ids)
        self.assertIn("rosbag-recorder", ground_ids)
        self.assertIn("ground-slam-mapping", ground_ids)
        self.assertIn("foxglove-bridge", ground_ids)
        self.assertIn("yari-atlas-bridge", ground_ids)
        self.assertEqual(len(ground_ids), len(ground))
        drone = self.module.recommended_apps_for_profile({"vehicle_class": "multirotor", "autopilot_stack": "px4"})
        drone_ids = {item["id"] for item in drone}
        self.assertIn("mavlink-router", drone_ids)
        self.assertIn("autopilot-log-downloader", drone_ids)
        self.assertIn("yari-atlas-bridge", drone_ids)
        self.assertIn("video-manager", drone_ids)
        self.assertEqual(len(drone_ids), len(drone))

    def test_app_readiness_reports_container_runtime_and_service_availability(self):
        container_app = self.module.normalize_app_manifest({
            "schema_version": "1",
            "id": "camera-streamer",
            "name": "Camera Streamer",
            "version": "0.1.0",
            "runtime": "container",
            "container": {"image": "registry.yari.io/yari/camera-streamer:0.1.0"},
            "permissions": ["camera.read"],
        })
        self.assertEqual(self.module.app_readiness(container_app)["state"], "blocked")
        ready = self.module.app_readiness(container_app, [], {"runtime": {"available": True, "name": "podman"}, "active": "not-created"})
        self.assertEqual(ready["state"], "ready")
        self.assertIn("podman", ready["message"])

        service_app = self.module.normalize_app_manifest({
            "schema_version": "1",
            "id": "missing-service",
            "name": "Missing Service",
            "version": "0.1.0",
            "runtime": "service-bundle",
            "services": ["missing.service"],
            "permissions": ["ros.read"],
        })
        blocked = self.module.app_readiness(service_app, [{"unit": "missing.service", "available": False}])
        self.assertEqual(blocked["state"], "blocked")
        self.assertIn("missing.service", blocked["message"])

    def test_app_catalog_loads_external_manifest_and_reports_errors(self):
        self.module.APP_MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
        (self.module.APP_MANIFEST_DIR / "demo.json").write_text('{"schema_version":"1","id":"demo-app","name":"Demo App","version":"1.0.0","runtime":"service-bundle","services":["demo.service"],"ports":[8080],"permissions":["ros.read"]}')
        (self.module.APP_MANIFEST_DIR / "camera.json").write_text('{"schema_version":"1","id":"camera-streamer","name":"Camera Streamer","version":"1.0.0","runtime":"container","container":{"image":"registry.yari.io/camera:1"},"ports":[{"container":8554,"host":8554,"protocol":"tcp"}],"permissions":["camera.read"]}')
        (self.module.APP_MANIFEST_DIR / "bad.json").write_text('{"schema_version":"2","id":"bad-app","runtime":"container","container":{"image":"bad"}}')
        catalog = self.module.app_catalog()
        demo = next(app for app in catalog["apps"] if app["id"] == "demo-app")
        camera = next(app for app in catalog["apps"] if app["id"] == "camera-streamer")
        self.assertEqual(demo["ports"], [8080])
        self.assertEqual(demo["source"], str(self.module.APP_MANIFEST_DIR / "demo.json"))
        self.assertEqual(camera["runtime"], "container")
        self.assertEqual(camera["container"]["image"], "registry.yari.io/camera:1")
        self.assertFalse(camera["actions"]["start"])
        self.assertEqual(camera["container_status"]["active"], "runtime-missing")
        self.assertFalse(catalog["container_runtime"]["available"])
        self.assertTrue(any("schema_version" in item["error"] for item in catalog["errors"]))

    def test_app_permission_review_summarizes_risk(self):
        app = self.module.normalize_app_manifest({
            "schema_version": "1",
            "id": "camera-streamer",
            "name": "Camera Streamer",
            "version": "0.1.0",
            "runtime": "container",
            "container": {"image": "registry.yari.io/camera:1", "network": "host"},
            "devices": ["/dev/video0"],
            "volumes": ["/var/lib/yari/apps/camera-streamer:/data"],
            "permissions": ["camera.read", "network.listen", "network.host", "storage.persistent"],
        })
        review = app["permission_review"]
        self.assertEqual(review["risk"], "high")
        permissions = {item["permission"]: item for item in review["items"]}
        self.assertEqual(permissions["camera.read"]["risk"], "medium")
        self.assertEqual(permissions["network.host"]["risk"], "high")
        self.assertEqual(permissions["storage.persistent"]["risk"], "medium")

        simple = self.module.normalize_app_manifest({
            "schema_version": "1",
            "id": "simple-app",
            "name": "Simple App",
            "version": "0.1.0",
            "runtime": "service-bundle",
            "services": ["demo.service"],
            "permissions": ["ros.read"],
        })
        self.assertEqual(simple["permission_review"]["risk"], "low")

    def test_app_manifest_validation_rejects_unsafe_fields(self):
        with self.assertRaises(ValueError):
            self.module.normalize_app_manifest({"schema_version": "1", "id": "bad-permission", "runtime": "container", "container": {"image": "demo"}, "permissions": ["shell"]})
        with self.assertRaises(ValueError):
            self.module.normalize_app_manifest({"schema_version": "1", "id": "bad-container", "runtime": "container"})
        with self.assertRaises(ValueError):
            self.module.normalize_app_manifest({"schema_version": "1", "id": "bad-service", "runtime": "service-bundle", "services": ["../../ssh"]})
        with self.assertRaises(ValueError):
            self.module.normalize_app_manifest({"schema_version": "1", "id": "bad-network", "runtime": "container", "container": {"image": "demo", "network": "container:host"}})
        with self.assertRaises(ValueError):
            self.module.normalize_app_manifest({"schema_version": "1", "id": "bad-protocol", "runtime": "container", "container": {"image": "demo"}, "ports": [{"container": 8554, "protocol": "sctp"}]})
        with self.assertRaises(ValueError):
            self.module.normalize_app_manifest({"schema_version": "1", "id": "bad-env", "runtime": "container", "container": {"image": "demo", "environment": {"BAD-NAME": "1"}}})
        with self.assertRaises(ValueError):
            self.module.normalize_app_manifest({"schema_version": "1", "id": "host-network", "runtime": "container", "container": {"image": "demo", "network": "host"}, "permissions": ["network.listen"]})
        with self.assertRaises(ValueError):
            self.module.normalize_app_manifest({"schema_version": "1", "id": "etc-volume", "runtime": "container", "container": {"image": "demo"}, "volumes": ["/etc:/host-etc"], "permissions": ["storage.persistent"]})
        with self.assertRaises(ValueError):
            self.module.normalize_app_manifest({"schema_version": "1", "id": "missing-storage", "runtime": "container", "container": {"image": "demo"}, "volumes": ["/var/lib/yari/apps/missing-storage:/data"]})
        with self.assertRaises(ValueError):
            self.module.normalize_app_manifest({"schema_version": "1", "id": "bad-device", "runtime": "container", "container": {"image": "demo"}, "devices": ["/dev/sda"], "permissions": ["camera.read"]})
        with self.assertRaises(ValueError):
            self.module.normalize_app_manifest({"schema_version": "1", "id": "bad-privileged", "runtime": "container", "container": {"image": "demo", "privileged": True}, "permissions": ["network.listen"]})

    def test_app_manifest_normalizes_container_ports_and_environment(self):
        app = self.module.normalize_app_manifest({
            "schema_version": "1",
            "id": "udp-video",
            "name": "UDP Video",
            "version": "0.1.0",
            "runtime": "container",
            "container": {"image": "registry.yari.io/video:1", "environment": {"YARI_MODE": "test"}},
            "ports": [{"container": 5600, "host": "5601", "protocol": "udp"}],
        })
        self.assertEqual(app["container"]["network"], "bridge")
        self.assertEqual(app["container"]["environment"], {"YARI_MODE": "test"})
        self.assertEqual(app["ports"], [{"container": 5600, "protocol": "udp", "host": 5601}])

    def test_install_app_manifest_writes_validated_external_manifest(self):
        payload = {
            "manifest": {
                "schema_version": "1",
                "id": "camera-streamer",
                "name": "Camera Streamer",
                "version": "0.1.0",
                "runtime": "container",
                "container": {"image": "registry.yari.io/yari/camera-streamer:0.1.0", "network": "host"},
                "permissions": ["camera.read", "network.listen", "network.host", "storage.persistent"],
                "ports": [{"container": 8554, "host": 8554, "protocol": "tcp"}],
            },
            "replace": False,
        }
        result = self.module.install_app_manifest(payload)
        manifest_path = self.module.APP_MANIFEST_DIR / "camera-streamer.json"
        self.assertTrue(result["ok"])
        self.assertTrue(manifest_path.exists())
        self.assertEqual(result["app"]["runtime"], "container")
        self.assertFalse(result["app"]["actions"]["start"])
        with self.assertRaises(ValueError):
            self.module.install_app_manifest(payload)
        payload["replace"] = True
        updated = self.module.install_app_manifest(payload)
        self.assertEqual(updated["app"]["id"], "camera-streamer")

    def test_uninstall_app_manifest_removes_only_external_manifest(self):
        self.module.install_app_manifest({
            "schema_version": "1",
            "id": "demo-service",
            "name": "Demo Service",
            "version": "0.1.0",
            "runtime": "service-bundle",
            "services": ["demo.service"],
            "permissions": ["ros.read"],
        })
        manifest_path = self.module.APP_MANIFEST_DIR / "demo-service.json"
        self.assertTrue(manifest_path.exists())
        result = self.module.uninstall_app_manifest("demo-service")
        self.assertTrue(result["ok"])
        self.assertFalse(manifest_path.exists())
        with self.assertRaises(ValueError):
            self.module.uninstall_app_manifest("ros2-manager")

    def test_documented_app_manifest_examples_normalize(self):
        examples_dir = SCRIPT.parents[1] / "apps" / "examples"
        examples = list(examples_dir.glob("*.json"))
        self.assertTrue(examples)
        app_ids = set()
        for path in examples:
            app = self.module.normalize_app_manifest(json.loads(path.read_text()), str(path))
            self.assertEqual(app["schema_version"], "1")
            self.assertIn(app["runtime"], {"core-service", "service-bundle", "container"})
            app_ids.add(app["id"])
        self.assertTrue({
            "foxglove-bridge",
            "yari-atlas-bridge",
            "mavlink-router",
            "rosbag-recorder",
            "camera-streamer",
            "autopilot-log-downloader",
            "ground-slam-mapping",
        }.issubset(app_ids))

    def test_validate_app_manifest_reports_install_readiness(self):
        manifest = {
            "schema_version": "1",
            "id": "camera-streamer",
            "name": "Camera Streamer",
            "version": "0.1.0",
            "runtime": "container",
            "container": {"image": "registry.yari.io/camera:1"},
            "permissions": ["camera.read"],
        }
        validation = self.module.validate_app_manifest_payload({"manifest": manifest})
        self.assertTrue(validation["ok"])
        self.assertTrue(validation["can_install"])
        self.assertFalse(validation["existing"])
        self.assertEqual(validation["app"]["id"], "camera-streamer")
        self.module.install_app_manifest({"manifest": manifest})
        validation = self.module.validate_app_manifest_payload({"manifest": manifest})
        self.assertFalse(validation["can_install"])
        self.assertTrue(validation["existing"])
        self.assertIn("already exists", validation["reason"])
        validation = self.module.validate_app_manifest_payload({"manifest": manifest, "replace": True})
        self.assertTrue(validation["can_install"])
        self.assertTrue(validation["replace"])

    def test_validate_app_manifest_blocks_builtin_replacement(self):
        manifest = {
            "schema_version": "1",
            "id": "log-manager",
            "name": "Log Manager",
            "version": "99.0.0",
            "runtime": "service-bundle",
            "services": ["yari-log-manager"],
        }
        validation = self.module.validate_app_manifest_payload({"manifest": manifest, "replace": True})
        self.assertFalse(validation["can_install"])
        self.assertIn("built-in", validation["reason"])
        with self.assertRaises(ValueError):
            self.module.install_app_manifest({"manifest": manifest, "replace": True})

    def test_app_registry_lists_local_manifests_and_install_state(self):
        self.module.APP_REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
        registry_manifest = self.module.APP_REGISTRY_DIR / "camera.json"
        registry_manifest.write_text('{"schema_version":"1","id":"camera-streamer","name":"Camera Streamer","version":"0.1.0","runtime":"container","container":{"image":"registry.yari.io/camera:1"},"permissions":["camera.read"]}')
        registry = self.module.app_registry()
        camera = next(app for app in registry["apps"] if app["id"] == "camera-streamer")
        self.assertFalse(camera["installed"])
        self.assertFalse(camera["update"]["update_available"])
        self.assertTrue(camera["actions"]["apply"])
        self.assertTrue(camera["actions"]["install"])
        self.assertFalse(camera["actions"]["update"])
        self.assertEqual(camera["update"]["registry_version"], "0.1.0")
        self.assertEqual(registry["registry_dir"], str(self.module.APP_REGISTRY_DIR))
        self.module.install_registry_app("camera-streamer")
        registry = self.module.app_registry()
        camera = next(app for app in registry["apps"] if app["id"] == "camera-streamer")
        self.assertTrue(camera["installed"])
        self.assertEqual(camera["installed_version"], "0.1.0")
        self.assertFalse(camera["update"]["update_available"])
        self.assertFalse(camera["actions"]["apply"])
        self.assertIn("current", camera["actions"]["reason"])
        self.assertTrue((self.module.APP_MANIFEST_DIR / "camera-streamer.json").exists())
        registry_manifest.write_text('{"schema_version":"1","id":"camera-streamer","name":"Camera Streamer","version":"0.2.0","runtime":"container","container":{"image":"registry.yari.io/camera:2"},"permissions":["camera.read"]}')
        registry = self.module.app_registry()
        camera = next(app for app in registry["apps"] if app["id"] == "camera-streamer")
        self.assertEqual(camera["installed_version"], "0.1.0")
        self.assertEqual(camera["update"]["registry_version"], "0.2.0")
        self.assertTrue(camera["update"]["update_available"])
        self.assertTrue(camera["actions"]["apply"])
        self.assertTrue(camera["actions"]["update"])
        catalog = self.module.app_catalog()
        installed = next(app for app in catalog["apps"] if app["id"] == "camera-streamer")
        self.assertTrue(installed["update"]["update_available"])

    def test_app_registry_marks_builtin_apps_as_base_image_managed(self):
        self.module.APP_REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
        registry_manifest = self.module.APP_REGISTRY_DIR / "foxglove.json"
        registry_manifest.write_text('{"schema_version":"1","id":"foxglove-bridge","name":"Foxglove Bridge","version":"core","runtime":"core-service","services":["foxglove-bridge"],"permissions":["ros.read"]}')
        registry = self.module.app_registry()
        foxglove = next(app for app in registry["apps"] if app["id"] == "foxglove-bridge")
        self.assertTrue(foxglove["installed"])
        self.assertEqual(foxglove["installed_source"], "builtin")
        self.assertFalse(foxglove["actions"]["apply"])
        self.assertIn("base image", foxglove["actions"]["reason"])
        with self.assertRaises(ValueError):
            self.module.update_installed_app("foxglove-bridge")

    def write_app_package(self, name, manifest, metadata=None):
        import hashlib
        import io
        self.module.APP_PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
        package = self.module.APP_PACKAGE_DIR / name
        manifest_bytes = json.dumps(manifest).encode("utf-8")
        metadata = dict(metadata or {})
        if metadata:
            metadata.setdefault("manifest_sha256", hashlib.sha256(manifest_bytes).hexdigest())
            metadata_bytes = json.dumps(metadata).encode("utf-8")
        else:
            metadata_bytes = None
        with tarfile.open(package, "w:gz") as archive:
            info = tarfile.TarInfo("manifest.json")
            info.size = len(manifest_bytes)
            archive.addfile(info, io.BytesIO(manifest_bytes))
            if metadata_bytes is not None:
                meta_info = tarfile.TarInfo("yari-package.json")
                meta_info.size = len(metadata_bytes)
                archive.addfile(meta_info, io.BytesIO(metadata_bytes))
        return package

    def test_app_packages_list_and_install_local_yariapp(self):
        manifest = {
            "schema_version": "1",
            "id": "camera-streamer",
            "name": "Camera Streamer",
            "version": "0.1.0",
            "runtime": "container",
            "container": {"image": "registry.yari.io/camera:1"},
            "permissions": ["camera.read"],
            "ui": {"path": "#video"},
        }
        package = self.write_app_package("camera-streamer-0.1.0.yariapp", manifest)
        packages = self.module.app_packages()
        self.assertEqual(packages["package_dir"], str(self.module.APP_PACKAGE_DIR))
        self.assertEqual(len(packages["packages"]), 1)
        item = packages["packages"][0]
        self.assertEqual(item["name"], package.name)
        self.assertEqual(item["app"]["id"], "camera-streamer")
        self.assertFalse(item["installed"])
        self.assertEqual(len(item["sha256"]), 64)
        self.assertEqual(len(item["manifest_sha256"]), 64)
        self.assertEqual(item["signature"]["status"], "missing")
        self.assertFalse(packages["signature_required"])
        result = self.module.install_app_package(package.name)
        self.assertTrue(result["ok"])
        self.assertTrue((self.module.APP_MANIFEST_DIR / "camera-streamer.json").exists())
        installed = json.loads((self.module.APP_MANIFEST_DIR / "camera-streamer.json").read_text())
        self.assertNotIn("source", installed)
        self.assertNotIn("installed", installed)
        packages = self.module.app_packages()
        item = packages["packages"][0]
        self.assertTrue(item["installed"])
        self.assertFalse(item["update"]["update_available"])
        manifest["version"] = "0.2.0"
        manifest["container"]["image"] = "registry.yari.io/camera:2"
        self.write_app_package("camera-streamer-0.1.0.yariapp", manifest)
        packages = self.module.app_packages()
        item = packages["packages"][0]
        self.assertEqual(item["installed_version"], "0.1.0")
        self.assertTrue(item["update"]["update_available"])

    def test_app_package_upload_validates_and_stores_package(self):
        manifest = {
            "schema_version": "1",
            "id": "uploaded-camera",
            "name": "Uploaded Camera",
            "version": "0.1.0",
            "runtime": "container",
            "container": {"image": "registry.yari.io/camera:1"},
            "permissions": ["camera.read"],
        }
        source = self.write_app_package("source-upload.yariapp", manifest)
        payload = {
            "name": "uploaded-camera-0.1.0.yariapp",
            "content_base64": base64.b64encode(source.read_bytes()).decode("ascii"),
        }
        result = self.module.upload_app_package(payload)
        self.assertTrue(result["ok"])
        self.assertEqual(result["package"]["name"], "uploaded-camera-0.1.0.yariapp")
        self.assertEqual(result["package"]["app"]["id"], "uploaded-camera")
        self.assertTrue((self.module.APP_PACKAGE_DIR / "uploaded-camera-0.1.0.yariapp").exists())
        packages = self.module.app_packages()
        self.assertTrue(any(item["name"] == "uploaded-camera-0.1.0.yariapp" for item in packages["packages"]))
        with self.assertRaises(ValueError):
            self.module.upload_app_package(payload)
        payload["replace"] = True
        self.assertTrue(self.module.upload_app_package(payload)["ok"])

    def test_app_package_delete_removes_local_package(self):
        manifest = {
            "schema_version": "1",
            "id": "delete-camera",
            "name": "Delete Camera",
            "version": "0.1.0",
            "runtime": "container",
            "container": {"image": "registry.yari.io/camera:1"},
        }
        package = self.write_app_package("delete-camera.yariapp", manifest)
        self.assertTrue(package.exists())
        result = self.module.delete_app_package(package.name)
        self.assertTrue(result["ok"])
        self.assertEqual(result["deleted"], package.name)
        self.assertFalse(package.exists())
        with self.assertRaises(ValueError):
            self.module.delete_app_package("../delete-camera.yariapp")

    def test_app_package_upload_rejects_invalid_content_and_oversize(self):
        self.module.APP_PACKAGE_UPLOAD_MAX_BYTES = 4
        with self.assertRaises(ValueError):
            self.module.upload_app_package({"name": "bad.yariapp", "content_base64": "not-base64"})
        with self.assertRaises(ValueError):
            self.module.upload_app_package({"name": "bad.yariapp", "content_base64": base64.b64encode(b"not a tar").decode("ascii")})
        self.assertFalse((self.module.APP_PACKAGE_DIR / "bad.yariapp").exists())
        with self.assertRaises(ValueError):
            self.module.upload_app_package({"name": "big.yariapp", "content_base64": base64.b64encode(b"12345").decode("ascii")})

    def test_app_package_metadata_checksum_and_signature_gate(self):
        manifest = {
            "schema_version": "1",
            "id": "signed-camera",
            "name": "Signed Camera",
            "version": "1.0.0",
            "runtime": "container",
            "container": {"image": "registry.yari.io/camera:1"},
            "permissions": ["camera.read"],
        }
        package = self.write_app_package("signed-camera.yariapp", manifest, {"signed_by": "YARI", "signature_type": "ed25519", "signature": "placeholder"})
        packages = self.module.app_packages()
        item = next(item for item in packages["packages"] if item["name"] == package.name)
        self.assertEqual(item["signature"]["status"], "public-key-missing")
        self.assertTrue(item["signature"]["present"])
        self.assertFalse(item["signature"]["verified"])
        result = self.module.install_app_package(package.name)
        self.assertEqual(result["package"]["signature"]["status"], "public-key-missing")

        self.module.APP_REQUIRE_SIGNED_PACKAGES = True
        unsigned = self.write_app_package("unsigned-camera.yariapp", {**manifest, "id": "unsigned-camera", "name": "Unsigned Camera"})
        with self.assertRaises(ValueError):
            self.module.install_app_package(unsigned.name)
        packages = self.module.app_packages()
        unsigned_item = next(item for item in packages["errors"] if "unsigned-camera" in item["path"])
        self.assertIn("signature", unsigned_item["error"])
        self.module.APP_REQUIRE_SIGNED_PACKAGES = False

    def test_app_package_can_require_verified_signature(self):
        manifest = {
            "schema_version": "1",
            "id": "verified-camera",
            "name": "Verified Camera",
            "version": "1.0.0",
            "runtime": "container",
            "container": {"image": "registry.yari.io/camera:1"},
            "permissions": ["camera.read"],
        }
        self.module.APP_PACKAGE_PUBLIC_KEY_FILE.write_text("public-key")
        self.module.has_command = lambda name: name in {"nmcli", "openssl"}
        package = self.write_app_package("verified-camera.yariapp", manifest, {"signed_by": "YARI", "signature_type": "sha256-rsa", "signature": "c2ln"})
        packages = self.module.app_packages()
        item = next(item for item in packages["packages"] if item["name"] == package.name)
        self.assertEqual(item["signature"]["status"], "verified")
        self.assertTrue(item["signature"]["verified"])

        self.module.APP_REQUIRE_VERIFIED_PACKAGES = True
        result = self.module.install_app_package(package.name)
        self.assertEqual(result["package"]["signature"]["status"], "verified")

        def failing_command_output(args, timeout=8):
            if args and args[0] == "openssl":
                raise RuntimeError("bad signature")
            return self.fake_command_output(args, timeout)

        self.module.command_output = failing_command_output
        bad = self.write_app_package("bad-signature.yariapp", {**manifest, "id": "bad-signature", "name": "Bad Signature"}, {"signed_by": "YARI", "signature_type": "sha256-rsa", "signature": "c2ln"})
        with self.assertRaises(ValueError):
            self.module.install_app_package(bad.name)
        self.module.APP_REQUIRE_VERIFIED_PACKAGES = False

    def test_app_package_rejects_manifest_checksum_mismatch(self):
        manifest = {
            "schema_version": "1",
            "id": "bad-checksum",
            "name": "Bad Checksum",
            "version": "1.0.0",
            "runtime": "container",
            "container": {"image": "registry.yari.io/camera:1"},
        }
        bad = self.write_app_package("bad-checksum.yariapp", manifest, {"manifest_sha256": "0" * 64})
        with self.assertRaises(ValueError):
            self.module.install_app_package(bad.name)
        packages = self.module.app_packages()
        self.assertTrue(any("manifest_sha256" in item["error"] for item in packages["errors"]))

    def test_app_package_rejects_unsafe_or_invalid_packages(self):
        with self.assertRaises(ValueError):
            self.module.package_path("../bad.yariapp")
        self.module.APP_PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
        bad = self.module.APP_PACKAGE_DIR / "bad.yariapp"
        bad.write_text("not a tar")
        packages = self.module.app_packages()
        self.assertTrue(packages["errors"])
        with self.assertRaises(ValueError):
            self.module.install_app_package("bad.yariapp")

    def test_update_installed_app_applies_registry_update(self):
        self.module.APP_REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
        registry_manifest = self.module.APP_REGISTRY_DIR / "camera.json"
        registry_manifest.write_text('{"schema_version":"1","id":"camera-streamer","name":"Camera Streamer","version":"0.1.0","runtime":"container","container":{"image":"registry.yari.io/camera:1"},"permissions":["camera.read"]}')
        self.module.install_registry_app("camera-streamer")
        registry_manifest.write_text('{"schema_version":"1","id":"camera-streamer","name":"Camera Streamer","version":"0.2.0","runtime":"container","container":{"image":"registry.yari.io/camera:2"},"permissions":["camera.read"]}')
        catalog = self.module.app_catalog()
        app = next(app for app in catalog["apps"] if app["id"] == "camera-streamer")
        self.assertTrue(app["update"]["update_available"])
        self.assertTrue(app["actions"]["update"])
        result = self.module.update_installed_app("camera-streamer")
        self.assertTrue(result["ok"])
        self.assertEqual(result["app"]["version"], "0.2.0")
        installed = json.loads((self.module.APP_MANIFEST_DIR / "camera-streamer.json").read_text())
        self.assertEqual(installed["version"], "0.2.0")
        self.assertEqual(installed["container"]["image"], "registry.yari.io/camera:2")
        catalog = self.module.app_catalog()
        app = next(app for app in catalog["apps"] if app["id"] == "camera-streamer")
        self.assertFalse(app["update"]["update_available"])
        self.assertFalse(app["actions"]["update"])
        with self.assertRaises(ValueError):
            self.module.update_installed_app("camera-streamer")

    def test_app_registry_reports_invalid_manifests(self):
        self.module.APP_REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
        (self.module.APP_REGISTRY_DIR / "bad.json").write_text('{"schema_version":"1","id":"bad app"}')
        registry = self.module.app_registry()
        self.assertTrue(registry["errors"])
        with self.assertRaises(ValueError):
            self.module.install_registry_app("missing-app")

    def test_app_action_controls_only_manifest_services(self):
        result = self.module.app_action("ros2-manager", "restart")
        self.assertTrue(result["ok"])
        self.assertIn(["systemctl", "restart", "yari-ros.service"], self.commands)
        enable = self.module.app_action("ros2-manager", "enable")
        self.assertTrue(enable["ok"])
        self.assertEqual(enable["action"], "enable")
        self.assertIn(["systemctl", "enable", "yari-ros.service"], self.commands)
        disable = self.module.app_action("ros2-manager", "disable")
        self.assertTrue(disable["ok"])
        self.assertIn(["systemctl", "disable", "yari-ros.service"], self.commands)
        with self.assertRaises(ValueError):
            self.module.app_action("missing-app", "start")
        self.module.APP_MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
        (self.module.APP_MANIFEST_DIR / "bad-service.json").write_text('{"id":"bad-service","services":["../../ssh"]}')
        with self.assertRaises(ValueError):
            self.module.app_action("bad-service", "start")

    def test_app_healthcheck_service_and_tcp_status(self):
        service_app = self.module.normalize_app_manifest({
            "schema_version": "1",
            "id": "health-service",
            "name": "Health Service",
            "version": "0.1.0",
            "runtime": "service-bundle",
            "services": ["yari-ros"],
            "healthcheck": {"type": "service", "service": "yari-ros"},
        })
        service = self.module.enrich_app(service_app)
        self.assertTrue(service["healthcheck_status"]["configured"])
        self.assertFalse(service["healthcheck_status"]["ok"])
        self.assertEqual(service["healthcheck_status"]["state"], "failing")

        class FakeSocket:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, traceback):
                return False
        original_create_connection = self.module.socket.create_connection
        self.module.socket.create_connection = lambda address, timeout=0: FakeSocket()
        try:
            tcp_app = self.module.normalize_app_manifest({
                "schema_version": "1",
                "id": "health-tcp",
                "name": "Health TCP",
                "version": "0.1.0",
                "runtime": "container",
                "container": {"image": "registry.yari.io/test:1"},
                "healthcheck": {"type": "tcp", "host": "127.0.0.1", "port": 8554},
            })
            status = self.module.app_healthcheck_status(tcp_app)
        finally:
            self.module.socket.create_connection = original_create_connection
        self.assertTrue(status["ok"])
        self.assertEqual(status["state"], "passing")

    def test_app_healthcheck_rejects_unsafe_or_invalid_checks(self):
        app = self.module.normalize_app_manifest({
            "schema_version": "1",
            "id": "bad-health",
            "name": "Bad Health",
            "version": "0.1.0",
            "runtime": "container",
            "container": {"image": "registry.yari.io/test:1"},
            "healthcheck": {"type": "command", "command": "whoami"},
        })
        status = self.module.app_healthcheck_status(app)
        self.assertEqual(status["state"], "unsupported")

        bad_tcp = dict(app)
        bad_tcp["healthcheck"] = {"type": "tcp", "port": 0}
        self.assertEqual(self.module.app_healthcheck_status(bad_tcp)["state"], "invalid")

    def test_container_app_action_requires_runtime(self):
        self.module.install_app_manifest({
            "schema_version": "1",
            "id": "camera-streamer",
            "name": "Camera Streamer",
            "version": "0.1.0",
            "runtime": "container",
            "container": {"image": "registry.yari.io/yari/camera-streamer:0.1.0"},
            "permissions": ["camera.read"],
        })
        with self.assertRaises(ValueError):
            self.module.app_action("camera-streamer", "start")
        self.module.has_command = lambda name: name in {"docker", "nmcli"}
        with self.assertRaises(ValueError):
            self.module.app_action("camera-streamer", "enable")

    def test_container_app_action_builds_runtime_command(self):
        self.module.has_command = lambda name: name in {"docker", "nmcli"}
        self.module.install_app_manifest({
            "schema_version": "1",
            "id": "camera-streamer",
            "name": "Camera Streamer",
            "version": "0.1.0",
            "runtime": "container",
            "container": {
                "image": "registry.yari.io/yari/camera-streamer:0.1.0",
                "network": "bridge",
                "environment": {"YARI_CAMERA_DEVICE": "/dev/video0"},
            },
            "ports": [{"container": 8554, "host": 8554, "protocol": "tcp"}],
            "devices": ["/dev/video0"],
            "volumes": ["/var/lib/yari/apps/camera-streamer:/data"],
            "permissions": ["camera.read", "network.listen", "storage.persistent"],
        })
        result = self.module.app_action("camera-streamer", "start")
        self.assertTrue(result["ok"])
        self.assertIn(["docker", "rm", "-f", "yari-camera-streamer"], self.commands)
        run_command = next(command for command in self.commands if command[:3] == ["docker", "run", "-d"])
        self.assertIn("--name", run_command)
        self.assertIn("yari-camera-streamer", run_command)
        self.assertIn("-p", run_command)
        self.assertIn("8554:8554/tcp", run_command)
        udp_app = self.module.normalize_app_manifest({
            "schema_version": "1",
            "id": "udp-video",
            "name": "UDP Video",
            "version": "0.1.0",
            "runtime": "container",
            "container": {"image": "registry.yari.io/video:1"},
            "ports": [{"container": 5600, "host": 5601, "protocol": "udp"}],
        })
        self.assertIn("5601:5600/udp", self.module.container_run_command("docker", udp_app))
        self.assertIn("--device", run_command)
        self.assertIn("/dev/video0", run_command)
        self.assertEqual(run_command[-1], "registry.yari.io/yari/camera-streamer:0.1.0")

    def test_app_logs_read_manifest_service_journals(self):
        logs = self.module.app_logs("log-manager", 20)
        self.assertTrue(logs["ok"])
        self.assertEqual(logs["app_id"], "log-manager")
        self.assertIn(["journalctl", "-u", "yari-log-manager.service", "-n", "20", "--no-pager"], self.commands)

    def test_container_app_logs_use_runtime_logs(self):
        self.module.has_command = lambda name: name in {"docker", "nmcli"}
        self.module.install_app_manifest({
            "schema_version": "1",
            "id": "camera-streamer",
            "name": "Camera Streamer",
            "version": "0.1.0",
            "runtime": "container",
            "container": {"image": "registry.yari.io/yari/camera-streamer:0.1.0"},
            "permissions": ["camera.read"],
        })
        catalog = self.module.app_catalog()
        app = next(app for app in catalog["apps"] if app["id"] == "camera-streamer")
        self.assertTrue(app["actions"]["logs"])
        self.assertEqual(catalog["container_runtime"]["name"], "docker")
        logs = self.module.app_logs("camera-streamer", 40)
        self.assertTrue(logs["ok"])
        self.assertEqual(logs["logs"][0]["container"], "yari-camera-streamer")
        self.assertIn(["docker", "logs", "--tail", "40", "yari-camera-streamer"], self.commands)

    def test_service_name_rejects_unknown_services(self):
        self.assertEqual(self.module.service_name("yari-onboarding"), "yari-onboarding.service")
        with self.assertRaises(ValueError):
            self.module.service_name("ssh")

    def test_write_mavlink_endpoints_validates_type(self):
        config = self.module.write_mavlink_endpoints({"endpoints": [{"name": "fc", "type": "serial", "device": "/dev/ttyACM0"}]})
        self.assertEqual(config["endpoints"][0]["name"], "fc")
        self.assertEqual(config["endpoints"][0]["baud"], 57600)
        with self.assertRaises(ValueError):
            self.module.write_mavlink_endpoints({"endpoints": [{"name": "bad", "type": "shell"}]})
        with self.assertRaises(ValueError):
            self.module.write_mavlink_endpoints({"endpoints": [{"name": "bad", "type": "udp", "port": 99999}]})

    def test_factory_reset_removes_saved_network_files(self):
        self.module.COMPLETE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.module.COMPLETE_FILE.write_text("")
        self.module.NM_CONNECTION_DIR.mkdir(parents=True, exist_ok=True)
        self.module.NETPLAN_DIR.mkdir(parents=True, exist_ok=True)
        (self.module.NM_CONNECTION_DIR / "yari-wifi.nmconnection").write_text("wifi")
        (self.module.NETPLAN_DIR / "01-yari-wifi.yaml").write_text("wifi")
        (self.module.NETPLAN_DIR / "01-tortoisebot-wifi.yaml").write_text("legacy")
        (self.module.NETPLAN_DIR / "99-tortoisebot-wifi.yaml").write_text("legacy")
        (self.module.NETPLAN_DIR / "10-ethernet.yaml").write_text("ethernet")
        state = self.module.factory_reset(reboot=False)
        self.assertFalse(self.module.COMPLETE_FILE.exists())
        self.assertFalse((self.module.NM_CONNECTION_DIR / "yari-wifi.nmconnection").exists())
        self.assertFalse((self.module.NETPLAN_DIR / "01-yari-wifi.yaml").exists())
        self.assertFalse((self.module.NETPLAN_DIR / "01-tortoisebot-wifi.yaml").exists())
        self.assertFalse((self.module.NETPLAN_DIR / "99-tortoisebot-wifi.yaml").exists())
        self.assertTrue((self.module.NETPLAN_DIR / "10-ethernet.yaml").exists())
        self.assertFalse(state["complete"])

    def test_save_pairing_tokens_redacts_status_and_writes_secret_file(self):
        status = self.module.save_pairing_tokens("atlas-secret", "fox-secret")
        self.assertTrue(self.module.PORTAL_SECRETS_FILE.exists())
        self.assertEqual(oct(self.module.PORTAL_SECRETS_FILE.stat().st_mode & 0o777), "0o600")
        self.assertTrue(status["atlas_token"]["configured"])
        self.assertNotIn("atlas-secret", str(status))

    def test_save_setup_config_persists_atlas_upload_url(self):
        result = self.module.save_setup_config({
            "hostname": "tortoisebot",
            "atlas_url": "http://atlas/api/v1",
            "atlas_upload_url": "http://atlas/upload",
        })
        self.assertTrue(result["ok"])
        config = self.module.read_json_file(self.module.PORTAL_CONFIG_FILE, {})
        self.assertEqual(config["atlas_url"], "http://atlas/api/v1")
        self.assertEqual(config["atlas_upload_url"], "http://atlas/upload")

    def test_save_setup_config_persists_device_profile_payload(self):
        result = self.module.save_setup_config({
            "hostname": "tortoisebot",
            "device_profile": {
                "profile_preset": "ardupilot_companion",
                "vehicle_class": "multirotor",
                "autopilot_stack": "ardupilot",
                "compute_target": "raspberry_pi",
                "ros_domain_id": 7,
            },
        })
        self.assertTrue(result["ok"])
        config = self.module.read_json_file(self.module.PORTAL_CONFIG_FILE, {})
        self.assertEqual(config["device_profile"]["profile_preset"], "ardupilot_companion")
        self.assertEqual(config["device_profile"]["autopilot_stack"], "ardupilot")
        self.assertEqual(config["device_profile"]["ros_domain_id"], 7)

    def test_device_profile_presets_include_supported_roles(self):
        presets = self.module.device_profile_presets()
        ids = {item["id"] for item in presets["presets"]}
        self.assertEqual(presets["default"], "tortoisebot_rover")
        self.assertIn("px4_companion", ids)
        self.assertIn("ardupilot_companion", ids)
        self.assertIn("custom", ids)
        px4 = next(item for item in presets["presets"] if item["id"] == "px4_companion")
        self.assertEqual(px4["values"]["autopilot_stack"], "px4")

    def test_default_device_profile_is_tortoisebot_rover(self):
        profile = self.module.read_device_profile()
        self.assertEqual(profile["profile_preset"], "tortoisebot_rover")
        self.assertEqual(profile["vehicle_class"], "ground_rover")
        self.assertEqual(profile["autopilot_stack"], "ros_only")
        self.assertEqual(profile["compute_target"], "raspberry_pi")

    def test_save_device_profile_validates_and_persists_role_metadata(self):
        result = self.module.save_device_profile({
            "profile_preset": "px4_companion",
            "vehicle_class": "multirotor",
            "autopilot_stack": "px4",
            "compute_target": "jetson_orin",
            "ros_domain_id": 42,
            "notes": "lab drone",
        })
        self.assertTrue(result["ok"])
        self.assertEqual(result["profile"]["profile_preset"], "px4_companion")
        self.assertEqual(result["profile"]["vehicle_class"], "multirotor")
        self.assertEqual(result["profile"]["autopilot_stack"], "px4")
        self.assertEqual(result["profile"]["compute_target"], "jetson_orin")
        self.assertEqual(result["profile"]["ros_domain_id"], 42)
        self.assertEqual(oct(self.module.PORTAL_CONFIG_FILE.stat().st_mode & 0o777), "0o600")
        self.assertEqual(self.module.device_status()["profile"]["profile_preset"], "px4_companion")
        self.assertEqual(self.module.device_status()["profile"]["vehicle_class"], "multirotor")

    def test_save_device_profile_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            self.module.save_device_profile({"profile_preset": "unsupported"})
        with self.assertRaises(ValueError):
            self.module.save_device_profile({"vehicle_class": "spaceship"})
        with self.assertRaises(ValueError):
            self.module.save_device_profile({"ros_domain_id": 233})

    def test_regenerate_device_id_writes_override(self):
        state = self.module.regenerate_device_id()
        self.assertTrue(self.module.DEVICE_ID_FILE.exists())
        self.assertEqual(state["device_id"], self.module.DEVICE_ID_FILE.read_text().strip())

    def test_network_status_includes_phase_one_placeholders(self):
        status = self.module.network_status()
        self.assertIn("static_ip", status["config"])
        self.assertTrue(status["config"]["static_ip"]["supported"])
        self.assertIn("policy", status["config"])
        self.assertTrue(status["config"]["policy"]["fallback_ap_enabled"])
        self.assertIn("lte", status["config"])

    def test_save_network_policy_persists_recovery_settings(self):
        result = self.module.save_network_policy({
            "fallback_ap_enabled": False,
            "fallback_timeout_sec": 90,
            "maintenance_ap_enabled": True,
            "serve_portal_on_client_network": True,
        })
        self.assertTrue(result["ok"])
        self.assertFalse(result["policy"]["fallback_ap_enabled"])
        self.assertTrue(result["policy"]["maintenance_ap_enabled"])
        self.assertEqual(result["policy"]["fallback_timeout_sec"], 90)
        self.assertEqual(oct(self.module.NETWORK_POLICY_CONFIG_FILE.stat().st_mode & 0o777), "0o600")
        self.assertEqual(self.module.read_network_policy()["fallback_timeout_sec"], 90)

    def test_save_network_policy_validates_timeout(self):
        with self.assertRaises(ValueError):
            self.module.save_network_policy({"fallback_timeout_sec": 4})
        with self.assertRaises(ValueError):
            self.module.save_network_policy({"fallback_timeout_sec": 601})

    def test_save_static_ip_config_validates_and_modifies_networkmanager(self):
        self.module.APPLY_NETWORK = True
        result = self.module.save_static_ip_config({
            "enabled": True,
            "connection_name": "yari-wifi",
            "address_cidr": "192.168.0.50/24",
            "gateway": "192.168.0.1",
            "dns": "1.1.1.1,8.8.8.8",
        })
        self.assertTrue(result["ok"])
        self.assertEqual(result["static_ip"]["address_cidr"], "192.168.0.50/24")
        self.assertIn(["nmcli", "connection", "modify", "yari-wifi", "ipv4.method", "manual", "ipv4.addresses", "192.168.0.50/24", "ipv4.gateway", "192.168.0.1", "ipv4.dns", "1.1.1.1,8.8.8.8", "ipv6.method", "ignore"], self.commands)
        with self.assertRaises(ValueError):
            self.module.save_static_ip_config({"enabled": True, "address_cidr": "not-an-ip"})

    def test_device_status_includes_hardware_model(self):
        self.module.DEVICE_MODEL_PATHS[0].write_text("Raspberry Pi 5 Model B\x00")
        status = self.module.device_status()
        self.assertEqual(status["device_model"], "Raspberry Pi 5 Model B")


    def test_autopilot_status_uses_manager_heartbeat_file(self):
        self.module.SERVICE_STATE_DIR.mkdir(parents=True, exist_ok=True)
        (self.module.SERVICE_STATE_DIR / "autopilot-manager.json").write_text('{"connected": true, "flight_stack": "PX4", "mode": "MANUAL", "updated": 1}')
        status = self.module.autopilot_status()
        self.assertTrue(status["connected"])
        self.assertEqual(status["flight_stack"], "PX4")
        self.assertEqual(status["mode"], "MANUAL")

    def test_ros_status_uses_service_manager_topics_and_recording(self):
        self.module.SERVICE_STATE_DIR.mkdir(parents=True, exist_ok=True)
        (self.module.SERVICE_STATE_DIR / "ros.json").write_text('{"installed": true, "nodes": ["/camera"], "topics": ["/scan [sensor_msgs/msg/LaserScan]"], "recording": {"active": true}, "updated": 1}')
        status = self.module.ros_status()
        self.assertEqual(status["nodes"], ["/camera"])
        self.assertTrue(status["recording"]["active"])
        self.assertIn("/scan [sensor_msgs/msg/LaserScan]", status["topics"])


    def test_ros_launch_profiles_are_configurable(self):
        self.module.ROS_LAUNCH_CONFIG_FILE.write_text('{"profiles": [{"name": "drone companion", "command": "ros2 launch demo demo.launch.py", "enabled": true}]}')
        profiles = self.module.read_ros_launch_profiles()
        self.assertEqual(profiles["profiles"][0]["name"], "drone-companion")
        self.assertTrue(profiles["profiles"][0]["command_configured"])

    def test_ros_launch_profile_requires_configured_command(self):
        self.module.ROS_LAUNCH_CONFIG_FILE.write_text('{"profiles": [{"name": "drone-companion", "command": "", "enabled": true}]}')
        result = self.module.start_ros_launch_profile({"profile": "drone-companion"})
        self.assertFalse(result["ok"])
        self.assertIn("command", result["error"])

    def test_ros_launch_profile_rejects_relative_cwd(self):
        self.module.ROS_LAUNCH_CONFIG_FILE.write_text('{"profiles": [{"name": "bad", "command": "echo ok", "cwd": "relative", "enabled": true}]}')
        with self.assertRaises(ValueError):
            self.module.start_ros_launch_profile({"profile": "bad"})


    def test_save_video_settings_validates_and_persists(self):
        settings = self.module.save_video_settings({"fps": "20", "encoding": "mono8", "bandwidth_kbps": "512", "stream_enabled": "on", "rtsp_url": "rtsp://127.0.0.1:8554/test", "foxglove_topic": "/camera/image_raw/compressed", "atlas_webrtc_enabled": "on", "atlas_camera_topic": "/camera/image_raw/compressed", "atlas_max_video_fps": "12"})
        self.assertEqual(settings["fps"], 20)
        self.assertEqual(settings["encoding"], "mono8")
        self.assertTrue(settings["stream_enabled"])
        self.assertTrue(settings["atlas_webrtc_enabled"])
        self.assertEqual(settings["atlas_max_video_fps"], 12)
        self.assertTrue(self.module.VIDEO_CONFIG_FILE.exists())
        with self.assertRaises(ValueError):
            self.module.save_video_settings({"fps": "0", "encoding": "mjpeg"})
        with self.assertRaises(ValueError):
            self.module.save_video_settings({"fps": "20", "encoding": "mjpeg", "rtsp_url": "http://bad"})
        with self.assertRaises(ValueError):
            self.module.save_video_settings({"fps": "20", "encoding": "mjpeg", "foxglove_topic": "camera/no-slash"})

    def test_video_stream_targets_reports_foxglove_and_atlas_readiness(self):
        self.module.PORTAL_CONFIG_FILE.write_text('{"atlas_url":"http://atlas/api/v1"}')
        self.module.PORTAL_SECRETS_FILE.write_text('{"atlas_token":"token"}')
        self.module.ros_command = lambda args, timeout=8: {"ok": True, "stdout": "/camera/image_raw/compressed [sensor_msgs/msg/CompressedImage]", "stderr": ""}
        settings = {"stream_enabled": True, "rtsp_url": "rtsp://127.0.0.1:8554/yari-video", "encoding": "mjpeg", "fps": 15, "foxglove_topic": "/camera/image_raw/compressed", "atlas_webrtc_enabled": True, "atlas_camera_topic": "/camera/image_raw/compressed", "atlas_max_video_fps": 10}
        targets = self.module.video_stream_targets(settings)
        self.assertTrue(targets["foxglove"]["ready"])
        self.assertTrue(targets["atlas_webrtc"]["ready"])

    def test_video_preview_status_exposes_snapshot_endpoint(self):
        self.module.has_command = lambda name: name == "ffmpeg"
        status = self.module.video_preview_status({"device": "/dev/video0"}, ["/dev/video0"])
        self.assertTrue(status["supported"])
        self.assertEqual(status["endpoint"], "/api/video/snapshot")

    def test_capture_video_snapshot_requires_camera(self):
        self.module.has_command = lambda name: True
        with self.assertRaises(ValueError):
            self.module.capture_video_snapshot()

    def test_cleanup_data_logs_requires_known_candidates_and_confirm(self):
        self.module.MCAP_DIR.mkdir(parents=True, exist_ok=True)
        log = self.module.MCAP_DIR / "sample.mcap"
        log.write_text("bag")
        preview = self.module.cleanup_data_logs({"confirm": False})
        self.assertTrue(preview["dry_run"])
        self.assertTrue(log.exists())
        with self.assertRaises(ValueError):
            self.module.cleanup_data_logs({"paths": ["/tmp/not-a-yari-log"], "confirm": True})
        result = self.module.cleanup_data_logs({"paths": [str(log)], "confirm": True})
        self.assertFalse(result["dry_run"])
        self.assertFalse(log.exists())



    def test_queue_flight_log_download_and_retry(self):
        queued = self.module.queue_flight_log_download({"log_id": "7", "endpoint_name": "fc"})
        self.assertEqual(queued["item"]["log_id"], 7)
        self.assertEqual(queued["item"]["status"], "queued")
        item = queued["item"]
        item["status"] = "failed"
        self.module.write_flight_log_downloads([item])
        retried = self.module.retry_flight_log_downloads({})
        self.assertEqual(retried["downloads"]["items"][0]["status"], "queued")

    def test_upload_queue_enqueue_retry_and_clear(self):
        self.module.MCAP_DIR.mkdir(parents=True, exist_ok=True)
        log = self.module.MCAP_DIR / "upload.mcap"
        log.write_text("bag")
        result = self.module.enqueue_uploads({"paths": [str(log)]})
        self.assertEqual(len(result["added"]), 1)
        self.assertEqual(result["added"][0]["status"], "queued")
        item = result["added"][0]
        item["status"] = "failed"
        self.module.write_upload_queue([item])
        retry = self.module.retry_uploads({})
        self.assertEqual(retry["queue"]["items"][0]["status"], "queued")
        item = retry["queue"]["items"][0]
        item["status"] = "uploaded"
        self.module.write_upload_queue([item])
        cleared = self.module.clear_upload_queue({"keep_failed": True})
        self.assertEqual(cleared["queue"]["items"], [])


    def test_ota_status_reports_mender_and_local_artifacts(self):
        self.module.OTA_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        artifact = self.module.OTA_ARTIFACT_DIR / "update.mender"
        artifact.write_text("artifact")
        (self.module.OTA_ARTIFACT_DIR / "ignore.txt").write_text("ignore")
        status = self.module.ota_status()
        self.assertTrue(status["supported"])
        self.assertEqual(status["engine"], "mender")
        self.assertFalse(status["mender"]["available"])
        self.assertEqual(status["artifacts"][0]["name"], "update.mender")
        self.assertEqual(status["state"]["state"], "idle")

    def test_ota_config_defaults_and_save_policy(self):
        status = self.module.ota_status()
        self.assertEqual(status["config"]["release_channel"], "stable")
        self.assertTrue(status["config"]["auto_check"])
        result = self.module.save_ota_config({
            "release_channel": "beta",
            "auto_check": True,
            "auto_download": True,
            "auto_install": False,
            "require_signed_artifacts": True,
            "atlas_assignment_url": "https://atlas.example/api/v1/updates/assignment",
        })
        self.assertTrue(result["ok"])
        self.assertEqual(result["config"]["release_channel"], "beta")
        self.assertEqual(oct(self.module.OTA_CONFIG_FILE.stat().st_mode & 0o777), "0o600")
        saved = json.loads(self.module.OTA_CONFIG_FILE.read_text())
        self.assertEqual(saved["atlas_assignment_url"], "https://atlas.example/api/v1/updates/assignment")
        self.assertEqual(self.module.ota_status()["config"]["release_channel"], "beta")

    def test_ota_config_rejects_invalid_or_unsafe_policy(self):
        with self.assertRaises(ValueError):
            self.module.save_ota_config({"release_channel": "nightly"})
        with self.assertRaises(ValueError):
            self.module.save_ota_config({"release_channel": "dev", "auto_install": True, "require_signed_artifacts": False})

    def test_install_ota_artifact_requires_confirm_mender_and_safe_path(self):
        self.module.OTA_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        artifact = self.module.OTA_ARTIFACT_DIR / "update.mender"
        artifact.write_text("artifact")
        with self.assertRaises(ValueError):
            self.module.install_ota_artifact({"path": "update.mender"})
        with self.assertRaises(ValueError):
            self.module.install_ota_artifact({"path": "update.mender", "confirm": True})
        self.module.has_command = lambda name: name in {"nmcli", "mender"}
        with self.assertRaises(ValueError):
            self.module.install_ota_artifact({"path": "../outside.mender", "confirm": True})

    def test_install_ota_artifact_runs_mender_for_confirmed_artifact(self):
        self.module.has_command = lambda name: name in {"nmcli", "mender"}
        self.module.OTA_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        artifact = self.module.OTA_ARTIFACT_DIR / "update.mender"
        artifact.write_text("artifact")
        result = self.module.install_ota_artifact({"path": "update.mender", "confirm": True})
        self.assertTrue(result["ok"])
        self.assertEqual(result["state"]["state"], "installed-reboot-required")
        self.assertIn(["mender", "install", str(artifact.resolve())], self.commands)
        saved = json.loads(self.module.OTA_STATE_FILE.read_text())
        self.assertEqual(saved["artifact"], str(artifact.resolve()))

    def test_portal_version_reports_missing_svelte_build_metadata(self):
        version = self.module.portal_version()
        self.assertEqual(version["frontend_stack"], "svelte-build-missing")

    def test_portal_version_reads_built_metadata(self):
        self.module.PORTAL_VERSION_FILE.write_text('{"name":"yari-os-device-portal","version":"0.1.0","build_time":"now","git_commit":"abc123","frontend_stack":"svelte-typescript-vite"}')
        version = self.module.portal_version()
        self.assertEqual(version["frontend_stack"], "svelte-typescript-vite")
        self.assertEqual(version["git_commit"], "abc123")

    def test_portal_api_auth_is_optional_and_accepts_token_headers(self):
        self.module.PORTAL_API_TOKEN = ""
        self.assertTrue(self.module.request_authorized({}))
        self.assertTrue(self.module.support_bundle_authorized({}))
        self.assertTrue(self.module.sensitive_media_authorized({}))
        self.module.PORTAL_API_TOKEN = "secret-token"
        self.assertTrue(self.module.portal_version()["api_token_required"])
        self.assertFalse(self.module.request_authorized({}))
        self.assertFalse(self.module.request_authorized({"x-yari-token": "wrong"}))
        self.assertFalse(self.module.support_bundle_authorized({}))
        self.assertFalse(self.module.support_bundle_authorized({"x-yari-token": "wrong"}))
        self.assertFalse(self.module.sensitive_media_authorized({}))
        self.assertFalse(self.module.sensitive_media_authorized({"x-yari-token": "wrong"}))
        self.assertTrue(self.module.request_authorized({"x-yari-token": "secret-token"}))
        self.assertTrue(self.module.request_authorized({"authorization": "Bearer secret-token"}))
        self.assertTrue(self.module.support_bundle_authorized({"x-yari-token": "secret-token"}))
        self.assertTrue(self.module.support_bundle_authorized({"authorization": "Bearer secret-token"}))
        self.assertTrue(self.module.sensitive_media_authorized({"x-yari-token": "secret-token"}))
        self.assertTrue(self.module.sensitive_media_authorized({"authorization": "Bearer secret-token"}))

    def test_network_diagnostics_reports_core_sections(self):
        diagnostics = self.module.network_diagnostics()
        self.assertIn("checks", diagnostics)
        self.assertIn("networkmanager", diagnostics)
        self.assertIn("recent_clues", diagnostics["networkmanager"])

    def test_logs_status_describes_support_bundle(self):
        status = self.module.logs_status()
        self.assertEqual(status["support_bundle_endpoint"], "/api/logs/support-bundle")
        self.assertEqual(status["support_bundle"]["format"], "tar.gz")
        self.assertIn("redacted", status["support_bundle"]["redaction"])
        self.assertIn("onboarding", status["sources"])
        self.assertIn("system", status["sources"])

    def test_support_bundle_contains_status_files(self):
        self.module.PORTAL_CONFIG_FILE.write_text('{"atlas_token":"secret","device_profile":{"vehicle_class":"ground_rover"}}')
        self.module.PORTAL_ASSETS_FILE.write_text('{"asset_count":1,"assets":[{"path":"index.html","bytes":10,"sha256":"abc","gzip":false}]}')
        bundle = self.module.support_bundle()
        self.assertTrue(bundle.exists())
        self.assertEqual(bundle.suffixes[-2:], [".tar", ".gz"])
        with tarfile.open(bundle, "r:gz") as archive:
            names = set(archive.getnames())
        self.assertIn("manifest.json", names)
        self.assertIn("device-status.json", names)
        self.assertIn("network-status.json", names)
        self.assertIn("network-diagnostics.json", names)
        self.assertIn("logs/onboarding.log", names)
        self.assertIn("apps/ros2-manager.json", names)
        self.assertIn("apps/yari-atlas-agent.json", names)
        self.assertIn("apps.json", names)
        self.assertIn("ota-status.json", names)
        self.assertIn("portal-version.json", names)
        self.assertIn("portal-assets.json", names)
        self.assertIn("config/device-portal-config.json", names)
        self.assertIn("config/network-policy.json", names)
        self.assertIn("config/ota-config.json", names)
        with tarfile.open(bundle, "r:gz") as archive:
            manifest = json.loads(archive.extractfile("manifest.json").read().decode("utf-8"))
            portal_config = json.loads(archive.extractfile("config/device-portal-config.json").read().decode("utf-8"))
        self.assertEqual(manifest["schema_version"], "1")
        self.assertEqual(manifest["format"], "tar.gz")
        self.assertIn("redacted", manifest["redaction"])
        self.assertIn("device-status.json", manifest["status_snapshots"])
        self.assertIn("config/device-portal-config.json", manifest["config_snapshots"])
        self.assertIn("logs/onboarding.log", manifest["logs"])
        self.assertIn("portal", manifest)
        self.assertNotEqual(portal_config["atlas_token"], "secret")
        self.assertTrue(portal_config["atlas_token"]["configured"])


if __name__ == "__main__":
    unittest.main()


