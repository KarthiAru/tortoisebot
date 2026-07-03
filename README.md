# TortoiseBot — ROS 2 Humble

<p align="center">
  <img src="https://github.com/rigbetellabs/tortoisebot_docs/raw/master/imgs/packaging/pack_front.png" alt="TortoiseBot Banner" width="800"/>
</p>

<p align="center">
  <img src="https://img.shields.io/github/stars/rigbetellabs/tortoisebot?style=for-the-badge"/>
  <img src="https://img.shields.io/github/forks/rigbetellabs/tortoisebot?style=for-the-badge"/>
  <img src="https://img.shields.io/github/watchers/rigbetellabs/tortoisebot?style=for-the-badge"/>
  <img src="https://img.shields.io/github/repo-size/rigbetellabs/tortoisebot?style=for-the-badge"/>
  <img src="https://img.shields.io/github/contributors/rigbetellabs/tortoisebot?style=for-the-badge"/>
</p>

<p align="center">
  <a href="https://rigbetellabs.com/"><img src="https://img.shields.io/website?down_color=lightgrey&down_message=offline&label=Rigbetellabs%20Website&style=for-the-badge&up_color=green&up_message=online&url=https%3A%2F%2Frigbetellabs.com%2F"/></a>
  <a href="https://rigbetellabs.com/discord"><img src="https://img.shields.io/discord/890669104330063903?logo=Discord&style=for-the-badge"/></a>
  <a href="https://www.youtube.com/channel/UCfIX89y8OvDIbEFZAAciHEA"><img src="https://img.shields.io/youtube/channel/subscribers/UCfIX89y8OvDIbEFZAAciHEA?label=YT%20Subscribers&style=for-the-badge"/></a>
  <a href="https://www.instagram.com/rigbetellabs/"><img src="https://img.shields.io/badge/Follow_on-Instagram-pink?style=for-the-badge&logo=instagram"/></a>
</p>

---

<p align="center">
  <a href="#1-installation">Installation</a> •
  <a href="#2-workspace-setup">Workspace Setup</a> •
  <a href="#3-simulation">Simulation</a> •
  <a href="#4-real-robot">Real Robot</a> •
  <a href="#5-more-wiki-resources">More Wiki Resources</a>
</p>

---

## 1. Installation

For Raspberry Pi hardware, the recommended base OS is **Ubuntu Server 22.04 LTS
64-bit for Raspberry Pi**. ROS 2 Humble binary packages target Ubuntu Jammy, so
that path is much cleaner than installing Humble on stock Raspberry Pi OS.

SD-card provisioning files live in [`provisioning/`](provisioning/README.md).

### 1.1 Required Dependencies

Install all required ROS 2 Humble packages:

```bash
sudo apt install \
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
  ros-humble-foxglove-bridge \
  ros-humble-v4l2-camera \
  ros-humble-image-transport-plugins \
  ros-humble-ros-gz-bridge \
  ros-humble-ros-gz-sim \
  ros-humble-ros-gz-interfaces
```

On TortoiseBot hardware, also install the Raspberry Pi Python sensor libraries used by the GPIO motor driver and BNO055 IMU node:

```bash
sudo apt install python3-pip python3-rpi.gpio i2c-tools v4l-utils
pip3 install adafruit-blinka adafruit-circuitpython-bno055
```

---

## 2. Workspace Setup

### 2.1 Clone the Repository

Clone the repository on both your **robot** and your **remote PC**:

```bash
mkdir -p ~/tb_ws/src && cd ~/tb_ws/src
git clone -b ros2-humble https://github.com/rigbetellabs/tortoisebot.git
```

### 2.2 Build the Workspace

```bash
cd ~/tb_ws
colcon build
source install/setup.bash
```

> **Remote PC Note:** When building on a remote PC, exclude hardware-specific packages (LiDAR, camera, firmware) that are only required on the robot itself:
>
> ```bash
> colcon build --packages-ignore ydlidar_sdk ydlidar_ros2_driver v4l2_camera tortoisebot_firmware tortoisebot_imu
> ```

