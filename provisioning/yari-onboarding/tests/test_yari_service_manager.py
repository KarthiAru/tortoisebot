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


if __name__ == "__main__":
    unittest.main()
