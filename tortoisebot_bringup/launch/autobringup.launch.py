#!/usr/bin/env python3
import os
from datetime import datetime

from launch import LaunchDescription
from launch.actions import (
    SetEnvironmentVariable,
    IncludeLaunchDescription,
    DeclareLaunchArgument,
    TimerAction,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import EnvironmentVariable, LaunchConfiguration, PythonExpression
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from ament_index_python.packages import get_package_share_directory


def real_robot_and_enabled(use_sim_time, enabled):
    return PythonExpression([
        "'true' if '", use_sim_time, "'.lower() == 'false' and '",
        enabled,
        "'.lower() == 'true' else 'false'",
    ])


def real_robot_and_all_enabled(use_sim_time, first_enabled, second_enabled):
    return PythonExpression([
        "'true' if '", use_sim_time, "'.lower() == 'false' and '",
        first_enabled, "'.lower() == 'true' and '",
        second_enabled,
        "'.lower() == 'true' else 'false'",
    ])


def real_robot_enabled_and_driver(use_sim_time, enabled, camera_driver, expected_driver):
    return PythonExpression([
        "'true' if '", use_sim_time, "'.lower() == 'false' and '",
        enabled, "'.lower() == 'true' and '",
        camera_driver, "'.lower() == '", expected_driver,
        "' else 'false'",
    ])


def launch_rviz_when(use_sim_time, launch_rviz, exploration, expected_exploration):
    return PythonExpression([
        "'true' if '", use_sim_time, "'.lower() == 'false' and '",
        launch_rviz, "'.lower() == 'true' and '",
        exploration, "'.lower() == '", expected_exploration,
        "' else 'false'",
    ])


def generate_launch_description():
    default_bag_name = datetime.now().strftime('tortoisebot_hardware_%Y%m%d_%H%M%S')

    desc_pkg = get_package_share_directory('tortoisebot_description')
    gazebo_pkg = get_package_share_directory('tortoisebot_gazebo')
    slam_pkg = get_package_share_directory('tortoisebot_slam')
    nav_pkg = get_package_share_directory('tortoisebot_navigation')
    lidar_pkg = get_package_share_directory('ydlidar_ros2_driver')
    bringup_pkg = get_package_share_directory('tortoisebot_bringup')

    default_map = os.path.join(nav_pkg, 'maps', 'explored_map.yaml')
    sim_rviz_config = os.path.join(desc_pkg, 'rviz', 'simulation.rviz')
    nav_rviz_config = os.path.join(desc_pkg, 'rviz', 'nav2.rviz')
    lidar_params = os.path.join(lidar_pkg, 'params', 'ydlidar.yaml')
    ekf_slam_params = os.path.join(slam_pkg, 'config', 'ekf.yaml')

    use_sim_time = LaunchConfiguration('use_sim_time')
    exploration = LaunchConfiguration('exploration')
    map_file = LaunchConfiguration('map_file')
    camera_device = LaunchConfiguration('camera_device')
    camera_driver = LaunchConfiguration('camera_driver')
    record_mcap = LaunchConfiguration('record_mcap')
    launch_rviz = LaunchConfiguration('launch_rviz')
    enable_imu = LaunchConfiguration('enable_imu')
    enable_camera = LaunchConfiguration('enable_camera')
    enable_slam = LaunchConfiguration('enable_slam')
    enable_navigation = LaunchConfiguration('enable_navigation')
    enable_image_optimizer = LaunchConfiguration('enable_image_optimizer')
    enable_foxglove_bridge = LaunchConfiguration('enable_foxglove_bridge')
    foxglove_remote_access = LaunchConfiguration('foxglove_remote_access')
    foxglove_device_token = LaunchConfiguration('foxglove_device_token')
    image_downsample_width = LaunchConfiguration('image_downsample_width')
    image_downsample_height = LaunchConfiguration('image_downsample_height')
    bag_dir = LaunchConfiguration('bag_dir')
    bag_name = LaunchConfiguration('bag_name')

    world_file = os.path.join(gazebo_pkg, 'worlds', 'nav2_test_world.sdf')

    ignition_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(gazebo_pkg, 'launch', 'ignition_sim.launch.py')),
        launch_arguments={
            'world': world_file,
            'spawn_x': '0.0',
            'spawn_y': '0.0',
        }.items(),
        condition=IfCondition(use_sim_time),
    )

    state_publisher = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(desc_pkg, 'launch', 'state_publisher.launch.py')),
        launch_arguments={'use_sim_time': 'False'}.items(),
        condition=UnlessCondition(use_sim_time),
    )

    lidar = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(lidar_pkg, 'launch', 'ydlidar_launch.py')),
        launch_arguments={'params_file': lidar_params}.items(),
        condition=UnlessCondition(use_sim_time),
    )

    imu = Node(
        package='tortoisebot_imu',
        executable='imu_node.py',
        name='imu_publisher',
        output='screen',
        condition=IfCondition(real_robot_and_enabled(use_sim_time, enable_imu)),
    )

    motors = Node(
        package='tortoisebot_firmware',
        executable='differential.py',
        name='differential',
        output='screen',
        condition=UnlessCondition(use_sim_time),
    )

    libcamera = Node(
        package='camera_ros',
        executable='camera_node',
        name='camera_node',
        namespace='camera',
        output='screen',
        parameters=[{
            'width': 640,
            'height': 480,
            'format': 'RGB888',
            'frame_id': 'camera_link',
        }],
        remappings=[
            ('~/image_raw', '/camera/image_raw'),
            ('~/camera_info', '/camera/camera_info'),
        ],
        condition=IfCondition(real_robot_enabled_and_driver(
            use_sim_time, enable_camera, camera_driver, 'libcamera')),
    )

    v4l2_camera = Node(
        package='v4l2_camera',
        executable='v4l2_camera_node',
        name='camera_node',
        namespace='camera',
        output='screen',
        parameters=[{
            'video_device': camera_device,
            'image_size': [640, 480],
            'pixel_format': 'YUYV',
            'output_encoding': 'rgb8',
            'camera_frame_id': 'camera_link',
        }],
        condition=IfCondition(real_robot_enabled_and_driver(
            use_sim_time, enable_camera, camera_driver, 'v4l2')),
    )

    image_optimizer = Node(
        package='tortoisebot_bringup',
        executable='image_optimizer.py',
        name='image_optimizer',
        output='screen',
        parameters=[{
            'input_topic': '/camera/image_raw',
            'mono_topic': '/camera/image_mono',
            'downsampled_topic': '/camera/image_mono_downsampled',
            'downsample_width': image_downsample_width,
            'downsample_height': image_downsample_height,
        }],
        condition=IfCondition(real_robot_and_all_enabled(
            use_sim_time, enable_camera, enable_image_optimizer)),
    )

    recorder = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(bringup_pkg, 'launch', 'hardware_record.launch.py')),
        launch_arguments={
            'bag_dir': bag_dir,
            'bag_name': bag_name,
        }.items(),
        condition=IfCondition(real_robot_and_enabled(use_sim_time, record_mcap)),
    )

    foxglove_bridge = Node(
        package='foxglove_bridge',
        executable='foxglove_bridge',
        name='foxglove_bridge',
        output='screen',
        parameters=[{
            'remote_access': ParameterValue(foxglove_remote_access, value_type=bool),
            'device_token': foxglove_device_token,
        }],
        condition=IfCondition(real_robot_and_enabled(use_sim_time, enable_foxglove_bridge)),
    )

    ekf = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_filter_node',
        output='screen',
        parameters=[ekf_slam_params, {'use_sim_time': False}],
        condition=IfCondition(PythonExpression([
            "'true' if ('", use_sim_time,
            "' == 'false' or '", use_sim_time,
            "' == 'False') and ('", exploration,
            "' == 'false' or '", exploration,
            "' == 'False') else 'false'",
        ])),
    )

    cartographer = TimerAction(
        period=6.0,
        actions=[IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(slam_pkg, 'launch', 'cartographer.launch.py')),
            condition=IfCondition(PythonExpression([
                "'true' if '", enable_slam,
                "'.lower() == 'true' and (('", exploration,
                "'.lower() == 'true') or ('", use_sim_time,
                "'.lower() == 'false')) else 'false'",
            ])),
            launch_arguments={
                'use_sim_time': use_sim_time,
                'is_odom_only': PythonExpression([
                    "'false' if '", exploration,
                    "' == 'true' or '", exploration,
                    "' == 'True' else 'true'",
                ]),
            }.items(),
        )],
    )

    navigation = TimerAction(
        period=14.0,
        actions=[IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(nav_pkg, 'launch', 'navigation_mapbased.launch.py')),
            condition=IfCondition(PythonExpression([
                "'true' if '", enable_navigation,
                "'.lower() == 'true' and '", exploration,
                "'.lower() == 'false' else 'false'",
            ])),
            launch_arguments={
                'map': map_file,
                'use_sim_time': use_sim_time,
            }.items(),
        )],
    )

    navigation_slam = TimerAction(
        period=20.0,
        actions=[IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(nav_pkg, 'launch', 'navigation_slam.launch.py')),
            condition=IfCondition(PythonExpression([
                "'true' if '", enable_navigation,
                "'.lower() == 'true' and '", exploration,
                "'.lower() == 'true' else 'false'",
            ])),
            launch_arguments={
                'use_sim_time': use_sim_time,
            }.items(),
        )],
    )

    rviz = TimerAction(
        period=8.0,
        actions=[IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(desc_pkg, 'launch', 'rviz.launch.py')),
            launch_arguments={
                'rvizconfig': nav_rviz_config,
                'use_sim_time': use_sim_time,
            }.items(),
            condition=IfCondition(launch_rviz_when(use_sim_time, launch_rviz, exploration, 'true')),
        )],
    )

    rviz_map = TimerAction(
        period=8.0,
        actions=[IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(desc_pkg, 'launch', 'rviz.launch.py')),
            launch_arguments={
                'rvizconfig': sim_rviz_config,
                'use_sim_time': use_sim_time,
            }.items(),
            condition=IfCondition(launch_rviz_when(use_sim_time, launch_rviz, exploration, 'false')),
        )],
    )

    return LaunchDescription([
        SetEnvironmentVariable('RCUTILS_LOGGING_BUFFERED_STREAM', '1'),

        DeclareLaunchArgument('use_sim_time', default_value='True',
                              description='True=Ignition Sim, False=Real Robot'),
        DeclareLaunchArgument('exploration', default_value='True',
                              description='True=SLAM mapping, False=Map-based Nav'),
        DeclareLaunchArgument('map_file', default_value=default_map,
                              description='Path to saved map yaml (used when exploration=False)'),
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
        DeclareLaunchArgument('enable_slam', default_value='True',
                              description='Start Cartographer SLAM/odom when use_sim_time=False'),
        DeclareLaunchArgument('enable_navigation', default_value='True',
                              description='Start Nav2 navigation when use_sim_time=False'),
        DeclareLaunchArgument('enable_image_optimizer', default_value='True',
                              description='Publish mono8 optimized camera topics when use_sim_time=False'),
        DeclareLaunchArgument('enable_foxglove_bridge', default_value='False',
                              description='Expose live ROS data and client publishing over Foxglove WebSocket'),
        DeclareLaunchArgument('foxglove_remote_access', default_value='False',
                              description='Connect Foxglove Bridge to Foxglove remote access'),
        DeclareLaunchArgument('foxglove_device_token',
                              default_value=EnvironmentVariable('FOXGLOVE_DEVICE_TOKEN', default_value=''),
                              description='Foxglove device token for remote access'),
        DeclareLaunchArgument('image_downsample_width', default_value='320',
                              description='Width for /camera/image_mono_downsampled'),
        DeclareLaunchArgument('image_downsample_height', default_value='240',
                              description='Height for /camera/image_mono_downsampled'),
        DeclareLaunchArgument('bag_dir', default_value=os.path.expanduser('~/tortoisebot_mcap'),
                              description='Directory where MCAP rosbag folders are written'),
        DeclareLaunchArgument('bag_name', default_value=default_bag_name,
                              description='MCAP rosbag folder name when record_mcap=True'),
        ignition_sim,
        state_publisher,
        lidar,
        imu,
        motors,
        libcamera,
        v4l2_camera,
        image_optimizer,
        recorder,
        foxglove_bridge,
        cartographer,
        navigation,
        navigation_slam,
        rviz,
        rviz_map,
    ])
