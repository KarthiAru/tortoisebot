#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROVISIONING_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${PROVISIONING_DIR}/.." && pwd)"

CONFIG_FILE="${PROVISIONING_DIR}/config/tortoisebot-image.local.env"
DEVICE=""
FORCE_DOWNLOAD=0
SKIP_DOWNLOAD=0
KEEP_MOUNTS=0

usage() {
  cat <<USAGE
Usage: sudo bash provisioning/scripts/build_tortoisebot_image.sh [options]

Build a TortoiseBot Ubuntu Raspberry Pi image on Ubuntu/Linux by editing the
image root filesystem directly. This replaces the deprecated Windows SD flow.

Options:
  --config PATH       Config env file. Default: provisioning/config/tortoisebot-image.local.env
  --device /dev/sdX   Also flash the finished image to this removable device.
  --force-download    Re-download and re-expand the base Ubuntu image.
  --skip-download     Use an already expanded image from CACHE_DIR.
  --keep-mounts       Leave mounts attached for debugging on failure.
  -h, --help          Show this help.

Example:
  cp provisioning/config/tortoisebot-image.example.env provisioning/config/tortoisebot-image.local.env
  nano provisioning/config/tortoisebot-image.local.env
  sudo bash provisioning/scripts/build_tortoisebot_image.sh
  sudo bash provisioning/scripts/build_tortoisebot_image.sh --device /dev/sdX
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      CONFIG_FILE="$2"
      shift 2
      ;;
    --device)
      DEVICE="$2"
      shift 2
      ;;
    --force-download)
      FORCE_DOWNLOAD=1
      shift
      ;;
    --skip-download)
      SKIP_DOWNLOAD=1
      shift
      ;;
    --keep-mounts)
      KEEP_MOUNTS=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo so loop mounts preserve Linux ownership and permissions." >&2
  exit 1
fi

if [[ ! -f "${CONFIG_FILE}" ]]; then
  echo "Missing config: ${CONFIG_FILE}" >&2
  echo "Copy provisioning/config/tortoisebot-image.example.env to tortoisebot-image.local.env first." >&2
  exit 1
fi

# shellcheck source=/dev/null
source "${CONFIG_FILE}"

: "${WIFI_SSID:?Set WIFI_SSID in ${CONFIG_FILE}}"
: "${WIFI_PASSWORD:?Set WIFI_PASSWORD in ${CONFIG_FILE}}"
: "${HOSTNAME:=tortoisebot}"
: "${USERNAME:=tortoisebot}"
: "${USER_PASSWORD:=raspberry}"
: "${REPO_URL:=https://github.com/KarthiAru/tortoisebot.git}"
: "${REPO_BRANCH:=mcap-logging}"
: "${IMAGE_URL:=https://cdimage.ubuntu.com/releases/22.04/release/ubuntu-22.04.5-preinstalled-server-arm64+raspi.img.xz}"
: "${CACHE_DIR:=${HOME}/.cache/tortoisebot}"
: "${OUTPUT_DIR:=${REPO_ROOT}/provisioning/output}"
: "${MAX_DEVICE_SIZE_GB:=128}"

info() {
  echo "==> $*"
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

need() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command '$1'. Install it and retry."
}

need curl
need xz
need losetup
need findmnt
need mount
need umount
need openssl
need lsblk

IMAGE_NAME="$(basename "${IMAGE_URL}")"
XZ_PATH="${CACHE_DIR}/${IMAGE_NAME}"
BASE_IMG_PATH="${CACHE_DIR}/${IMAGE_NAME%.xz}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUTPUT_IMG_PATH="${OUTPUT_DIR}/tortoisebot-ubuntu-22.04-humble-${STAMP}.img"
ROOT_MOUNT=""
BOOT_MOUNT=""
LOOP_DEV=""

cleanup() {
  local status=$?
  if [[ "${KEEP_MOUNTS}" -eq 1 && "${status}" -ne 0 ]]; then
    echo "Keeping mounts for debugging:"
    echo "  root: ${ROOT_MOUNT}"
    echo "  boot: ${BOOT_MOUNT}"
    echo "  loop: ${LOOP_DEV}"
    exit "${status}"
  fi
  if [[ -n "${BOOT_MOUNT}" ]] && findmnt -rno TARGET "${BOOT_MOUNT}" >/dev/null 2>&1; then
    umount "${BOOT_MOUNT}" || true
  fi
  if [[ -n "${ROOT_MOUNT}" ]] && findmnt -rno TARGET "${ROOT_MOUNT}" >/dev/null 2>&1; then
    umount "${ROOT_MOUNT}" || true
  fi
  if [[ -n "${LOOP_DEV}" ]]; then
    losetup -d "${LOOP_DEV}" || true
  fi
  [[ -n "${BOOT_MOUNT}" ]] && rmdir "${BOOT_MOUNT}" 2>/dev/null || true
  [[ -n "${ROOT_MOUNT}" ]] && rmdir "${ROOT_MOUNT}" 2>/dev/null || true
  exit "${status}"
}
trap cleanup EXIT

