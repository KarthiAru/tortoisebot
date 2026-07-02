#!/usr/bin/env python3
import cv2
from cv_bridge import CvBridge
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image


class ImageOptimizer(Node):
    def __init__(self):
        super().__init__('image_optimizer')

        self.declare_parameter('input_topic', '/camera/image_raw')
        self.declare_parameter('mono_topic', '/camera/image_mono')
        self.declare_parameter('downsampled_topic', '/camera/image_mono_downsampled')
        self.declare_parameter('downsample_width', 320)
        self.declare_parameter('downsample_height', 240)

        self.input_topic = self.get_parameter('input_topic').value
        self.mono_topic = self.get_parameter('mono_topic').value
        self.downsampled_topic = self.get_parameter('downsampled_topic').value
        self.downsample_width = int(self.get_parameter('downsample_width').value)
        self.downsample_height = int(self.get_parameter('downsample_height').value)

        if self.downsample_width <= 0 or self.downsample_height <= 0:
            raise ValueError('downsample_width and downsample_height must be positive')

        self.bridge = CvBridge()
        self.mono_pub = self.create_publisher(Image, self.mono_topic, 10)
        self.downsampled_pub = self.create_publisher(Image, self.downsampled_topic, 10)
        self.subscription = self.create_subscription(Image, self.input_topic, self.image_callback, 10)

        self.get_logger().info(
            f'Optimizing {self.input_topic} -> {self.mono_topic} and '
            f'{self.downsampled_topic} ({self.downsample_width}x{self.downsample_height}, mono8)'
        )

    def image_callback(self, msg):
        try:
            mono = self.to_mono8(msg)
        except Exception as exc:
            self.get_logger().warn(f'Failed to convert {msg.encoding} image to mono8: {exc}')
            return

        mono_msg = self.bridge.cv2_to_imgmsg(mono, encoding='mono8')
        mono_msg.header = msg.header
        self.mono_pub.publish(mono_msg)

        downsampled = cv2.resize(
            mono,
            (self.downsample_width, self.downsample_height),
            interpolation=cv2.INTER_AREA,
        )
        downsampled_msg = self.bridge.cv2_to_imgmsg(downsampled, encoding='mono8')
        downsampled_msg.header = msg.header
        self.downsampled_pub.publish(downsampled_msg)

    def to_mono8(self, msg):
        encoding = msg.encoding.lower()
        if encoding == 'mono8':
            return self.bridge.imgmsg_to_cv2(msg, desired_encoding='mono8')
        if encoding == 'bgr8':
            bgr = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        if encoding == 'rgb8':
            rgb = self.bridge.imgmsg_to_cv2(msg, desired_encoding='rgb8')
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        # Let cv_bridge handle common compatible color encodings when possible.
        bgr = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)


def main(args=None):
    rclpy.init(args=args)
    node = ImageOptimizer()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
