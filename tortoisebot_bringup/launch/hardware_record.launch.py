#!/usr/bin/env python3
from datetime import datetime

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import EnvironmentVariable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


RECORD_TOPICS = [
    '/scan',
    '/imu/data',
    '/camera/image_raw/compressed',
    '/camera/image_mono_downsampled',
    '/camera/camera_info',
    '/tf',
    '/tf_static',
    '/cmd_vel',
    '/odom',
    '/lpwm',
    '/rpwm',
    '/ldir',
    '/rdir',
]


def generate_launch_description():
    default_bag_name = datetime.now().strftime('tortoisebot_hardware_%Y%m%d_%H%M%S')

    bag_dir = LaunchConfiguration('bag_dir')
    bag_name = LaunchConfiguration('bag_name')
    storage_config_file = LaunchConfiguration('storage_config_file')
    output_path = PathJoinSubstitution([bag_dir, bag_name])

    record_command = [
        'ros2',
        'bag',
        'record',
        '--storage',
        'mcap',
        '--storage-config-file',
        storage_config_file,
        '--output',
        output_path,
        *RECORD_TOPICS,
    ]

    recorder = ExecuteProcess(
        cmd=record_command,
        output='screen',
        shell=False,
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'bag_dir',
            default_value=PathJoinSubstitution([
                EnvironmentVariable('HOME'),
                'tortoisebot_mcap',
            ]),
            description='Directory where MCAP rosbag folders are written.',
        ),
        DeclareLaunchArgument(
            'bag_name',
            default_value=default_bag_name,
            description='Name of the rosbag folder created under bag_dir.',
        ),
        DeclareLaunchArgument(
            'storage_config_file',
            default_value=PathJoinSubstitution([
                FindPackageShare('tortoisebot_bringup'),
                'config',
                'mcap_writer_options.yaml',
            ]),
            description='MCAP writer storage options used by rosbag2.',
        ),
        recorder,
    ])
