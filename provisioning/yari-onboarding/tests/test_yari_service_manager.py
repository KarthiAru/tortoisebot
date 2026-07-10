#!/usr/bin/env python3
import importlib.machinery
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "yari-service-manager"


def load_module():
    loader = importlib.machinery.SourceFileLoader("yari_service_manager", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class YariServiceManagerTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.module.STATE_DIR = root / "state"
        self.module.RUNTIME_DIR = root / "run"
        self.module.CONFIG_DIR = root / "config"
        self.module.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.module.PORTAL_CONFIG_FILE = self.module.CONFIG_DIR / "device-portal.json"
        self.module.PORTAL_SECRETS_FILE = self.module.CONFIG_DIR / "device-portal-secrets.json"
        self.module.MAVLINK_CONFIG_FILE = root / "mavlink.json"
        self.module.UPLOAD_QUEUE_FILE = root / "upload-queue.json"
        self.module.FLIGHT_LOG_DOWNLOADS_FILE = root / "flight-log-downloads.json"
        self.module.FLIGHT_LOG_DIR = root / "flight-logs"
        self.module.ONBOARDING_STATE_FILE = root / "onboarding-state.json"

    def test_write_mavlink_router_config_maps_serial_and_udp_endpoints(self):
        config = self.module.write_mavlink_router_config([
            {"name": "fc", "type": "serial", "device": "/dev/ttyACM0", "baud": 115200, "enabled": True},
            {"name": "qgc", "type": "udp", "host": "192.168.0.10", "port": 14550, "enabled": True},
        ])
        content = config.read_text()
        self.assertIn("[UartEndpoint autopilot]", content)
        self.assertIn("Device=/dev/ttyACM0", content)
        self.assertIn("Baud=115200", content)
        self.assertIn("[UdpEndpoint qgc]", content)
        self.assertIn("Address=192.168.0.10", content)

    def test_mavlink_router_status_reports_missing_router_without_failing(self):
        self.module.MAVLINK_CONFIG_FILE.write_text('{"endpoints":[{"name":"qgc","type":"udp","host":"127.0.0.1","port":14550,"enabled":true}]}')
        self.module.command_exists = lambda name: False
        status = self.module.mavlink_router_status()
        self.assertEqual(status["routing"], "configured")
        self.assertFalse(status["router_process"]["running"])
        self.assertIn("not installed", status["router_process"]["error"])
        self.assertTrue(Path(status["router_config"]).exists())

    def test_upload_queue_summary_marks_missing_queued_files(self):
        self.module.UPLOAD_QUEUE_FILE.write_text('{"items":[{"id":"one","path":"/tmp/definitely-missing-yari-log.mcap","status":"queued"}]}')
        summary = self.module.upload_queue_summary()
        self.assertEqual(summary["counts"]["missing"], 1)
        self.assertEqual(summary["items"][0]["status"], "missing")


    def test_probe_autopilot_reports_missing_pymavlink(self):
        self.module.import_mavutil = lambda: (None, "missing pymavlink")
        result = self.module.probe_autopilot([{"name": "fc", "type": "serial", "device": "/dev/ttyACM0", "enabled": True}])
        self.assertFalse(result["connected"])
        self.assertEqual(result["detection"], "pymavlink-missing")

    def test_probe_autopilot_decodes_heartbeat(self):
        class FakeHeartbeat:
            type = 2
            autopilot = 12
            base_mode = 128
            custom_mode = 0
            system_status = 4

        class FakeConnection:
            target_system = 1
            target_component = 1
            flightmode = "MANUAL"
            def wait_heartbeat(self, timeout=0):
                return FakeHeartbeat()
            def recv_match(self, blocking=False):
                return None
            def close(self):
                pass

        class FakeMavlink:
            MAV_MODE_FLAG_SAFETY_ARMED = 128

        class FakeMavutil:
            mavlink = FakeMavlink()
            def mavlink_connection(self, target, **kwargs):
                return FakeConnection()

        self.module.import_mavutil = lambda: (FakeMavutil(), None)
        result = self.module.probe_autopilot([{"name": "fc", "type": "serial", "device": "/dev/ttyACM0", "enabled": True}], timeout=0.1)
        self.assertTrue(result["connected"])
        self.assertEqual(result["flight_stack"], "PX4")
        self.assertEqual(result["mode"], "MANUAL")
        self.assertTrue(result["armed"])



    def test_list_remote_flight_logs_uses_log_entries(self):
        class FakeLogEntry:
            id = 4
            num_logs = 5
            last_log_num = 4
            time_utc = 123
            size = 456

        class FakeMav:
            def log_request_list_send(self, *args):
                self.requested = args

        class FakeConnection:
            target_system = 1
            target_component = 1
            mav = FakeMav()
            calls = 0
            def wait_heartbeat(self, timeout=0):
                return object()
            def recv_match(self, type=None, blocking=False, timeout=0):
                self.calls += 1
                return FakeLogEntry() if self.calls == 1 else None
            def close(self):
                pass

        class FakeMavutil:
            def mavlink_connection(self, target, **kwargs):
                return FakeConnection()

        self.module.import_mavutil = lambda: (FakeMavutil(), None)
        result = self.module.list_remote_flight_logs([{"name": "fc", "type": "serial", "device": "/dev/ttyACM0", "enabled": True}], timeout=0.1)
        self.assertTrue(result["ok"])
        self.assertEqual(result["logs"][0]["id"], 4)
        self.assertEqual(result["logs"][0]["size"], 456)

    def test_video_pipeline_args_builds_rtsp_ffmpeg_command(self):
        args = self.module.video_pipeline_args({"fps": 10, "encoding": "h264", "size": "320x240", "rtsp_url": "rtsp://127.0.0.1:8554/test"}, "/dev/video0")
        self.assertEqual(args[0], "ffmpeg")
        self.assertIn("/dev/video0", args)
        self.assertIn("rtsp://127.0.0.1:8554/test", args)
        self.assertIn("libx264", args)

    def test_start_video_stream_reports_disabled_and_missing_ffmpeg(self):
        disabled = self.module.start_video_stream({"stream_enabled": False}, ["/dev/video0"])
        self.assertEqual(disabled["state"], "disabled")
        self.module.command_exists = lambda name: False
        missing = self.module.start_video_stream({"stream_enabled": True}, ["/dev/video0"])
        self.assertEqual(missing["state"], "ffmpeg-missing")

    def test_video_status_reports_stream_targets(self):
        self.module.command = lambda args, timeout=8: {"ok": True, "stdout": "/camera/image_raw/compressed [sensor_msgs/msg/CompressedImage]", "stderr": "", "returncode": 0} if "ros2 topic list" in " ".join(args) else {"ok": False, "stdout": "", "stderr": "missing", "returncode": 1}
        (self.module.CONFIG_DIR / "video.json").write_text('{"foxglove_topic":"/camera/image_raw/compressed","atlas_webrtc_enabled":true,"atlas_camera_topic":"/camera/image_raw/compressed","stream_enabled":false}')
        self.module.PORTAL_CONFIG_FILE.write_text('{"atlas_url":"http://atlas/api/v1"}')
        self.module.PORTAL_SECRETS_FILE.write_text('{"atlas_token":"token"}')
        status = self.module.video_status()
        self.assertEqual(status["stream"]["state"], "disabled")
        self.assertTrue(status["stream_targets"]["foxglove"]["ready"])
        self.assertTrue(status["stream_targets"]["atlas_webrtc"]["ready"])



    def test_agent_status_reports_remote_access_and_telemetry(self):
        secrets = Path(self.tmp.name) / "secrets.json"
        config = Path(self.tmp.name) / "portal.json"
        secrets.write_text('{"atlas_token":"secret","foxglove_token":"fox"}')
        config.write_text('{"atlas_url":"http://atlas/api/v1","device_id":"dev-1"}')
        self.module.ONBOARDING_STATE_FILE.write_text('{"mode":"client","device_id":"state-dev"}')
        old_secrets = self.module.os.environ.get("YARI_PORTAL_SECRETS_FILE")
        old_config = self.module.os.environ.get("YARI_PORTAL_CONFIG_FILE")
        self.module.os.environ["YARI_PORTAL_SECRETS_FILE"] = str(secrets)
        self.module.os.environ["YARI_PORTAL_CONFIG_FILE"] = str(config)
        try:
            status = self.module.agent_status()
        finally:
            if old_secrets is None:
                self.module.os.environ.pop("YARI_PORTAL_SECRETS_FILE", None)
            else:
                self.module.os.environ["YARI_PORTAL_SECRETS_FILE"] = old_secrets
            if old_config is None:
                self.module.os.environ.pop("YARI_PORTAL_CONFIG_FILE", None)
            else:
                self.module.os.environ["YARI_PORTAL_CONFIG_FILE"] = old_config
        self.assertTrue(status["remote_access"]["atlas"]["ready"])
        self.assertTrue(status["remote_access"]["foxglove"]["ready"])
        self.assertEqual(status["telemetry"]["device_id"], "dev-1")
        self.assertIn("ip_addresses", status["telemetry"])

    def test_process_upload_queue_waits_for_atlas_config(self):
        self.module.write_upload_queue([{"id": "one", "path": "/tmp/missing.mcap", "status": "queued"}])
        result = self.module.process_upload_queue({}, {})
        self.assertEqual(result["state"], "waiting-for-atlas-config")
        self.assertFalse(result["token_configured"])

    def test_process_upload_queue_marks_successful_upload(self):
        log = Path(self.tmp.name) / "sample.mcap"
        log.write_text("bag")
        self.module.write_upload_queue([{"id": "one", "path": str(log), "status": "queued", "kind": "mcap"}])
        calls = []
        def fake_upload(url, token, file_path, metadata, timeout=30):
            calls.append((url, token, file_path, metadata))
            return {"status": 201, "body": "ok"}
        self.module.multipart_upload = fake_upload
        result = self.module.process_upload_queue({"atlas_url": "http://atlas/api/v1"}, {"atlas_token": "secret"})
        self.assertEqual(result["items"][0]["status"], "uploaded")
        self.assertEqual(calls[0][0], "http://atlas/api/v1/logs/upload")
        self.assertEqual(calls[0][1], "secret")

    def test_process_upload_queue_marks_missing_files(self):
        self.module.write_upload_queue([{"id": "one", "path": "/tmp/definitely-missing-upload.mcap", "status": "queued"}])
        result = self.module.process_upload_queue({"atlas_upload_url": "http://atlas/upload"}, {"atlas_token": "secret"})
        self.assertEqual(result["items"][0]["status"], "missing")


if __name__ == "__main__":
    unittest.main()