read_public_key() {
  if [[ -n "${SSH_AUTHORIZED_KEY:-}" ]]; then
    printf '%s\n' "${SSH_AUTHORIZED_KEY}"
    return
  fi
  local key_path="${SUDO_USER:+/home/${SUDO_USER}/.ssh/id_ed25519.pub}"
  if [[ -n "${key_path}" && -f "${key_path}" ]]; then
    cat "${key_path}"
    return
  fi
  if [[ -f "${HOME}/.ssh/id_ed25519.pub" ]]; then
    cat "${HOME}/.ssh/id_ed25519.pub"
    return
  fi
  die "No SSH public key found. Set SSH_AUTHORIZED_KEY in ${CONFIG_FILE}."
}


next_id() {
  local file="$1"
  local field="$2"
  local minimum="$3"
  awk -F: -v field="${field}" -v minimum="${minimum}" '
    BEGIN { max = minimum - 1 }
    $field ~ /^[0-9]+$/ && $field > max { max = $field }
    END { print max + 1 }
  ' "${file}"
}

ensure_group() {
  local root="$1"
  local group="$2"
  local gid="${3:-}"
  local group_file="${root}/etc/group"
  local gshadow_file="${root}/etc/gshadow"

  if grep -q "^${group}:" "${group_file}"; then
    return
  fi

  if [[ -z "${gid}" ]]; then
    gid="$(next_id "${group_file}" 3 1000)"
  fi

  printf '%s:x:%s:\n' "${group}" "${gid}" >> "${group_file}"
  if [[ -f "${gshadow_file}" ]]; then
    printf '%s:!::\n' "${group}" >> "${gshadow_file}"
  fi
}

add_user_to_group() {
  local root="$1"
  local user="$2"
  local group="$3"
  local group_file="${root}/etc/group"
  local gshadow_file="${root}/etc/gshadow"

  awk -F: -v OFS=: -v user="${user}" -v group="${group}" '
    $1 == group {
      split($4, members, ",")
      found = 0
      for (idx in members) {
        if (members[idx] == user) { found = 1 }
      }
      if (!found) { $4 = ($4 == "" ? user : $4 "," user) }
    }
    { print }
  ' "${group_file}" > "${group_file}.tmp"
  mv "${group_file}.tmp" "${group_file}"

  if [[ -f "${gshadow_file}" ]]; then
    awk -F: -v OFS=: -v user="${user}" -v group="${group}" '
      $1 == group {
        split($4, members, ",")
        found = 0
        for (idx in members) {
          if (members[idx] == user) { found = 1 }
        }
        if (!found) { $4 = ($4 == "" ? user : $4 "," user) }
      }
      { print }
    ' "${gshadow_file}" > "${gshadow_file}.tmp"
    mv "${gshadow_file}.tmp" "${gshadow_file}"
  fi
}

ensure_user() {
  local root="$1"
  local user="$2"
  local password_hash="$3"
  local passwd_file="${root}/etc/passwd"
  local shadow_file="${root}/etc/shadow"
  local home_dir="/home/${user}"
  local uid
  local gid

  if grep -q "^${user}:" "${passwd_file}"; then
    uid="$(awk -F: -v user="${user}" '$1 == user { print $3 }' "${passwd_file}")"
    gid="$(awk -F: -v user="${user}" '$1 == user { print $4 }' "${passwd_file}")"
    awk -F: -v OFS=: -v user="${user}" -v home="${home_dir}" '
      $1 == user { $6 = home; $7 = "/bin/bash" }
      { print }
    ' "${passwd_file}" > "${passwd_file}.tmp"
    mv "${passwd_file}.tmp" "${passwd_file}"
  else
    uid="$(next_id "${passwd_file}" 3 1000)"
    gid="${uid}"
    ensure_group "${root}" "${user}" "${gid}"
    printf '%s:x:%s:%s:TortoiseBot Operator:%s:/bin/bash\n' "${user}" "${uid}" "${gid}" "${home_dir}" >> "${passwd_file}"
  fi

  if grep -q "^${user}:" "${shadow_file}"; then
    awk -F: -v OFS=: -v user="${user}" -v hash="${password_hash}" '
      $1 == user { $2 = hash; $3 = 0; $4 = 0; $5 = 99999; $6 = 7; $7 = ""; $8 = ""; $9 = "" }
      { print }
    ' "${shadow_file}" > "${shadow_file}.tmp"
    mv "${shadow_file}.tmp" "${shadow_file}"
  else
    printf '%s:%s:0:0:99999:7:::\n' "${user}" "${password_hash}" >> "${shadow_file}"
  fi

  install -d -m 0755 -o "${uid}" -g "${gid}" "${root}${home_dir}"
  if [[ -f "${root}/etc/skel/.bashrc" && ! -f "${root}${home_dir}/.bashrc" ]]; then
    cp "${root}/etc/skel/.bashrc" "${root}${home_dir}/.bashrc"
    chown "${uid}:${gid}" "${root}${home_dir}/.bashrc"
  fi
  printf '%s:%s\n' "${uid}" "${gid}"
}

