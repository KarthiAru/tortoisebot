# Raspberry Pi SD Card Provisioning

Use Ubuntu Server 22.04 LTS 64-bit for Raspberry Pi as the base image. ROS 2
Humble binary packages target Ubuntu Jammy, so this is the most reliable route
for TortoiseBot hardware.

## Flash the SD Card

1. Open Raspberry Pi Imager.
2. Select Ubuntu Server 22.04 LTS 64-bit.
3. In OS customization, set hostname, username, SSH, locale, and Wi-Fi.
4. Flash the SD card and boot the Raspberry Pi.

If you prefer manual Wi-Fi setup, mount the SD card writable partition and copy:

```bash
sudo cp provisioning/netplan/50-cloud-init.yaml.template /media/$USER/writable/etc/netplan/50-cloud-init.yaml
```

Then replace `YOUR_WIFI_SSID` and `YOUR_WIFI_PASSWORD`, unmount the card, and
boot the robot.

## Install ROS 2 Humble and TortoiseBot Dependencies

After SSHing into the robot:

```bash
sudo apt update
sudo apt install -y git
git clone <YOUR_REPO_URL> ~/tb_ws/src/tortoisebot
cd ~/tb_ws/src/tortoisebot
sudo bash provisioning/scripts/install_tortoisebot_humble.sh
cd ~/tb_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build
echo "source ~/tb_ws/install/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

## Bake It Into an Image

Yes, this repo can be packaged with ROS 2 Humble into a prebuilt SD-card image.
The recommended approach is to customize an Ubuntu Server 22.04 Raspberry Pi
image or automate first boot with cloud-init. Baking the install into stock
Raspberry Pi OS is not recommended for Humble because Raspberry Pi OS is
Debian-based while Humble binary packages are built for Ubuntu Jammy.

For production images, create a first-boot script that:

1. Applies the Netplan Wi-Fi config.
2. Runs `provisioning/scripts/install_tortoisebot_humble.sh`.
3. Clones this repo into `~/tb_ws/src/tortoisebot`.
4. Runs `rosdep install` and `colcon build`.
5. Optionally installs a systemd service that launches `autobringup.launch.py`.
