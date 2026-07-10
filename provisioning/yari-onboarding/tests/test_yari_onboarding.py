#!/usr/bin/env python3
import importlib.machinery
import importlib.util
import os
import tempfile
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
        self.module.VIDEO_CONFIG_FILE = root / "video.json"
        self.module.ROS_RECORDING_CONFIG_FILE = root / "ros-recording.json"
        self.module.ROS_RECORDING_PID_FILE = root / "ros-record.pid"
        self.module.ROS_RECORDING_LOG_FILE = root / "ros-record.log"
        self.module.MCAP_DIR = root / "mcap"
        self.module.UPLOAD_QUEUE_FILE = root / "upload-queue.json"
        self.module.DEVICE_ID_FILE = root / "device-id"
        self.module.SUPPORT_BUNDLE_DIR = root / "bundles"
        self.module.SERVICE_STATE_DIR = root / "services"
        self.module.APPLY_NETWORK = False
        self.commands = []
        self.module.run = self.fake_run
        self.module.has_command = lambda name: name == "nmcli"
        self.module.os.chown = lambda path, uid, gid: None

    def fake_run(self, args, check=False, capture=True):
        self.commands.append(args)
        class Result:
            returncode = 0
            stdout = ""
            stderr = ""
        return Result()

    def test_normalize_form_value_strips_accidental_wrapping_quotes(self):
        self.assertEqual(self.module.normalize_form_value('"Brindavan"'), "Brindavan")
        self.assertEqual(self.module.normalize_form_value("'secret'"), "secret")
        self.assertEqual(self.module.normalize_form_value('pa"ss'), 'pa"ss')

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
        state = self.module.factory_reset(reboot=False)
        self.assertFalse(self.module.COMPLETE_FILE.exists())
        self.assertFalse((self.module.NM_CONNECTION_DIR / "yari-wifi.nmconnection").exists())
        self.assertFalse((self.module.NETPLAN_DIR / "01-yari-wifi.yaml").exists())
        self.assertFalse(state["complete"])

    def test_save_pairing_tokens_redacts_status_and_writes_secret_file(self):
        status = self.module.save_pairing_tokens("atlas-secret", "fox-secret")
        self.assertTrue(self.module.PORTAL_SECRETS_FILE.exists())
        self.assertEqual(oct(self.module.PORTAL_SECRETS_FILE.stat().st_mode & 0o777), "0o600")
        self.assertTrue(status["atlas_token"]["configured"])
        self.assertNotIn("atlas-secret", str(status))

    def test_regenerate_device_id_writes_override(self):
        state = self.module.regenerate_device_id()
        self.assertTrue(self.module.DEVICE_ID_FILE.exists())
        self.assertEqual(state["device_id"], self.module.DEVICE_ID_FILE.read_text().strip())

    def test_network_status_includes_phase_one_placeholders(self):
        status = self.module.network_status()
        self.assertIn("static_ip", status["config"])
        self.assertIn("lte", status["config"])


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


    def test_save_video_settings_validates_and_persists(self):
        settings = self.module.save_video_settings({"fps": "20", "encoding": "mono8", "bandwidth_kbps": "512"})
        self.assertEqual(settings["fps"], 20)
        self.assertEqual(settings["encoding"], "mono8")
        self.assertTrue(self.module.VIDEO_CONFIG_FILE.exists())
        with self.assertRaises(ValueError):
            self.module.save_video_settings({"fps": "0", "encoding": "mjpeg"})

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

    def test_support_bundle_contains_status_files(self):
        bundle = self.module.support_bundle()
        self.assertTrue(bundle.exists())
        self.assertEqual(bundle.suffixes[-2:], [".tar", ".gz"])


if __name__ == "__main__":
    unittest.main()