### 2.3 Key Launch Arguments

`autobringup.launch.py` is the single entry point for all operating modes:

| Argument | `True` | `False` |
|---|---|---|
| `use_sim_time` | Ignition Gazebo simulation | Real robot hardware |
| `exploration` | SLAM — build a new map | Navigation — use a saved map |

### 2.4 Available Launch Files

| Category | Launch File | Purpose |
|---|---|---|
| **Main** | `autobringup.launch.py` | All-in-one bringup (sim + real, SLAM + nav) |
| **Main** | `bringup.launch.py` | Simulation only (no nav stack) |
| **Logging** | `hardware_record.launch.py` | Record hardware topics to MCAP for Foxglove |
| **SLAM** | `cartographer.launch.py` | Cartographer SLAM node |
| **Navigation** | `navigation_slam.launch.py` | Nav2 stack during SLAM |
| **Navigation** | `navigation_mapbased.launch.py` | Nav2 with AMCL on a saved map |
| **Navigation** | `save_map.launch.py` | Save current Cartographer map to disk |
| **Visualization** | `rviz.launch.py` | RViz2 sensor & map visualization |
| **Sim** | `ignition_sim.launch.py` | Ignition Gazebo simulation |
| **Sim** | `gazebo.launch.py` | Gazebo Classic simulation |

---

## 3. Simulation

The TortoiseBot simulation runs inside **Ignition Gazebo** with full ROS 2 Humble integration. RViz2 launches automatically alongside Gazebo, providing a live side-by-side view of the robot's sensor data, SLAM map, and navigation stack.

### 3.1 Teleoperation in Simulation

Drive the robot manually using the keyboard teleop:

```bash
# Terminal 1 — Launch Gazebo + RViz + SLAM
ros2 launch tortoisebot_bringup autobringup.launch.py use_sim_time:=True exploration:=True

# Terminal 2 — Keyboard teleoperation
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

<p align="center">
  <img src="media/teleop.gif" alt="Teleoperation Demo" width="800"/>
</p>

### 3.2 Autonomous Exploration & SLAM Mapping

The robot maps the environment autonomously using **Cartographer SLAM**. Use the `2D Nav Goal` button in RViz2 to send exploration goals:

```bash
ros2 launch tortoisebot_bringup autobringup.launch.py use_sim_time:=True exploration:=True
```

<p align="center">
  <img src="media/navigation.gif" alt="SLAM Mapping Demo" width="800"/>
</p>

<p align="center">
  <img src="media/goaltravel.gif" alt="Goal Travel during SLAM" width="800"/>
</p>

### 3.3 Autonomous Navigation on a Saved Map

Once a map has been built and saved, the robot localizes itself using **AMCL** (Adaptive Monte Carlo Localization) and navigates autonomously to any goal point:

```bash
# Step 1 — Save the map after exploration
ros2 launch tortoisebot_navigation save_map.launch.py map_name:=/home/vn/tb_ws/maps/my_map

# Step 2 — Navigate using the saved map
ros2 launch tortoisebot_bringup autobringup.launch.py use_sim_time:=True exploration:=False map_file:=/home/vn/tb_ws/maps/my_map.yaml
```

<p align="center">
  <img src="media/amclnav.gif" alt="AMCL Navigation on Saved Map" width="800"/>
</p>

---

## 4. Real Robot

### 4.1 Network Setup — Connecting the Robot to Your Wi-Fi

Before powering up the robot for the first time, configure Wi-Fi credentials directly on the SD card.

> **Recommended:** Perform these steps on a Linux or macOS machine.

1. Insert the SD card into your computer using a card reader.
2. Navigate to the `writable` partition, then to `/etc/netplan/`.
3. Open `50-cloud-init.yaml` in a text editor.
4. Locate the `wifis` section and add your credentials:

```yaml
wlan0:
  optional: true
  access-points:
    "your_wifi_ssid":
      password: "your_wifi_password"
  dhcp4: true
