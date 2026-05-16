#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pyrealsense2 as rs
import numpy as np
import cv2
import torch
import rospy
from geometry_msgs.msg import Point
from std_msgs.msg import String

# ROS 노드 초기화
rospy.init_node('yolo_realsense_depth_node', anonymous=True)
pub_3d = rospy.Publisher('/object_position_3d', Point, queue_size=10)
pub_label = rospy.Publisher('/object_label', String, queue_size=10)

# --- YOLOv5 모델 로드 ---
model = torch.hub.load('ultralytics/yolov5', 'custom', path='best.pt', force_reload=False)
model.conf = 0.5  # confidence threshold

# --- Realsense 설정 ---
pipeline = rs.pipeline()
config = rs.config()

# RGB + Depth 스트림 동시 enable
config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)

# 파이프라인 시작
profile = pipeline.start(config)

# Depth 스케일 (단위: 미터)
depth_sensor = profile.get_device().first_depth_sensor()
depth_scale = depth_sensor.get_depth_scale()
print(f"[INFO] Depth Scale: {depth_scale}")

# 내부 파라미터 (D435 예시)
intrinsics = profile.get_stream(rs.stream.color).as_video_stream_profile().get_intrinsics()
fx, fy, cx, cy = intrinsics.fx, intrinsics.fy, intrinsics.ppx, intrinsics.ppy
print(f"[INFO] Camera intrinsics: fx={fx}, fy={fy}, cx={cx}, cy={cy}")

try:
    while not rospy.is_shutdown():
        frames = pipeline.wait_for_frames()
        color_frame = frames.get_color_frame()
        depth_frame = frames.get_depth_frame()
        if not color_frame or not depth_frame:
            continue

        # numpy 변환
        color_img = np.asanyarray(color_frame.get_data())
        depth_img = np.asanyarray(depth_frame.get_data())

        # YOLOv5 추론
        results = model(color_img)
        detections = results.pandas().xyxy[0]

        for _, row in detections.iterrows():
            x1, y1, x2, y2, conf, cls = row[:6]
            label = str(row['name'])

            # 중심점 좌표
            cx_box = int((x1 + x2) / 2)
            cy_box = int((y1 + y2) / 2)

            # 깊이값 (단위: 미터)
            depth_value = depth_img[cy_box, cx_box] * depth_scale
            if depth_value == 0:
                continue  # 깊이 정보 없는 경우 skip

            # 3D 좌표 계산
            X = (cx_box - cx) * depth_value / fx
            Y = (cy_box - cy) * depth_value / fy
            Z = depth_value

            # ROS 발행
            pub_3d.publish(Point(X, Y, Z))
            pub_label.publish(label)

            # 디버깅 출력
            print(f"[INFO] {label}: X={X:.3f} Y={Y:.3f} Z={Z:.3f}")

            # 시각화
            cv2.circle(color_img, (cx_box, cy_box), 5, (0,255,0), -1)
            cv2.putText(color_img, f"{label} {Z:.2f}m", (cx_box-40, cy_box-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,0), 2)

        # 결과 표시
        cv2.imshow('YOLOv5 + Depth', color_img)
        if cv2.waitKey(1) == ord('q'):
            break

finally:
    pipeline.stop()
    cv2.destroyAllWindows()

