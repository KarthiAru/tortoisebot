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
        with self.assertRaises(ValueError):
            self.module.write_mavlink_endpoints({"endpoints": [{"name": "bad", "type": "shell"}]})

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


if __name__ == "__main__":
    unittest.main()