```

<p align="center">
  <img src="https://github.com/rigbetellabs/tortoisebot_docs/blob/ros2/imgs/tortoiseBot_demo/path_for_wifi_add.png?raw=true" alt="Netplan path" width="600"/>
</p>

<p align="center">
  <img src="https://github.com/rigbetellabs/tortoisebot_docs/blob/ros2/imgs/tortoiseBot_demo/wifi_ssid_pass.png?raw=true" alt="SSID and password entry" width="600"/>
</p>

**Example configuration:**

<p align="center">
  <img src="https://github.com/rigbetellabs/tortoisebot_docs/blob/ros2/imgs/tortoiseBot_demo/wifi_rpi_config.png?raw=true" alt="Wi-Fi RPi config example" width="600"/>
</p>

5. Save the file and exit the text editor.
6. Safely eject the SD card and insert it into the robot.

The robot will connect to your Wi-Fi network automatically on the next boot.

---

### 4.2 SSH into the Robot

After powering on the robot, obtain its IP address (displayed on its OLED screen or found via your router's device list):

<p align="center">
  <img src="https://github.com/rigbetellabs/tortoisebot_docs/blob/master/imgs/tortoiseBot_setup/001.jpeg?raw=true" alt="Finding robot IP" width="600"/>
</p>

Connect to the robot from your PC terminal:

```bash
ssh tortoisebot@<ROBOT_IP_ADDRESS>
# Example: ssh tortoisebot@192.168.0.120
# Password: raspberry
```

---

### 4.3 Hardware Runbook - Copy/Paste Commands

Use these commands on the Raspberry Pi after SSH login. The robot workspace is
expected at `~/tb_ws`, with this repo cloned at `~/tb_ws/src/tortoisebot`.

#### Source ROS 2 and the Workspace

Run this in every new SSH terminal before using `ros2`:

```bash
source /opt/ros/humble/setup.bash
source ~/tb_ws/install/setup.bash
```

Optional: make sourcing automatic for future SSH sessions:

```bash
grep -qxF 'source /opt/ros/humble/setup.bash' ~/.bashrc || echo 'source /opt/ros/humble/setup.bash' >> ~/.bashrc
grep -qxF 'source ~/tb_ws/install/setup.bash' ~/.bashrc || echo 'source ~/tb_ws/install/setup.bash' >> ~/.bashrc
source ~/.bashrc
```

#### Sync Latest Code on the Pi

```bash
cd ~/tb_ws/src/tortoisebot
git pull --ff-only origin mcap-logging

cd ~/tb_ws
colcon build --packages-select tortoisebot_bringup
source install/setup.bash
```

For larger dependency changes, rebuild everything:

```bash
cd ~/tb_ws
colcon build
source install/setup.bash
```

#### Start Robot, SLAM, Camera, and MCAP Logging

This is the normal hardware launch for data collection. Leave this terminal
running until the run is complete.

```bash
source /opt/ros/humble/setup.bash
source ~/tb_ws/install/setup.bash

ros2 launch tortoisebot_bringup bringup.launch.py \
  use_sim_time:=False \
  exploration:=True \
  record_mcap:=True \
  enable_camera:=True
```

Add Foxglove Bridge when you want live visualization or Foxglove teleop:

```bash
ros2 launch tortoisebot_bringup bringup.launch.py \
  use_sim_time:=False \
  exploration:=True \
  record_mcap:=True \
  enable_camera:=True \
  enable_foxglove_bridge:=True
```

The Raspberry Pi CSI camera uses `camera_ros`/libcamera by default. The launch
keeps the raw image available for live debugging and publishes optimized
Foxglove-friendly topics:

```text
/camera/image_raw
/camera/image_mono
/camera/image_mono_downsampled
/camera/camera_info
```

`/camera/image_mono_downsampled` defaults to `320x240` `mono8` and is the image
topic recorded into MCAP by default to keep bags much smaller than raw color
frames.

For a USB V4L2 webcam fallback, use:

```bash
ros2 launch tortoisebot_bringup bringup.launch.py \
  use_sim_time:=False \
  exploration:=True \
  record_mcap:=True \
  enable_camera:=True \
  camera_driver:=v4l2 \
  camera_device:=/dev/video0