ssh_key="$(read_public_key | tr -d '\r' | head -n 1)"
[[ "${ssh_key}" =~ ^ssh-(ed25519|rsa|ecdsa)[[:space:]]+[^[:space:]]+ ]] || die "SSH key does not look like an OpenSSH public key."

mkdir -p "${CACHE_DIR}" "${OUTPUT_DIR}"

if [[ "${SKIP_DOWNLOAD}" -ne 1 ]]; then
  if [[ "${FORCE_DOWNLOAD}" -eq 1 ]]; then
    rm -f "${XZ_PATH}" "${BASE_IMG_PATH}"
  fi
  if [[ ! -f "${XZ_PATH}" ]]; then
    info "Downloading ${IMAGE_URL}"
    curl -L --fail --retry 3 -o "${XZ_PATH}" "${IMAGE_URL}"
  else
    info "Using cached download: ${XZ_PATH}"
  fi
  if [[ ! -f "${BASE_IMG_PATH}" ]]; then
    info "Expanding ${XZ_PATH}"
    xz -dk "${XZ_PATH}"
  else
    info "Using cached expanded image: ${BASE_IMG_PATH}"
  fi
fi

[[ -f "${BASE_IMG_PATH}" ]] || die "Expanded image not found: ${BASE_IMG_PATH}"

info "Copying base image to ${OUTPUT_IMG_PATH}"
cp --reflink=auto "${BASE_IMG_PATH}" "${OUTPUT_IMG_PATH}"

info "Attaching image with loop partitions"
LOOP_DEV="$(losetup -Pf --show "${OUTPUT_IMG_PATH}")"
ROOT_PART="${LOOP_DEV}p2"
BOOT_PART="${LOOP_DEV}p1"
[[ -b "${ROOT_PART}" ]] || ROOT_PART="${LOOP_DEV}p2"
[[ -b "${BOOT_PART}" ]] || BOOT_PART="${LOOP_DEV}p1"
[[ -b "${ROOT_PART}" ]] || die "Root partition not found for ${LOOP_DEV}"
[[ -b "${BOOT_PART}" ]] || die "Boot partition not found for ${LOOP_DEV}"

ROOT_MOUNT="$(mktemp -d /tmp/tortoisebot-root.XXXXXX)"
BOOT_MOUNT="$(mktemp -d /tmp/tortoisebot-boot.XXXXXX)"

info "Mounting root and boot partitions"
mount "${ROOT_PART}" "${ROOT_MOUNT}"
mount "${BOOT_PART}" "${BOOT_MOUNT}"

info "Writing hostname and hosts"
printf '%s\n' "${HOSTNAME}" > "${ROOT_MOUNT}/etc/hostname"
cat > "${ROOT_MOUNT}/etc/hosts" <<HOSTS
127.0.0.1 localhost
127.0.1.1 ${HOSTNAME}

::1 localhost ip6-localhost ip6-loopback
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
HOSTS

info "Creating ${USERNAME} user directly in rootfs"
password_hash="$(openssl passwd -6 "${USER_PASSWORD}")"
uid_gid="$(ensure_user "${ROOT_MOUNT}" "${USERNAME}" "${password_hash}")"
user_uid="${uid_gid%%:*}"
user_gid="${uid_gid##*:}"

for group in adm sudo dialout video plugdev i2c gpio; do
  ensure_group "${ROOT_MOUNT}" "${group}"
  add_user_to_group "${ROOT_MOUNT}" "${USERNAME}" "${group}"
done

