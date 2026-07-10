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
        self.module.MAVLINK_CONFIG_FILE = root / "mavlink.json"
        self.module.UPLOAD_QUEUE_FILE = root / "upload-queue.json"

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


if __name__ == "__main__":
    unittest.main()
