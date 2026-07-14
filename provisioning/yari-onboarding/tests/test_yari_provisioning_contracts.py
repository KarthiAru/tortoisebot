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


    def test_onboarding_service_gracefully_stops_managed_runtime_on_shutdown(self):
        unit_text = (REPO_ROOT / "yari-onboarding" / "systemd" / "yari-onboarding.service").read_text(encoding="utf-8")
        server_text = ONBOARDING_SERVER.read_text(encoding="utf-8")
        self.assertIn("ExecStop=/usr/local/sbin/yari-onboarding shutdown-stop", unit_text)
        self.assertIn("TimeoutStopSec=45", unit_text)
        self.assertIn("KillSignal=SIGINT", unit_text)
        self.assertIn('"shutdown-stop"', server_text)
        self.assertIn("def shutdown_stop", server_text)
        self.assertIn("stop_ros_launch_profile()", server_text)
        self.assertIn("stop_ros_recording()", server_text)
        self.assertIn("stop_atlas_bridge()", server_text)

    def test_security_status_has_persistent_portal_api_token_file(self):
        text = ONBOARDING_SERVER.read_text(encoding="utf-8")
        self.assertIn("PORTAL_API_TOKEN_FILE = Path", text)
        self.assertIn("portal-api-token.json", text)
        self.assertLess(text.index("PORTAL_API_TOKEN_FILE = Path"), text.index("def generated_portal_api_token"))
        self.assertIn("credential_file_status(PORTAL_API_TOKEN_FILE)", text)

    def test_tortoisebot_minimal_remote_profiles_keep_camera_mcap_and_disable_slam_navigation(self):
        server_text = ONBOARDING_SERVER.read_text(encoding="utf-8")
        portal_text = (REPO_ROOT / "yari-onboarding" / "portal" / "src" / "App.svelte").read_text(encoding="utf-8")
        service_manager_text = (REPO_ROOT / "yari-onboarding" / "scripts" / "yari-service-manager").read_text(encoding="utf-8")
        launch_text = (REPO_ROOT / ".." / "tortoisebot_bringup" / "launch" / "autobringup.launch.py").resolve().read_text(encoding="utf-8")
        self.assertIn("Minimal hardware + Atlas remote", server_text)
        self.assertIn("Minimal hardware + Foxglove remote", server_text)
        self.assertIn("record_mcap:=True enable_camera:=True", server_text)
        self.assertIn("enable_slam:=False enable_navigation:=False", server_text)
        self.assertIn("enable_foxglove_bridge:=False foxglove_remote_access:=False", server_text)
        self.assertIn("enable_foxglove_bridge:=True foxglove_remote_access:=True", server_text)
        self.assertIn("compressed/chunked MCAP logging", server_text)
        self.assertIn("--storage-config-file", server_text)
        self.assertIn("mcap_writer_options.yaml", server_text)
        self.assertIn("profile_by_name", server_text)
        self.assertIn("default_ros_launch_profiles(), payload", server_text)
        self.assertIn("tortoisebot-atlas-minimal", portal_text)
        self.assertIn("tortoisebot-foxglove-minimal", portal_text)
        self.assertNotIn("tortoisebot-hardware", portal_text)
        self.assertIn("tortoisebot-atlas-minimal", service_manager_text)
        self.assertIn("tortoisebot-foxglove-minimal", service_manager_text)
        self.assertIn("enable_slam = LaunchConfiguration('enable_slam')", launch_text)
        self.assertIn("enable_navigation = LaunchConfiguration('enable_navigation')", launch_text)
        self.assertIn("DeclareLaunchArgument('enable_slam'", launch_text)
        self.assertIn("DeclareLaunchArgument('enable_navigation'", launch_text)

    def test_atlas_bridge_defaults_to_camera_ros_compressed_topic(self):
        server_text = ONBOARDING_SERVER.read_text(encoding="utf-8")
        service_manager_text = (REPO_ROOT / "yari-onboarding" / "scripts" / "yari-service-manager").read_text(encoding="utf-8")
        portal_text = (REPO_ROOT / "yari-onboarding" / "portal" / "src" / "App.svelte").read_text(encoding="utf-8")
        self.assertIn("/camera/camera_node/image_raw/compressed", server_text)
        self.assertIn("/camera/camera_node/image_raw/compressed", service_manager_text)
        self.assertIn("/camera/camera_node/image_raw/compressed", portal_text)
        self.assertIn("foxglove_topic\": \"/camera/image_raw/compressed", server_text)
    def test_atlas_bridge_uses_persisted_vehicle_token_without_leaking_it_to_state(self):
        text = ONBOARDING_SERVER.read_text(encoding="utf-8")
        self.assertIn("portal_secrets = read_json_file(PORTAL_SECRETS_FILE, {})", text)
        self.assertIn("portal_secrets.get(\"atlas_token\")", text)
        self.assertIn("YARI_ATLAS_VEHICLE_TOKEN", text)
        self.assertIn("Atlas vehicle token is not configured", text)
        self.assertIn("vehicle_token_configured", text)
        self.assertIn("env=env", text)
        self.assertNotIn("vehicle_token:=", text)

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

    def test_portal_exposes_static_ip_controls(self):
        server_text = ONBOARDING_SERVER.read_text(encoding="utf-8")
        portal_text = (REPO_ROOT / "yari-onboarding" / "portal" / "src" / "App.svelte").read_text(encoding="utf-8")
        self.assertIn('if path == "/api/network/static-ip":', server_text)
        self.assertIn("save_static_ip_config(payload)", server_text)
        self.assertIn("Static IPv4", portal_text)
        self.assertIn("staticIpForm", portal_text)
        self.assertIn("/api/network/static-ip", portal_text)
        self.assertIn("Address / CIDR", portal_text)

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
