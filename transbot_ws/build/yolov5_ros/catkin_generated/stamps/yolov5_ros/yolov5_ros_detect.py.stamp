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
from numpy import random
import numpy as np

# YOLOv5 경로 설정 (roslaunch 실행 시 기본 cwd는 ~/.ros 이므로 절대경로 지정)
YOLOV5_DIR = os.path.expanduser('~/transbot_ws/src/yolov5_ros/yolov5')
if YOLOV5_DIR not in sys.path:
    sys.path.append(YOLOV5_DIR)

from std_msgs.msg import String
from models.experimental import attempt_load
from utils.general import check_img_size, non_max_suppression, scale_coords
from utils.torch_utils import select_device

# 카메라 설정 함수
def configure_camera(width, height, fps):
    # 파이프라인 생성
    pipeline = rs.pipeline()

    # 파이프라인 구성
    config = rs.config()

    # 카메라 설정 (해상도, FPS)
    config.enable_stream(rs.stream.depth, width, height, rs.format.z16, fps)
    config.enable_stream(rs.stream.color, width, height, rs.format.bgr8, fps)

    # 카메라 시작
    pipeline.start(config)

    return pipeline

# 카메라에서 프레임을 캡처하고 YOLOv5에 입력하는 함수
def capture_video_and_detect(width=640, height=480, fps=30):
    # 카메라 구성
    pipeline = configure_camera(width, height, fps)

    # 장치 설정
    device = select_device(opt.device)
    half = (device.type != 'cpu')
    if half:
        print("Using FP16 mode for inference")

    # 모델 로드
    model = attempt_load(opt.weights, map_location=device)
    stride = int(model.stride.max())
    imgsz = check_img_size(opt.img_size, s=stride)

    if half:
        model.half()  # FP16 적용

    # YOLOv5 클래스 이름 가져오기
    names = model.module.names if hasattr(model, 'module') else model.names
    colors = [[random.randint(0, 255) for _ in range(3)] for _ in names]

    # Warm-up
    if device.type != 'cpu':
        dummy = torch.zeros(1, 3, imgsz, imgsz).to(device)
        if half:
            dummy = dummy.half()
        else:
            dummy = dummy.float()
        _ = model(dummy)  # GPU 초기화

    try:
        while True:
            # 프레임 캡처
            frames = pipeline.wait_for_frames()

            # 컬러 및 깊이 프레임 얻기
            color_frame = frames.get_color_frame()
            depth_frame = frames.get_depth_frame()

            # 컬러 및 깊이 이미지를 numpy 배열로 변환
            color_image = np.asanyarray(color_frame.get_data())
            depth_image = np.asanyarray(depth_frame.get_data())

            # YOLOv5 입력을 위한 전처리
            img = torch.from_numpy(color_image).to(device)
            img = img.permute(2, 0, 1).float()  # HWC -> CHW
            img /= 255.0  # 0-1 정규화

            if img.ndimension() == 3:
                img = img.unsqueeze(0)

            # Inference (YOLOv5 모델 예측)
            pred = model(img, augment=opt.augment)[0]

            # NMS
            pred = non_max_suppression(pred, opt.conf_thres, opt.iou_thres,
                                       classes=opt.classes, agnostic=opt.agnostic_nms)

            # 결과 처리
            for i, det in enumerate(pred):
                im0 = color_image.copy()  # .copy() 없이 참조 사용
                if det is not None and len(det):
                    det[:, :4] = scale_coords(img.shape[2:], det[:, :4], im0.shape).round()
                    for *xyxy, conf, cls in reversed(det):
                        x1, y1, x2, y2 = [int(x.item()) for x in xyxy]
                        x_center = (x1 + x2) / 2
                        y_center = (y1 + y2) / 2
                        msg = f"{names[int(cls)]}: Center=({x_center:.2f},{y_center:.2f}), conf={conf:.2f}"
                        pub.publish(msg)

                # YOLOv5 결과 이미지 출력
                cv2.imshow("YOLOv5 + Depth", im0)
                cv2.imshow("Depth Frame", depth_image)

            # 'q'를 눌러 종료
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        # 카메라 종료
        pipeline.stop()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    sys.argv = [arg for arg in sys.argv if not arg.startswith('__')]
    parser = argparse.ArgumentParser()
    parser.add_argument('--weights', type=str,
                        default=os.path.expanduser('~/transbot_ws/src/yolov5_ros/yolov5/best.pt'),
                        help='model path')
    parser.add_argument('--source', type=str, default=os.path.expanduser('2'),
                        help='source')
    parser.add_argument('--img-size', type=int, default=640,
                        help='inference size')
    parser.add_argument('--conf-thres', type=float, default=0.50,
                        help='object confidence threshold')
    parser.add_argument('--iou-thres', type=float, default=0.45,
                        help='IOU threshold for NMS')
    parser.add_argument('--device', default='0', help='cuda device or cpu')
    parser.add_argument('--augment', action='store_true', help='augmented inference')
    parser.add_argument('--classes', nargs='+', type=int, help='filter by classes')
    parser.add_argument('--agnostic-nms', action='store_true', help='class‑agnostic NMS')
    parser.add_argument('--update', action='store_true', help='update all models')
    opt = parser.parse_args()

    rospy.init_node('yolov5_node', anonymous=True)
    pub = rospy.Publisher('/yolov5/detections', String, queue_size=10)

    # torch.no_grad 범위로 전체 래핑
    with torch.no_grad():
        if opt.update:
            for opt.weights in ['best.pt']:
                detect()
                # strip_optimizer(opt.weights)  # 모델 경량화용 함수만 필요할 때 사용
        else:
            capture_video_and_detect(width=1280, height=720, fps=30)  # 예시: 1280x720 해상도, 30 FPS

