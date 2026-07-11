#!/usr/bin/env python3
import json
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_SCRIPT = REPO_ROOT / "yari-onboarding" / "scripts" / "yari-package-app"
ONBOARDING_SCRIPT = REPO_ROOT / "yari-onboarding" / "scripts" / "yari-onboarding"


class YariPackageAppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.manifest_path = self.root / "camera-streamer.json"
        self.manifest = {
            "schema_version": "1",
            "id": "camera-streamer",
            "name": "Camera Streamer",
            "version": "0.1.0",
            "runtime": "container",
            "container": {"image": "registry.yari.io/yari/camera-streamer:0.1.0"},
            "permissions": ["camera.read"],
        }
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_package_app(self, *args):
        return subprocess.run(
            ["python3", str(PACKAGE_SCRIPT), *map(str, args)],
            text=True,
            capture_output=True,
            check=False,
        )

    def read_package(self, path):
        with tarfile.open(path, "r:*") as archive:
            manifest = json.loads(archive.extractfile("manifest.json").read().decode("utf-8"))
            metadata = json.loads(archive.extractfile("yari-package.json").read().decode("utf-8"))
        return manifest, metadata

    def test_build_unsigned_yariapp_package(self):
        output_dir = self.root / "packages"
        result = self.run_package_app(self.manifest_path, "--output-dir", output_dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        package_path = Path(payload["path"])
        self.assertEqual(package_path.name, "camera-streamer-0.1.0.yariapp")
        self.assertTrue(package_path.exists())
        manifest, metadata = self.read_package(package_path)
        self.assertEqual(manifest, self.manifest)
        self.assertEqual(metadata["package_format"], "yari-app-package-v1")
        self.assertEqual(metadata["app_id"], "camera-streamer")
        self.assertEqual(metadata["app_version"], "0.1.0")
        self.assertEqual(metadata["manifest_sha256"], payload["manifest_sha256"])
        self.assertNotIn("signature", metadata)

    def test_refuses_to_overwrite_without_force(self):
        output = self.root / "camera.yariapp"
        first = self.run_package_app(self.manifest_path, "--output", output)
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.run_package_app(self.manifest_path, "--output", output)
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("Output already exists", second.stderr)
        forced = self.run_package_app(self.manifest_path, "--output", output, "--force")
        self.assertEqual(forced.returncode, 0, forced.stderr)

    @unittest.skipUnless(shutil.which("openssl"), "openssl is required for signed package round-trip")
    def test_build_signed_package_verifies_with_onboarding_backend(self):
        private_key = self.root / "app-private.pem"
        public_key = self.root / "app-public.pem"
        subprocess.run(["openssl", "genrsa", "-out", str(private_key), "2048"], check=True, capture_output=True)
        subprocess.run(["openssl", "rsa", "-in", str(private_key), "-pubout", "-out", str(public_key)], check=True, capture_output=True)
        output = self.root / "signed-camera.yariapp"
        result = self.run_package_app(
            self.manifest_path,
            "--output",
            output,
            "--sign-key",
            private_key,
            "--signed-by",
            "YARI Test",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest, metadata = self.read_package(output)
        self.assertEqual(manifest, self.manifest)
        self.assertEqual(metadata["signed_by"], "YARI Test")
        self.assertEqual(metadata["signature_type"], "sha256-rsa")
        self.assertTrue(metadata["signature"])
        verify = subprocess.run(
            [
                "env",
                f"YARI_APP_PACKAGE_DIR={self.root}",
                f"YARI_APP_PACKAGE_PUBLIC_KEY_FILE={public_key}",
                "python3",
                "-c",
                (
                    "import importlib.machinery, importlib.util, json;"
                    f"loader=importlib.machinery.SourceFileLoader('yari_onboarding','{ONBOARDING_SCRIPT}');"
                    "spec=importlib.util.spec_from_loader(loader.name,loader);"
                    "m=importlib.util.module_from_spec(spec);loader.exec_module(m);"
                    "p=m.read_app_package('"
                    + str(output)
                    + "');print(json.dumps(p['signature']))"
                ),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(verify.returncode, 0, verify.stderr)
        signature = json.loads(verify.stdout)
        self.assertTrue(signature["verified"])
        self.assertEqual(signature["status"], "verified")


if __name__ == "__main__":
    unittest.main()