```

#### Manual Teleop from SSH

Use keyboard teleop only in open space. It publishes directly to `/cmd_vel`, so
it bypasses Nav2 costmaps and does not avoid obstacles.

```bash
source /opt/ros/humble/setup.bash
source ~/tb_ws/install/setup.bash

ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

Stop manual motion with `k`, `Ctrl+C`, or an explicit zero velocity:

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{}'
```

#### Foxglove Live Connection and Teleop

Use Foxglove WebSocket, not Rosbridge, for live ROS 2 data and publishing.
Start the bridge with the main launch:

```bash
ros2 launch tortoisebot_bringup bringup.launch.py \
  use_sim_time:=False \
  exploration:=True \
  record_mcap:=True \
  enable_camera:=True \
  enable_foxglove_bridge:=True
```

In Foxglove on your PC:

```text
Open connection -> Foxglove WebSocket -> ws://<ROBOT_IP>:8765
```

Example:

```text
ws://192.168.0.117:8765
```

Add a **Teleop** panel and configure it:

```text
Topic: /cmd_vel
Schema: geometry_msgs/msg/Twist
Publish rate: 5 Hz
Stop on release: enabled
Up:    linear.x  = 0.08
Down:  linear.x  = -0.05
Left:  angular.z = 0.45
Right: angular.z = -0.45
Stop:  all Twist fields = 0
```

Foxglove teleop is also direct `/cmd_vel` control. Do not use it at the same
time as keyboard teleop or while Nav2 is actively executing a goal.

#### Autonomous Mapping with Collision Avoidance

`exploration:=True` starts Cartographer SLAM and Nav2 in SLAM mode. Nav2 uses
`/scan` in the local and global costmaps to plan around obstacles. This is
collision-aware only when you send Nav2 goals; manual `/cmd_vel` teleop is not
collision-aware.

Before sending goals, verify the stack:

```bash
source /opt/ros/humble/setup.bash
source ~/tb_ws/install/setup.bash

ros2 topic list | grep -E '^/scan$|^/map$|^/tf$|^/cmd_vel$'
ros2 topic hz /scan
ros2 lifecycle nodes
```

From RViz on a remote Ubuntu PC, set the fixed frame to `map`, display `/map`,
`/scan`, `TF`, the robot model, and costmaps, then use **2D Nav Goal**. Send
short goals into visible free space and let Cartographer grow the map as the
robot moves.

Foxglove is useful for watching `/map`, `/scan`, `/tf`, `/cmd_vel`, and
`/camera/image_mono_downsampled`; use RViz or another Nav2-compatible goal tool
for collision-aware navigation goals.

#### Save the Map

After mapping, save the current map:

```bash
source /opt/ros/humble/setup.bash
source ~/tb_ws/install/setup.bash

mkdir -p ~/tb_ws/maps
ros2 run nav2_map_server map_saver_cli \
  -f ~/tb_ws/maps/tortoisebot_map \
  --ros-args -p use_sim_time:=false
```

This creates:

```text
~/tb_ws/maps/tortoisebot_map.yaml
~/tb_ws/maps/tortoisebot_map.pgm
```

#### Map-Based Navigation on a Saved Map

```bash
source /opt/ros/humble/setup.bash
source ~/tb_ws/install/setup.bash

ros2 launch tortoisebot_bringup bringup.launch.py \
  use_sim_time:=False \
  exploration:=False \
  map_file:=/home/tortoisebot/tb_ws/maps/tortoisebot_map.yaml \
  record_mcap:=True \
  enable_camera:=True \
  enable_foxglove_bridge:=True