install -d -m 0700 -o "${user_uid}" -g "${user_gid}" "${ROOT_MOUNT}/home/${USERNAME}/.ssh"
printf '%s
' "${ssh_key}" > "${ROOT_MOUNT}/home/${USERNAME}/.ssh/authorized_keys"
chown -R "${user_uid}:${user_gid}" "${ROOT_MOUNT}/home/${USERNAME}/.ssh"
chmod 0700 "${ROOT_MOUNT}/home/${USERNAME}/.ssh"
chmod 0600 "${ROOT_MOUNT}/home/${USERNAME}/.ssh/authorized_keys"

cat > "${ROOT_MOUNT}/etc/sudoers.d/90-tortoisebot" <<SUDOERS
${USERNAME} ALL=(ALL) NOPASSWD:ALL
SUDOERS
chmod 0440 "${ROOT_MOUNT}/etc/sudoers.d/90-tortoisebot"

info "Patching SSH server config in rootfs"
install -d "${ROOT_MOUNT}/etc/ssh/sshd_config.d"
cat > "${ROOT_MOUNT}/etc/ssh/sshd_config.d/10-tortoisebot-auth.conf" <<SSHD_DROPIN
PasswordAuthentication yes
KbdInteractiveAuthentication yes
ChallengeResponseAuthentication yes
PubkeyAuthentication yes
SSHD_DROPIN

sshd_config="${ROOT_MOUNT}/etc/ssh/sshd_config"
if [[ -f "${sshd_config}" ]]; then
  cp -n "${sshd_config}" "${sshd_config}.tortoisebot.bak" || true
  sed -i -E \
    -e '/^[#[:space:]]*PasswordAuthentication[[:space:]]+/d' \
    -e '/^[#[:space:]]*KbdInteractiveAuthentication[[:space:]]+/d' \
    -e '/^[#[:space:]]*ChallengeResponseAuthentication[[:space:]]+/d' \
    -e '/^[#[:space:]]*PubkeyAuthentication[[:space:]]+/d' \
    "${sshd_config}"
  cat >> "${sshd_config}" <<SSHD_CONFIG

# TortoiseBot provisioning
PasswordAuthentication yes
KbdInteractiveAuthentication yes
ChallengeResponseAuthentication yes
PubkeyAuthentication yes
SSHD_CONFIG
fi

info "Writing Wi-Fi netplan into rootfs and boot NoCloud seed"
install -d "${ROOT_MOUNT}/etc/netplan"
cat > "${ROOT_MOUNT}/etc/netplan/99-tortoisebot-wifi.yaml" <<NETPLAN
network:
  version: 2
  ethernets:
    eth0:
      dhcp4: true
      optional: true
  wifis:
    wlan0:
      dhcp4: true
      optional: true
      access-points:
        "${WIFI_SSID}":
          password: "${WIFI_PASSWORD}"
NETPLAN
chmod 0600 "${ROOT_MOUNT}/etc/netplan/99-tortoisebot-wifi.yaml"

install -d "${ROOT_MOUNT}/etc/cloud/cloud.cfg.d"
cat > "${ROOT_MOUNT}/etc/cloud/cloud.cfg.d/99-tortoisebot-disable-network-config.cfg" <<CLOUD_NETWORK
network: {config: disabled}
CLOUD_NETWORK

cat > "${BOOT_MOUNT}/network-config" <<NETPLAN
version: 2
ethernets:
  eth0:
    dhcp4: true
    optional: true
wifis:
  wlan0:
    dhcp4: true
    optional: true
    access-points:
      "${WIFI_SSID}":
        password: "${WIFI_PASSWORD}"
NETPLAN

cat > "${BOOT_MOUNT}/meta-data" <<META
instance-id: tortoisebot-${HOSTNAME}-ubuntu-image
local-hostname: ${HOSTNAME}
META

cat > "${BOOT_MOUNT}/user-data" <<USERDATA
#cloud-config
hostname: ${HOSTNAME}
manage_etc_hosts: true
ssh_pwauth: true
package_update: false
package_upgrade: false
runcmd:
  - [ touch, /etc/cloud/cloud-init.disabled ]
final_message: "TortoiseBot image boot complete. SSH in and run: sudo /usr/local/sbin/tortoisebot-install.sh"
USERDATA

info "Installing TortoiseBot manual installer into rootfs"
cat > "${ROOT_MOUNT}/usr/local/sbin/tortoisebot-install.sh" <<INSTALLER
#!/usr/bin/env bash
set -euxo pipefail

USERNAME="${USERNAME}"
REPO_URL="${REPO_URL}"
REPO_BRANCH="${REPO_BRANCH}"
WS="/home/\${USERNAME}/tb_ws"
REPO_DIR="\${WS}/src/tortoisebot"
LOG_FILE="/var/log/tortoisebot-install.log"
SENTINEL="/var/lib/tortoisebot/.install-complete"

