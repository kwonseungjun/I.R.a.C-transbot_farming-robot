#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
import argparse
import time
import pyrealsense2 as rs
import cv2
import torch
import torch.backends.cudnn as cudnn
import sys
import os
import numpy as np
from numpy import random
from std_msgs.msg import String
from geometry_msgs.msg import Point

# YOLOv5 경로 설정
YOLOV5_DIR = os.path.expanduser('~/transbot_ws/src/yolov5_ros/yolov5')
if YOLOV5_DIR not in sys.path:
    sys.path.append(YOLOV5_DIR)

from models.experimental import attempt_load
from utils.general import check_img_size, non_max_suppression, scale_coords
from utils.torch_utils import select_device
from utils.datasets import letterbox  # YOLO 전처리

# 카메라 설정 함수
def configure_camera(width, height, fps):
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.depth, width, height, rs.format.z16, fps)
    config.enable_stream(rs.stream.color, width, height, rs.format.bgr8, fps)
    pipeline.start(config)
    return pipeline

# 카메라 내부 파라미터 가져오기 (정렬된 color 기준)
def get_camera_intrinsics(pipeline, align):
    frames = pipeline.wait_for_frames()
    aligned_frames = align.process(frames)

    color_frame = aligned_frames.get_color_frame()
    color_profile = color_frame.profile.as_video_stream_profile()
    intrinsics = color_profile.get_intrinsics()

    # 내부 파라미터 출력
    print("--- Color camera intrinsics (USED FOR 3D) ---")
    print(f"fx: {intrinsics.fx}, fy: {intrinsics.fy}")
    print(f"cx: {intrinsics.ppx}, cy: {intrinsics.ppy}")
    print(f"width: {intrinsics.width}, height: {intrinsics.height}")

    return intrinsics

# 픽셀 → 3D 변환
def get_3d_coordinates(x, y, depth_value, intrinsics):
    fx = intrinsics.fx
    fy = intrinsics.fy
    cx = intrinsics.ppx
    cy = intrinsics.ppy

    Z = depth_value / 1000.0
    X = (x - cx) * Z / fx
    Y = - (y - cy) * Z / fy

    return X, Y, Z

def get_depth_at_center(x, y, depth_image):
    h, w = depth_image.shape
    x = int(np.clip(x, 0, w - 1))
    y = int(np.clip(y, 0, h - 1))

    depth_value = depth_image[y, x]
    if depth_value == 0:
        return None

    return depth_value

def publish_3d_point(X, Y, Z):
    point = Point()
    point.x = X
    point.y = Y
    point.z = Z
    pub_3d.publish(point)

# RGB-Depth 정렬 + YOLOv5 탐지
def capture_video_and_detect(width=640, height=480, fps=30):
    pipeline = configure_camera(width, height, fps)
    align = rs.align(rs.stream.color)

    # 수정 완료: intrinsics는 align 적용 뒤의 color 기준
    intrinsics = get_camera_intrinsics(pipeline, align)

    # --- 장치 설정 ---
    device = select_device(opt.device)
    half = device.type != 'cpu'
    if half:
        print("Using FP16 mode for inference")

    model = attempt_load(opt.weights, map_location=device)
    stride = int(model.stride.max())
    imgsz = check_img_size(opt.img_size, s=stride)
    if half:
        model.half()

    names = model.module.names if hasattr(model, 'module') else model.names
    colors = [[random.randint(0, 255) for _ in range(3)] for _ in names]

    if device.type != 'cpu':
        dummy = torch.zeros(1, 3, imgsz, imgsz).to(device)
        _ = model(dummy.half() if half else dummy.float())

    print(f" 해상도: {width}x{height}, FPS: {fps}")

    try:
        while not rospy.is_shutdown():
            frames = pipeline.wait_for_frames()
            aligned_frames = align.process(frames)

            color_frame = aligned_frames.get_color_frame()
            depth_frame = aligned_frames.get_depth_frame()
            if not color_frame or not depth_frame:
                continue

            color_image = np.asanyarray(color_frame.get_data())
            depth_image = np.asanyarray(depth_frame.get_data())

            img0 = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)
            img = letterbox(img0, imgsz, stride=stride)[0]
            img = img.transpose((2, 0, 1))
            img = np.ascontiguousarray(img)
            img = torch.from_numpy(img).to(device)
            img = img.half() if half else img.float()
            img /= 255.0
            if img.ndimension() == 3:
                img = img.unsqueeze(0)

            pred = model(img, augment=opt.augment)[0]
            pred = non_max_suppression(pred, opt.conf_thres, opt.iou_thres,
                                       classes=opt.classes, agnostic=opt.agnostic_nms)

            for det in pred:
                im0 = color_image.copy()
                if len(det):
                    det[:, :4] = scale_coords(img.shape[2:], det[:, :4], im0.shape).round()

                    for *xyxy, conf, cls in reversed(det):
                        x1, y1, x2, y2 = [int(x.item()) for x in xyxy]
                        x_center = (x1 + x2) / 2
                        y_center = (y1 + y2) / 2

                        depth_value = get_depth_at_center(x_center, y_center, depth_image)

                        if depth_value:
                            X, Y, Z = get_3d_coordinates(x_center, y_center, depth_value, intrinsics)
                            publish_3d_point(X, Y, Z)

                            label = f'{names[int(cls)]} {conf:.2f}  X={X:.2f}m Y={Y:.2f}m Z={Z:.2f}m'
                            cv2.putText(im0, label, (x1, y1 - 10),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, colors[int(cls)], 2)


                        cv2.rectangle(im0, (x1, y1), (x2, y2), colors[int(cls)], 2)

                cv2.imshow("YOLOv5 RGB", im0)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        pipeline.stop()
        cv2.destroyAllWindows()

# main
if __name__ == '__main__':
    sys.argv = [arg for arg in sys.argv if not arg.startswith('__')]
    parser = argparse.ArgumentParser()
    parser.add_argument('--weights', type=str,
                        default=os.path.expanduser('~/transbot_ws/src/yolov5_ros/yolov5/strawberry.pt'))
    parser.add_argument('--source', type=str, default='0')
    parser.add_argument('--img-size', type=int, default=640)
    parser.add_argument('--conf-thres', type=float, default=0.70)
    parser.add_argument('--iou-thres', type=float, default=0.50)
    parser.add_argument('--device', default='0')
    parser.add_argument('--augment', action='store_true')
    parser.add_argument('--classes', nargs='+', type=int)
    parser.add_argument('--agnostic-nms', action='store_true')
    opt = parser.parse_args()

    rospy.init_node('yolov5_node', anonymous=True)
    pub_3d = rospy.Publisher('/depth_3d_points', Point, queue_size=10)

    capture_video_and_detect()