```

Set the initial pose if AMCL needs help, then send Nav2 goals. As with SLAM
mode, obstacle avoidance comes from Nav2 costmaps fed by `/scan`.

#### Stop Robot and Logging

Press `Ctrl+C` in the launch terminal. That stops the robot nodes and closes the
MCAP bag cleanly.

Before powering off the Raspberry Pi or removing the SD card, verify the latest
bag and flush filesystem writes:

```bash
source /opt/ros/humble/setup.bash
source ~/tb_ws/install/setup.bash

LATEST=$(ls -td ~/tortoisebot_mcap/tortoisebot_hardware_* | head -1)
ros2 bag info "$LATEST"
sync
```

If `ros2 bag info` succeeds, the bag is readable at that moment. `sync` makes
Linux flush pending writes to the SD card. After that, shut down cleanly:

```bash
sudo shutdown -h now
```

Wait until the Pi is halted before removing power or extracting the SD card.

### 4.4 Verify Robot Topics

Use a second SSH terminal while the launch is running:

```bash
source /opt/ros/humble/setup.bash
source ~/tb_ws/install/setup.bash

ros2 topic list
ros2 topic hz /scan
ros2 topic hz /camera/image_raw
ros2 topic hz /camera/image_mono_downsampled
ros2 topic info /camera/image_mono_downsampled -v
```

Expected important topics:

```text
/scan
/map
/camera/image_raw
/camera/image_mono
/camera/image_mono_downsampled
/camera/camera_info
/tf
/tf_static
/cmd_vel
/odom
```

`ros2 topic info /camera/image_mono_downsampled -v` should show:

- Publisher: `/image_optimizer`
- Subscriber: `/rosbag2_recorder` when `record_mcap:=True`

To check the optimized camera image encoding:

```bash
ros2 topic echo --once /camera/image_mono_downsampled | grep encoding
```

Expected:

```text
encoding: mono8
```

Do not use `/camera/image_raw/header` or `/camera/image_raw/encoding`; those are
message fields, not ROS topics.

### 4.5 MCAP Logging for Foxglove

The hardware recorder uses ROS 2 `rosbag2` with MCAP storage:

```bash
ros2 bag record --storage mcap ...
```

The launch records to:

```text
~/tortoisebot_mcap/tortoisebot_hardware_<timestamp>/
```

Find and inspect the latest recording:

```bash
source /opt/ros/humble/setup.bash
source ~/tb_ws/install/setup.bash

LATEST=$(ls -td ~/tortoisebot_mcap/tortoisebot_hardware_* | head -1)
echo "$LATEST"
ros2 bag info "$LATEST"
find "$LATEST" -name '*.mcap' -ls
```

Expected non-zero message counts:

```text
/camera/image_mono_downsampled
/camera/camera_info
/scan
/tf
/tf_static
/cmd_vel
```

Open the generated `.mcap` file in Foxglove. For the Image panel, select:

```text
/camera/image_mono_downsampled
```

If Foxglove reports an unsupported image encoding, confirm the file is from a
new recording and check:

```bash
ros2 topic echo --once /camera/image_mono_downsampled | grep encoding
```

Older test bags may contain `nv21` or full raw color images. Fresh bags from
this launch should record the smaller `mono8` downsampled stream by default.

Copy a bag from the Pi to a PC:

```bash
scp -r tortoisebot@<ROBOT_IP>:~/tortoisebot_mcap/tortoisebot_hardware_<timestamp> ./
```

Prefer copying over SSH when possible. If you extract logs from the SD card,
always run the stop/verify/`sync` sequence above before shutdown; otherwise the
MCAP file may be missing its final footer/index and Foxglove may report it as
malformed.

### 4.6 Troubleshooting

#### `ros2: command not found`

```bash
source /opt/ros/humble/setup.bash
source ~/tb_ws/install/setup.bash
```

#### Foxglove Cannot Connect

Make sure Foxglove Bridge was enabled and is listening on the robot:

```bash
ros2 node list | grep foxglove
ss -ltnp | grep 8765
```

In Foxglove, choose **Foxglove WebSocket** and use:

```text
ws://<ROBOT_IP>:8765
```

Use `ws://localhost:8765` only when the bridge is running on the same computer
as Foxglove.