install -d /var/lib/tortoisebot
touch "\${LOG_FILE}"
chmod 0644 "\${LOG_FILE}"
exec > >(tee -a "\${LOG_FILE}") 2>&1

echo "==> TortoiseBot install started at \$(date -Is)"

if [[ -f "\${SENTINEL}" ]]; then
  echo "==> TortoiseBot install already completed. Remove \${SENTINEL} to force a reinstall."
  exit 0
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates git

install -d -o "\${USERNAME}" -g "\${USERNAME}" "\${WS}/src"
if [[ ! -d "\${REPO_DIR}/.git" ]]; then
  sudo -u "\${USERNAME}" git clone --branch "\${REPO_BRANCH}" "\${REPO_URL}" "\${REPO_DIR}"
else
  sudo -u "\${USERNAME}" git -C "\${REPO_DIR}" fetch origin "\${REPO_BRANCH}"
  sudo -u "\${USERNAME}" git -C "\${REPO_DIR}" checkout "\${REPO_BRANCH}"
  sudo -u "\${USERNAME}" git -C "\${REPO_DIR}" pull --ff-only
fi

bash "\${REPO_DIR}/provisioning/scripts/install_tortoisebot_humble.sh"

# The YDLidar SDK is installed as a native CMake package above. Do not let
# colcon discover it as a workspace package and race the ROS driver build.
touch "\${REPO_DIR}/YDLidar-SDK/COLCON_IGNORE"

cd "\${WS}"
rosdep install --from-paths src --ignore-src -r -y --rosdistro humble
chown -R "\${USERNAME}:\${USERNAME}" "\${WS}"
sudo -u "\${USERNAME}" bash -lc "source /opt/ros/humble/setup.bash && cd '\${WS}' && colcon build"
chown -R "\${USERNAME}:\${USERNAME}" "\${WS}"

if ! grep -q "\${WS}/install/setup.bash" "/home/\${USERNAME}/.bashrc"; then
  echo "source \${WS}/install/setup.bash" >> "/home/\${USERNAME}/.bashrc"
fi
chown "\${USERNAME}:\${USERNAME}" "/home/\${USERNAME}/.bashrc"

touch "\${SENTINEL}"
echo "==> TortoiseBot install complete at \$(date -Is)"
INSTALLER
chmod 0755 "${ROOT_MOUNT}/usr/local/sbin/tortoisebot-install.sh"

cat > "${ROOT_MOUNT}/etc/motd" <<MOTD
TortoiseBot Raspberry Pi is online.

To install ROS 2 Humble and the TortoiseBot workspace, run:
  sudo /usr/local/sbin/tortoisebot-install.sh

To monitor install progress:
  tail -f /var/log/tortoisebot-install.log
MOTD

info "Syncing image changes"
sync

umount "${BOOT_MOUNT}"
BOOT_MOUNT=""
umount "${ROOT_MOUNT}"
ROOT_MOUNT=""
losetup -d "${LOOP_DEV}"
LOOP_DEV=""

info "Image ready: ${OUTPUT_IMG_PATH}"

if [[ -n "${DEVICE}" ]]; then
  [[ -b "${DEVICE}" ]] || die "Device does not exist: ${DEVICE}"
  device_size_bytes="$(blockdev --getsize64 "${DEVICE}")"
  max_bytes=$((MAX_DEVICE_SIZE_GB * 1024 * 1024 * 1024))
  if (( device_size_bytes >= max_bytes )); then
    die "${DEVICE} is >= ${MAX_DEVICE_SIZE_GB}GB; refusing to flash."
  fi
  echo
  lsblk -o NAME,SIZE,MODEL,TRAN,MOUNTPOINTS "${DEVICE}"
  echo
  read -r -p "About to overwrite ${DEVICE} with ${OUTPUT_IMG_PATH}. Type YES to continue: " confirm
  [[ "${confirm}" == "YES" ]] || die "Confirmation declined."
  info "Unmounting mounted partitions under ${DEVICE}"
  while read -r mountpoint; do
    [[ -n "${mountpoint}" ]] && umount "${mountpoint}" || true
  done < <(lsblk -nrpo MOUNTPOINTS "${DEVICE}" | sed '/^$/d')
  info "Flashing ${DEVICE}"
  dd if="${OUTPUT_IMG_PATH}" of="${DEVICE}" bs=4M status=progress conv=fsync
  sync
  info "Flash complete. Eject ${DEVICE}, boot the Pi, then SSH to ${USERNAME}@${HOSTNAME}.local or the router IP."
fi
