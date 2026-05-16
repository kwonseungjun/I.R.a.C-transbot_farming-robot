#!/usr/bin/env python
# -*- coding: utf-8 -*-
import rospy
from sensor_msgs.msg import Image
from geometry_msgs.msg import Point
from std_msgs.msg import String
import ros_numpy
import numpy as np

# Depth 스케일 (이미 토픽에서 고려된 값이면 1.0 사용 가능)
depth_scale = 1.0  # 필요에 따라 조정

# RGB 카메라 해상도 (YOLO 입력)
yolo_width = 1920
yolo_height = 1080
        
class Depth3DCalculator:
    def __init__(self):
        rospy.init_node("depth_3d_calculator", anonymous=True)

        # 깊이 이미지 구독
        self.sub_depth = rospy.Subscriber("/camera/depth/image_rect_raw", Image, self.depth_callback)

        # 바운딩 박스 중심 좌표 구독 (YOLO 노드에서 발행)
        self.sub_bboxes = rospy.Subscriber("/yolov5/detections", String, self.bbox_callback)

        # 3D 좌표 발행
        self.pub_3d_points = rospy.Publisher("/depth_3d_points", Point, queue_size=10)

        # 최신 depth 이미지 저장
        self.latest_depth_image = None

    def depth_callback(self, msg):
        """Depth 이미지 수신"""
        try:
            self.latest_depth_image = ros_numpy.numpify(msg)
        except Exception as e:
            rospy.logerr("Error converting depth image: {}".format(e))

    def bbox_callback(self, msg):
        """YOLO 바운딩 박스 중심 기준 3D 좌표 계산"""
        if self.latest_depth_image is None:
            rospy.logwarn("No depth image received yet.")
            return

        try:
            if "Center: (" in msg.data and ")" in msg.data:
                coordinates = msg.data.split("Center: (")[1].split(")")[0]
                x_yolo, y_yolo = map(float, coordinates.split(","))

                # YOLO 좌표를 depth 이미지 해상도로 변환
                depth_h, depth_w = self.latest_depth_image.shape
                x_pixel = int(np.clip(x_yolo * depth_w / yolo_width, 0, depth_w - 1))
                y_pixel = int(np.clip(y_yolo * depth_h / yolo_height, 0, depth_h - 1))

                # 5x5 주변 영역 평균 깊이 계산
                window_size = 5
                half_win = window_size // 2
                x1 = max(0, x_pixel - half_win)
                x2 = min(depth_w, x_pixel + half_win + 1)
                y1 = max(0, y_pixel - half_win)
                y2 = min(depth_h, y_pixel + half_win + 1)

                depth_window = self.latest_depth_image[y1:y2, x1:x2]
                valid_depths = depth_window[depth_window > 0]  # 0은 무효값

                if valid_depths.size == 0:
                    rospy.logwarn("No valid depth values in 5x5 region around ({}, {})".format(x_pixel, y_pixel))
                    return

                depth_value = np.mean(valid_depths) * depth_scale

                if np.isnan(depth_value) or np.isinf(depth_value) or depth_value <= 0:
                    rospy.logwarn("Invalid depth value around bbox center.")
                    return

                # 이미 내부 파라미터가 고려된 Depth 이미지라면
                # Depth 값 자체를 Z로, X/Y는 픽셀 좌표 비율로 단순 변환 가능
                X = (x_pixel - depth_w / 2) * depth_value / (depth_w / 2)
                Y = (y_pixel - depth_h / 2) * depth_value / (depth_h / 2)
                Z = depth_value

                rospy.loginfo("3D Point: X={:.3f}, Y={:.3f}, Z={:.3f}".format(X, Y, Z))
                self.publish_3d_point(X, Y, Z)

        except Exception as e:
            rospy.logerr("Error in bbox_callback: {}".format(e))

    def publish_3d_point(self, X, Y, Z):
        point = Point()
        point.x = X
        point.y = Y
        point.z = Z
        self.pub_3d_points.publish(point)

if __name__ == "__main__":
    depth_calculator = Depth3DCalculator()
    rospy.spin()

