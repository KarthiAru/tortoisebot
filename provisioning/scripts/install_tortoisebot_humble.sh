#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo: sudo bash provisioning/scripts/install_tortoisebot_humble.sh" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y software-properties-common curl gnupg lsb-release locales
locale-gen en_US en_US.UTF-8
update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

add-apt-repository universe -y
install -d -m 0755 /etc/apt/keyrings
curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /etc/apt/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo "$UBUNTU_CODENAME") main" \
  > /etc/apt/sources.list.d/ros2.list

apt-get update
apt-get install -y \
  ca-certificates \
  build-essential \
  cmake \
  git \
  python3-colcon-common-extensions \
  python3-pip \
  python3-rosdep \
  python3-rpi.gpio \
  i2c-tools \
  v4l-utils \
  ros-humble-ros-base \
  ros-humble-joint-state-publisher \
  ros-humble-robot-state-publisher \
  ros-humble-cartographer \
  ros-humble-cartographer-ros \
  ros-humble-teleop-twist-keyboard \
  ros-humble-teleop-twist-joy \
  ros-humble-xacro \
  ros-humble-nav2-bringup \
  ros-humble-navigation2 \
  ros-humble-urdf \
  ros-humble-robot-localization \
  ros-humble-ros2bag \
  ros-humble-rosbag2-storage-mcap \
  ros-humble-rosbag2-transport \
  ros-humble-v4l2-camera \
  ros-humble-image-transport-plugins

pip3 install adafruit-blinka adafruit-circuitpython-bno055

for group in dialout gpio i2c video plugdev; do
  groupadd -f "$group"
done

for user_home in /home/*; do
  user="$(basename "$user_home")"
  if id "$user" >/dev/null 2>&1; then
    usermod -aG dialout,gpio,i2c,video,plugdev "$user" || true
  fi
done

if [[ -f /boot/firmware/config.txt ]] && ! grep -q '^dtparam=i2c_arm=on' /boot/firmware/config.txt; then
  echo 'dtparam=i2c_arm=on' >> /boot/firmware/config.txt
fi

if ! rosdep db 2>/dev/null | grep -q "humble"; then
  rosdep init || true
fi
if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]] && id "${SUDO_USER}" >/dev/null 2>&1; then
  rosdep fix-permissions || true
  sudo -u "${SUDO_USER}" rosdep update
else
  rosdep update
fi

install_ydlidar_sdk() {
  local repo_dir
  repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  local sdk_dir="${repo_dir}/YDLidar-SDK"
  local build_dir="/tmp/ydlidar_sdk_build"

  if [[ ! -f "${sdk_dir}/CMakeLists.txt" ]]; then
    echo "YDLidar-SDK not found at ${sdk_dir}; skipping SDK install."
    return 0
  fi

  cmake -S "${sdk_dir}" -B "${build_dir}" \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_EXAMPLES=OFF \
    -DBUILD_TEST=OFF \
    -DBUILD_CSHARP=OFF
  cmake --build "${build_dir}" --parallel "$(nproc)"
  cmake --install "${build_dir}"
  ldconfig
}

install_ydlidar_sdk

if ! grep -q "/opt/ros/humble/setup.bash" /home/*/.bashrc 2>/dev/null; then
  for bashrc in /home/*/.bashrc; do
    echo "source /opt/ros/humble/setup.bash" >> "$bashrc"
  done
fi

echo "TortoiseBot ROS 2 Humble dependencies installed. Reboot if I2C was enabled for the first time."
