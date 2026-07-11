#!/usr/bin/env python3
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install_tortoisebot_humble.sh"
IMAGE_SCRIPT = REPO_ROOT / "scripts" / "build_tortoisebot_image.sh"
ONBOARDING_INSTALLER = REPO_ROOT / "yari-onboarding" / "scripts" / "install-yari-onboarding"
PORTAL_BUILD_HELPER = REPO_ROOT / "yari-onboarding" / "scripts" / "build-yari-portal"
ONBOARDING_SERVER = REPO_ROOT / "yari-onboarding" / "scripts" / "yari-onboarding"


def apt_install_packages(script_text):
    match = re.search(r"apt-get install -y \\\n(?P<body>.*?)(?:\n\n|\n[a-zA-Z_][a-zA-Z0-9_]+\(\))", script_text, re.S)
    if not match:
        return set()
    packages = set()
    for raw_line in match.group("body").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        packages.add(line.rstrip("\\").strip())
    return packages


class TortoiseBotProvisioningContractTests(unittest.TestCase):
    def test_dependency_installer_installs_node_for_svelte_portal_builds(self):
        packages = apt_install_packages(INSTALL_SCRIPT.read_text(encoding="utf-8"))
        self.assertIn("nodejs", packages)
        self.assertIn("network-manager", packages)
        self.assertIn("avahi-daemon", packages)

    def test_generated_first_run_installer_refreshes_yari_portal_before_heavy_sentinel_exit(self):
        text = IMAGE_SCRIPT.read_text(encoding="utf-8")
        dependency_call = 'bash "\\${REPO_DIR}/provisioning/scripts/install_tortoisebot_humble.sh"'
        portal_installer = 'bash "\\${REPO_DIR}/provisioning/yari-onboarding/scripts/install-yari-onboarding"'
        sentinel_check = 'if [[ -f "\\${SENTINEL}" ]]; then'
        self.assertIn(dependency_call, text)
        self.assertIn(portal_installer, text)
        self.assertIn(sentinel_check, text)
        self.assertLess(text.index(portal_installer), text.index(sentinel_check))
        self.assertLess(text.index(sentinel_check), text.index(dependency_call))
        self.assertLess(text.index(dependency_call), text.index('touch "\\${REPO_DIR}/YDLidar-SDK/COLCON_IGNORE"'))

    def test_onboarding_installer_requires_optimized_svelte_dist_before_deploy(self):
        text = ONBOARDING_INSTALLER.read_text(encoding="utf-8")
        self.assertIn("validate_portal_dist", text)
        self.assertIn("${PORTAL_DIST}/portal-version.json", text)
        self.assertIn("${PORTAL_DIST}/portal-assets.json", text)
        self.assertIn("portal_gzip_assets=", text)
        self.assertIn("precompressed assets missing", text)
        ensure_call = text.rindex("ensure_portal_dist")
        validate_call = text.rindex("if ! validate_portal_dist")
        copy_call = text.index("cp -a \"${PORTAL_DIST}/.\" /opt/yari/onboarding/web/")
        self.assertLess(ensure_call, validate_call)
        self.assertLess(validate_call, copy_call)

    def test_onboarding_installer_accepts_checked_in_svelte_dist_after_git_pull(self):
        text = ONBOARDING_INSTALLER.read_text(encoding="utf-8")
        self.assertIn("portal_dist_stale", text)
        self.assertIn("YARI_PORTAL_FORCE_BUILD", text)
        self.assertIn("YARI_PORTAL_BUILD_ON_DEVICE", text)
        self.assertIn("Build it on a development machine first", text)
        self.assertIn("Do not compare source/dist mtimes", text)
        self.assertIn("Use YARI_PORTAL_FORCE_BUILD=1 for an explicit rebuild", text)
        self.assertNotIn("-newer \"${PORTAL_DIST}/portal-version.json\"", text)
        self.assertNotIn("source_paths", text)
        self.assertIn("Building Svelte YARI OS portal", text)
        self.assertLess(text.index("portal_dist_stale"), text.index("ensure_portal_dist"))
        self.assertLess(text.index("YARI_PORTAL_BUILD_ON_DEVICE"), text.index("if ! install_node20_build_tools"))

    def test_onboarding_installer_refreshes_nodesource_keyring_before_opt_in_node_install(self):
        text = ONBOARDING_INSTALLER.read_text(encoding="utf-8")
        self.assertIn("YARI_PORTAL_BUILD_ON_DEVICE", text)
        self.assertIn("rm -f /etc/apt/sources.list.d/nodesource.list", text)
        self.assertIn("rm -f /etc/apt/keyrings/nodesource.gpg", text)
        self.assertIn("gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg", text)
        self.assertIn("chmod 0644 /etc/apt/keyrings/nodesource.gpg", text)
        self.assertLess(text.index("rm -f /etc/apt/sources.list.d/nodesource.list"), text.index("apt-get install -y ca-certificates curl gnupg"))
        self.assertLess(text.index("gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg"), text.index("apt-get install -y nodejs"))

    def test_portal_build_helper_is_reproducible_and_metadata_checked(self):
        text = PORTAL_BUILD_HELPER.read_text(encoding="utf-8")
        self.assertIn("npm ci", text)
        self.assertIn("npm run build", text)
        self.assertIn("package-lock.json", text)
        self.assertIn("portal-version.json", text)
        self.assertIn("portal-assets.json", text)
        self.assertIn("precompressed .gz assets", text)

    def test_portal_build_helper_rejects_windows_node_from_wsl(self):
        text = PORTAL_BUILD_HELPER.read_text(encoding="utf-8")
        self.assertIn("is_windows_mount_path", text)
        self.assertIn("/mnt/[a-zA-Z]/*", text)
        self.assertIn("Detected Windows Node/npm on PATH while building from WSL", text)
        self.assertIn("Install Linux Node.js", text)
        self.assertLess(text.index("windows_node_hint"), text.index("command -v node"))

    def test_image_builder_and_installer_use_shared_portal_build_helper(self):
        image_text = IMAGE_SCRIPT.read_text(encoding="utf-8")
        installer_text = ONBOARDING_INSTALLER.read_text(encoding="utf-8")
        self.assertIn("build-yari-portal", image_text)
        self.assertIn("build-yari-portal", installer_text)
        self.assertIn("/usr/local/bin/build-yari-portal", installer_text)


    def test_ros_launch_and_bridge_run_as_onboarding_user_and_expose_logs(self):
        text = ONBOARDING_SERVER.read_text(encoding="utf-8")
        self.assertIn("def user_shell_command", text)
        self.assertIn('return ["runuser", "-u", user, "--", "bash", "-lc", inner]', text)
        self.assertIn("export HOME=", text)
        self.assertIn("USER=", text)
        self.assertIn("subprocess.Popen(user_shell_command(shell_cmd)", text)
        self.assertIn('if source == "ros-launch":', text)
        self.assertIn("tail_file_log(source, ROS_LAUNCH_LOG_FILE, lines)", text)
        self.assertIn('if source == "atlas-bridge":', text)
        self.assertIn("tail_file_log(source, ATLAS_BRIDGE_LOG_FILE, lines)", text)

    def test_tortoisebot_portal_endpoints_are_wired_to_http_handler(self):
        text = ONBOARDING_SERVER.read_text(encoding="utf-8")
        self.assertIn('if path == "/api/tortoisebot/status":', text)
        self.assertIn('self.send_json(200, tortoisebot_status())', text)
        self.assertIn('if path == "/api/tortoisebot/operation":', text)
        self.assertIn('self.send_json(200, run_tortoisebot_operation(payload))', text)
        self.assertIn('if path == "/api/tortoisebot/atlas-bridge":', text)
        self.assertIn('start_atlas_bridge(payload)', text)
        self.assertIn('stop_atlas_bridge()', text)

    def test_image_builder_copies_prebuilt_portal_into_rootfs(self):
        text = IMAGE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("build_yari_portal", text)
        self.assertIn("portal_dist=", text)
        self.assertIn("${portal_dist}/index.html", text)
        self.assertIn("${portal_dist}/portal-version.json", text)
        self.assertIn("${portal_dist}/portal-assets.json", text)
        self.assertIn("portal_gzip_assets=", text)
        self.assertIn("precompressed assets missing", text)
        self.assertIn("${ROOT_MOUNT}/opt/yari/onboarding/web/", text)
        self.assertIn("multi-user.target.wants/yari-onboarding.service", text)


if __name__ == "__main__":
    unittest.main()