#### Robot Moves Manually But Does Not Avoid Obstacles

Keyboard teleop and Foxglove Teleop publish directly to `/cmd_vel`. This is
expected and bypasses Nav2. For obstacle avoidance, stop teleop and send goals
through Nav2 while `exploration:=True` or `exploration:=False` is running.

#### Only `/rosout` and `/parameter_events` Are Visible

The robot launch is not running, or you are in a different ROS domain. Start the
bringup launch, then check again:

```bash
ros2 topic list
```

#### Camera Topic Exists But No Frames

Check the camera frame rate:

```bash
ros2 topic hz /camera/image_raw
```

Check camera node logs in the launch terminal. For the Raspberry Pi CSI camera,
`camera_ros` should log an OV5647/OVxxxx camera and a configured stream. Direct
V4L2 streaming from `/dev/video0` may fail on CSI cameras; that is why the
default launch uses libcamera instead of `v4l2_camera`.

Useful camera checks:

```bash
ros2 topic list | grep camera
ros2 topic info /camera/image_raw -v
ros2 topic hz /camera/image_mono_downsampled
ros2 topic echo --once /camera/image_mono_downsampled | grep encoding
```

#### Optimized Image Topics Are Missing

The MCAP recorder expects `/camera/image_mono_downsampled`. If it is missing,
make sure the optimizer is enabled and the package was rebuilt:

```bash
ros2 launch tortoisebot_bringup bringup.launch.py \
  use_sim_time:=False \
  exploration:=True \
  record_mcap:=True \
  enable_camera:=True \
  enable_image_optimizer:=True
```

Verify:

```bash
ros2 topic list | grep image_mono
ros2 topic echo --once /camera/image_mono_downsampled | grep encoding
```

Expected:

```text
encoding: mono8
```

#### Camera Topics Are Under `/camera/camera_node/...`

Rebuild and restart after pulling the latest launch remaps:

```bash
cd ~/tb_ws/src/tortoisebot
git pull --ff-only origin mcap-logging

cd ~/tb_ws
colcon build --packages-select tortoisebot_bringup
source install/setup.bash
```

Then stop the old launch with `Ctrl+C` and start it again.

#### Cartographer Drops Earlier Points

If the launch terminal repeatedly prints this warning:

```text
range_data_collator.cc:82] Dropped ... earlier points.
```

rebuild the YDLidar driver after pulling the latest code:

```bash
cd ~/tb_ws/src/tortoisebot
git pull --ff-only origin mcap-logging

cd ~/tb_ws
colcon build --packages-select ydlidar_ros2_driver tortoisebot_slam tortoisebot_bringup
source install/setup.bash
```

The driver defaults `disable_point_timestamps: true` so Cartographer treats each
2D scan as an instantaneous scan. This avoids dropped points caused by SDK
per-point timestamps that no longer match acquisition order after the driver
re-bins points into angle order.

#### Check Disk Space Before Long Recordings

```bash
df -h ~
du -sh ~/tortoisebot_mcap/* | sort -h | tail
```

> Note: this repository does not include a wheel encoder odometry driver. The
> MCAP recorder includes `/odom`, but that topic will only contain data if
> another odometry node is running.

---

## 5. Raspberry Pi SD Card Image

### 5.1 Build and Flash a Repeatable Ubuntu SD Image

Use the Ubuntu/Linux provisioning workflow in [`provisioning/`](provisioning/README.md).
The old Windows PowerShell flow is deprecated because Windows cannot reliably
configure the Linux ext4 root partition with correct users, SSH keys, ownership,
and permissions.

On an Ubuntu development machine:

```bash
sudo apt-get update
sudo apt-get install -y curl xz-utils util-linux openssl coreutils

cp provisioning/config/tortoisebot-image.example.env provisioning/config/tortoisebot-image.local.env
nano provisioning/config/tortoisebot-image.local.env
```

Set Wi-Fi, SSH key, repo URL, and branch in the local env file. Then build and
flash the card:

