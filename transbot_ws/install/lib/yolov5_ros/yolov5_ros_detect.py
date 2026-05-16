#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
import argparse
import time
import cv2
import torch
import torch.backends.cudnn as cudnn
import sys
import os
from numpy import random

# YOLOv5 경로 설정 (roslaunch 실행 시 기본 cwd는 ~/.ros 이므로 절대경로 지정)
YOLOV5_DIR = os.path.expanduser('~/transbot_ws/src/yolov5_ros/yolov5')
if YOLOV5_DIR not in sys.path:
    sys.path.append(YOLOV5_DIR)

from std_msgs.msg import String
sys.argv = [arg for arg in sys.argv if not arg.startswith('__')]
from models.experimental import attempt_load
from utils.datasets import LoadStreams
from utils.general import check_img_size, non_max_suppression, scale_coords
from utils.torch_utils import select_device
from utils.plots import plot_one_box  # 바운딩 박스를 그리는 함수 추가

def detect():
    device = select_device(opt.device)
    half = device.type != 'cpu'

    model = attempt_load(opt.weights, map_location=device)
    stride = int(model.stride.max())
    imgsz = check_img_size(opt.img_size, s=stride)
    if half:
        model.half()

    # 스트림 입력만 고려
    dataset = LoadStreams(opt.source, img_size=imgsz, stride=stride)
    names = model.module.names if hasattr(model, 'module') else model.names
    colors = [[random.randint(0, 255) for _ in range(3)] for _ in names]  # 클래스별 색상 설정

    if device.type != 'cpu':
        model(torch.zeros(1, 3, imgsz, imgsz).to(device).type_as(next(model.parameters())))

    for path, img, im0s, vid_cap in dataset:
        if rospy.is_shutdown():
            break

        img = torch.from_numpy(img).to(device)
        img = img.half() if half else img.float()
        img /= 255.0
        if img.ndimension() == 3:
            img = img.unsqueeze(0)

        pred = model(img, augment=opt.augment)[0]
        pred = non_max_suppression(pred, opt.conf_thres, opt.iou_thres, classes=opt.classes, agnostic=opt.agnostic_nms)

        for i, det in enumerate(pred):
            im0 = im0s[i].copy()
            if len(det):
                det[:, :4] = scale_coords(img.shape[2:], det[:, :4], im0.shape).round()
                for *xyxy, conf, cls in reversed(det):
                    x1, y1, x2, y2 = [int(x.item()) for x in xyxy]
                    x_center = (x1 + x2) / 2
                    y_center = (y1 + y2) / 2
                    msg = f"{names[int(cls)]}: Center=({x_center:.2f}, {y_center:.2f}), conf={conf:.2f}"
                    pub.publish(msg)

    rospy.loginfo("Detection finished")
    cv2.destroyAllWindows()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--weights', type=str, default=os.path.expanduser('~/transbot_ws/src/yolov5_ros/yolov5/best.pt'),
                        help='model path')
    parser.add_argument('--source', type=str, default=os.path.expanduser('3'), help='source')
    parser.add_argument('--img-size', type=int, default=640, help='inference size')
    parser.add_argument('--conf-thres', type=float, default=0.50, help='object confidence threshold')
    parser.add_argument('--iou-thres', type=float, default=0.45, help='IOU threshold for NMS')
    parser.add_argument('--device', default='0', help='cuda device or cpu')
    parser.add_argument('--augment', action='store_true', help='augmented inference')
    parser.add_argument('--classes', nargs='+', type=int, help='filter by classes')
    parser.add_argument('--agnostic-nms', action='store_true', help='class-agnostic NMS')
    parser.add_argument('--update', action='store_true', help='update all models')
    opt = parser.parse_args()
    

    rospy.init_node('yolov5_node', anonymous=True)
    pub = rospy.Publisher('/yolov5/detections', String, queue_size=10)

    # ✅ detect() 호출
    with torch.no_grad():
        if opt.update:
            for opt.weights in ['best.pt']:
                detect()
                strip_optimizer(opt.weights)
        else:
            detect()
