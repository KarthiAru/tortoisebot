#!/usr/bin/env python3

import os
from datetime import datetime

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    bringup_pkg = get_package_share_directory('tortoisebot_bringup')
    nav_pkg = get_package_share_directory('tortoisebot_navigation')
    autobringup_launch = os.path.join(
        bringup_pkg,
        'launch',
        'autobringup.launch.py',
    )
    default_map = os.path.join(nav_pkg, 'maps', 'explored_map.yaml')
    default_bag_name = datetime.now().strftime('tortoisebot_hardware_%Y%m%d_%H%M%S')

    use_sim_time = LaunchConfiguration('use_sim_time')
    exploration = LaunchConfiguration('exploration')
    map_file = LaunchConfiguration('map_file')
    camera_device = LaunchConfiguration('camera_device')
    camera_driver = LaunchConfiguration('camera_driver')
    record_mcap = LaunchConfiguration('record_mcap')
    launch_rviz = LaunchConfiguration('launch_rviz')
    enable_imu = LaunchConfiguration('enable_imu')
    enable_camera = LaunchConfiguration('enable_camera')
    enable_image_optimizer = LaunchConfiguration('enable_image_optimizer')
    enable_foxglove_bridge = LaunchConfiguration('enable_foxglove_bridge')
    image_downsample_width = LaunchConfiguration('image_downsample_width')
    image_downsample_height = LaunchConfiguration('image_downsample_height')
    bag_dir = LaunchConfiguration('bag_dir')
    bag_name = LaunchConfiguration('bag_name')

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='False',
                              description='False=Real Robot, True=Ignition simulation'),
        DeclareLaunchArgument('exploration', default_value='True',
                              description='True=SLAM mapping, False=Map-based Nav'),
        DeclareLaunchArgument('map_file', default_value=default_map,
                              description='Path to saved map yaml when exploration=False'),
        DeclareLaunchArgument('camera_device', default_value='/dev/video0',
                              description='V4L2 camera device path when camera_driver:=v4l2'),
        DeclareLaunchArgument('camera_driver', default_value='libcamera',
                              description='Camera driver: libcamera for Pi CSI, v4l2 for USB webcams'),
        DeclareLaunchArgument('record_mcap', default_value='False',
                              description='Record hardware topics to MCAP when use_sim_time=False'),
        DeclareLaunchArgument('launch_rviz', default_value='False',
                              description='Launch RViz on the robot. Usually false for headless Pi.'),
        DeclareLaunchArgument('enable_imu', default_value='False',
                              description='Start the BNO055 IMU node when use_sim_time=False'),
        DeclareLaunchArgument('enable_camera', default_value='False',
                              description='Start the camera node when use_sim_time=False'),
        DeclareLaunchArgument('enable_image_optimizer', default_value='True',
                              description='Publish mono8 optimized camera topics when use_sim_time=False'),
        DeclareLaunchArgument('enable_foxglove_bridge', default_value='False',
                              description='Expose live ROS data and client publishing over Foxglove WebSocket'),
        DeclareLaunchArgument('image_downsample_width', default_value='320',
                              description='Width for /camera/image_mono_downsampled'),
        DeclareLaunchArgument('image_downsample_height', default_value='240',
                              description='Height for /camera/image_mono_downsampled'),
        DeclareLaunchArgument('bag_dir', default_value=os.path.expanduser('~/tortoisebot_mcap'),
                              description='Directory where MCAP rosbag folders are written'),
        DeclareLaunchArgument('bag_name', default_value=default_bag_name,
                              description='MCAP rosbag folder name when record_mcap=True'),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(autobringup_launch),
            launch_arguments={
                'use_sim_time': use_sim_time,
                'exploration': exploration,
                'map_file': map_file,
                'camera_device': camera_device,
                'camera_driver': camera_driver,
                'record_mcap': record_mcap,
                'launch_rviz': launch_rviz,
                'enable_imu': enable_imu,
                'enable_camera': enable_camera,
                'enable_image_optimizer': enable_image_optimizer,
                'enable_foxglove_bridge': enable_foxglove_bridge,
                'image_downsample_width': image_downsample_width,
                'image_downsample_height': image_downsample_height,
                'bag_dir': bag_dir,
                'bag_name': bag_name,
            }.items(),
        ),
    ])