```bash
lsblk -o NAME,SIZE,MODEL,TRAN,MOUNTPOINTS
sudo bash provisioning/scripts/build_tortoisebot_image.sh --device /dev/sdX
```

Replace `/dev/sdX` with the whole removable microSD device, not a partition like
`/dev/sdX1`.

The script caches the Ubuntu base image under `~/.cache/tortoisebot`. Force a
fresh OS download with:

```bash
sudo bash provisioning/scripts/build_tortoisebot_image.sh --force-download --device /dev/sdX
```

After first boot, SSH in and start the manual installer:

```bash
ssh tortoisebot@<ROBOT_IP>
sudo /usr/local/sbin/tortoisebot-install.sh
```

Monitor install logs:

```bash
tail -f /var/log/tortoisebot-install.log
```

### 5.2 Can ROS 2 Humble and This Code Be Pre-Packaged?

Yes. The practical route is to build a custom **Ubuntu Server 22.04 Raspberry Pi
image** or use cloud-init/first-boot automation that installs ROS 2 Humble,
clones this repo, runs `rosdep`, and builds the workspace. Baking this directly
into stock Raspberry Pi OS is not recommended for Humble because Raspberry Pi OS
is Debian-based while Humble apt binaries are built for Ubuntu Jammy.

See [`provisioning/README.md`](provisioning/README.md) for the image workflow,
Wi-Fi template, and install script.

---

## 6. More Wiki Resources

The TortoiseBot documentation is continuously maintained and updated by the team at **RigBetel Labs**. The full wiki covers hardware assembly, OS flashing, advanced configuration, and project showcases.

| Resource | Link |
|---|---|
| 🚀 Getting Started | [Wiki — Getting Started](https://github.com/rigbetellabs/tortoisebot/wiki/1.-Getting-Started) |
| 🔧 Hardware Assembly | [Wiki — Hardware Assembly](https://github.com/rigbetellabs/tortoisebot/wiki/2.-Hardware-Assembly) |
| ⚙️ TortoiseBot Setup | [Wiki — TortoiseBot Setup](https://github.com/rigbetellabs/tortoisebot/wiki/3.-TortoiseBot-Setup) |
| 💻 Server PC Setup | [Wiki — Server PC Setup](https://github.com/rigbetellabs/tortoisebot/wiki/4.-Server-PC-Setup) |
| 🎮 Running Demos | [Wiki — Running Demos](https://github.com/rigbetellabs/tortoisebot/wiki/5.-Running-Demos) |
| 💬 Community Discord | [Join the Community](https://discord.gg/qDuCSMTjvN) |

Don't forget to ⭐ **Star this repository** to stay updated with the latest releases and show your support for the team!

---

<p align="center">
  TortoiseBot is designed, assembled, and maintained by the team at<br/><br/>
  <strong>RigBetel Labs LLP®</strong><br/>
  Charholi Bk., via. Loheagaon, Pune – 412105, MH, India 🇮🇳<br/><br/>
  🌐 <a href="https://rigbetellabs.com">RigBetelLabs.com</a> &nbsp;|&nbsp;
  📞 <a href="https://wa.me/918432152998">+91-8432152998</a> &nbsp;|&nbsp;
  📨 <a href="mailto:info@rigbetellabs.com">info@rigbetellabs.com</a><br/><br/>
  <a href="http://linkedin.com/company/rigbetellabs/">LinkedIn</a> &nbsp;|&nbsp;
  <a href="http://instagram.com/rigbetellabs/">Instagram</a> &nbsp;|&nbsp;
  <a href="http://facebook.com/rigbetellabs">Facebook</a> &nbsp;|&nbsp;
  <a href="http://twitter.com/rigbetellabs">Twitter</a> &nbsp;|&nbsp;
  <a href="https://www.youtube.com/channel/UCfIX89y8OvDIbEFZAAciHEA">YouTube</a> &nbsp;|&nbsp;
  <a href="https://discord.gg/qDuCSMTjvN">Discord</a>
</p>
