#!/usr/bin/env python
import rospy
from sensor_msgs.msg import Image
from geometry_msgs.msg import Point
import ros_numpy
import numpy as np

class DepthReader:
    def __init__(self):
        rospy.init_node("depth_reader", anonymous=True)
        self.sub_depth = rospy.Subscriber("/camera/depth/image_raw", Image, self.depth_callback)
        self.d2m_pub = rospy.Publisher('/d2m', Point, queue_size=10)
        rospy.on_shutdown(self.cleanup)

    def depth_callback(self, msg):
        depth_image = ros_numpy.numpify(msg)

        center_x = depth_image.shape[1] // 2
        center_y = depth_image.shape[0] // 2

        samples = [
            depth_image[center_y - 3, center_x - 3],
            depth_image[center_y + 3, center_x - 3],
            depth_image[center_y - 3, center_x + 3],
            depth_image[center_y + 3, center_x + 3],
            depth_image[center_y, center_x]
        ]

        valid_samples = [d for d in samples if 40 < d < 80000]
        if valid_samples:
            depth_value = sum(valid_samples) / len(valid_samples)
        else:
            depth_value = 0 

        print("Depth at center: {} mm".format(depth_value))
        
    def cleanup(self):
        print("Shutting down depth reader.")

if __name__ == "__main__":
    reader = DepthReader()
    rospy.spin()
