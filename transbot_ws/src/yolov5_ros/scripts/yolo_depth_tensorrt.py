#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rospy
import argparse
import time
import pyrealsense2 as rs
import cv2
import numpy as np
from std_msgs.msg import String
from geometry_msgs.msg import Point
import sys
import os
import torch  # for NMS & decoding

# TensorRT
import tensorrt as trt
import pycuda.driver as cuda
import pycuda.autoinit

# ============================================
# CLASS NAMES
# ============================================
CLASS_NAMES = ['ripe', 'unripe', 'rotten']

# ============================================
# GLOBAL FLAGS
# ============================================
detect_start = 1
detect_stop = 1

pub_3d = None
cls_pub = None
d2t = None

# YOLOv5 path (for utils)
YOLOV5_DIR = os.path.expanduser('~/transbot_ws/src/yolov5_ros/yolov5')
if YOLOV5_DIR not in sys.path:
    sys.path.append(YOLOV5_DIR)

from utils.general import non_max_suppression, scale_coords
from utils.datasets import letterbox


# ============================================
# TensorRT YOLOv5
# ============================================
class TrtYOLOv5:
    def __init__(self, engine_file_path, input_shape=(640, 640),
                 conf_thres=0.5, iou_thres=0.5):

        self.input_h, self.input_w = input_shape
        self.conf_thres = conf_thres
        self.iou_thres = iou_thres

        self.strides = [8, 16, 32]
        self.anchors = torch.tensor(
            [
                [[1.25000, 1.62500],
                 [2.00000, 3.75000],
                 [4.12500, 2.87500]],
                [[1.87500, 3.81250],
                 [3.87500, 2.81250],
                 [3.68750, 7.43750]],
                [[3.62500, 2.81250],
                 [4.87500, 6.18750],
                 [11.65625, 10.18750]]
            ],
            dtype=torch.float32
        )

        self.anchor_grids = []
        for i, s in enumerate(self.strides):
            self.anchor_grids.append(self.anchors[i] * s)

        self.logger = trt.Logger(trt.Logger.WARNING)
        self.runtime = trt.Runtime(self.logger)

        if not os.path.exists(engine_file_path):
            raise FileNotFoundError(engine_file_path)

        with open(engine_file_path, "rb") as f:
            engine_data = f.read()
            self.engine = self.runtime.deserialize_cuda_engine(engine_data)

        self.context = self.engine.create_execution_context()

        # Dynamic input support
        try:
            binding_idx = self.engine.get_binding_index(self.engine[0])
            shape = self.engine.get_binding_shape(binding_idx)
            if -1 in shape:
                self.context.set_binding_shape(binding_idx, (1, 3, self.input_h, self.input_w))
        except:
            pass

        self.inputs, self.outputs, self.bindings, self.stream, self.output_shapes = self.allocate_buffers()
        self.input_dtype = self.inputs[0]["host"].dtype

    def allocate_buffers(self):
        inputs, outputs, bindings = [], [], []
        output_shapes = []
        stream = cuda.Stream()

        for binding in self.engine:
            binding_shape = self.engine.get_binding_shape(binding)
            size = trt.volume(binding_shape)
            dtype = trt.nptype(self.engine.get_binding_dtype(binding))

            host_mem = cuda.pagelocked_empty(size, dtype)
            device_mem = cuda.mem_alloc(host_mem.nbytes)

            bindings.append(int(device_mem))

            if self.engine.binding_is_input(binding):
                inputs.append({"host": host_mem, "device": device_mem})
            else:
                outputs.append({"host": host_mem, "device": device_mem})
                output_shapes.append(binding_shape)

        return inputs, outputs, bindings, stream, output_shapes

    def _decode_single(self, x, anchor_grid, stride):
        bs, na, ny, nx, no = x.shape

        x = x.sigmoid()

        yv, xv = torch.meshgrid(torch.arange(ny), torch.arange(nx))
        grid = torch.stack((xv, yv), 2).float().to(x.device)
        grid = grid.view(1, 1, ny, nx, 2)

        anchor_grid = anchor_grid.to(x.device).view(1, na, 1, 1, 2)

        x[..., 0:2] = (x[..., 0:2] * 2.0 - 0.5 + grid) * stride
        x[..., 2:4] = ((x[..., 2:4] * 2.0) ** 2) * anchor_grid

        return x.view(1, -1, no)

    def infer(self, img):
        # preprocess
        img_in = letterbox(img, (self.input_h, self.input_w), stride=32, auto=False)[0]
        img_in = img_in.transpose((2, 0, 1))
        img_in = np.ascontiguousarray(img_in).astype(self.input_dtype)
        img_in /= np.array(255.0, dtype=self.input_dtype)

        np.copyto(self.inputs[0]["host"], img_in.ravel())
        cuda.memcpy_htod_async(self.inputs[0]["device"], self.inputs[0]["host"], self.stream)

        # inference
        self.context.execute_async_v2(self.bindings, self.stream.handle, None)

        for out in self.outputs:
            cuda.memcpy_dtoh_async(out["host"], out["device"], self.stream)
        self.stream.synchronize()

        # decode
        decoded = []
        for i, out in enumerate(self.outputs):
            shape = self.output_shapes[i]
            x = torch.from_numpy(np.array(out["host"]).reshape(shape)).float()
            decoded.append(self._decode_single(x, self.anchor_grids[i], self.strides[i]))

        pred = torch.cat(decoded, dim=1)
        det = non_max_suppression(pred, self.conf_thres, self.iou_thres)[0]
        return det


# ============================================
# DEPTH & CAMERA
# ============================================
def configure_camera(width, height, fps):
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.depth, width, height, rs.format.z16, fps)
    config.enable_stream(rs.stream.color, width, height, rs.format.bgr8, fps)
    pipeline.start(config)
    return pipeline

def get_camera_intrinsics(pipeline, align):
    frames = pipeline.wait_for_frames()
    aligned = align.process(frames)
    color_frame = aligned.get_color_frame()
    intrinsics = color_frame.profile.as_video_stream_profile().get_intrinsics()
    return intrinsics

def get_depth_at_center(x, y, depth_image):
    h, w = depth_image.shape
    x = int(np.clip(x, 0, w - 1))
    y = int(np.clip(y, 0, h - 1))
    depth_value = depth_image[y, x]
    if depth_value == 0:
        return None
    return depth_value

def get_3d_coordinates(x, y, depth, intrinsics):
    fx, fy = intrinsics.fx, intrinsics.fy
    cx, cy = intrinsics.ppx, intrinsics.ppy
    Z = depth / 1000.0
    X = - (x - cx) * Z / fx
    Y = - (y - cy) * Z / fy
    return X, Y, Z


# ============================================
# Publishers
# ============================================
def publish_3d_point(X, Y, Z):
    if pub_3d is None:
        return
    pt = Point()
    pt.y = X
    pt.z = Y
    pt.x = Z
    pub_3d.publish(pt)


# ============================================
# CALLBACKS
# ============================================
def m2d_callback(msg):
    rospy.sleep(2)
    global detect_start
    detect_start = 1

def t2d_callback(msg):
    rospy.sleep(2)
    global detect_stop
    detect_stop = 0


# ============================================
# MAIN LOOP
# ============================================
def capture_video_and_detect(width, height, fps, opt):
    global detect_start, detect_stop, d2t, cls_pub

    pipeline = configure_camera(width, height, fps)
    align = rs.align(rs.stream.color)
    intrinsics = get_camera_intrinsics(pipeline, align)

    model = TrtYOLOv5(
        engine_file_path=opt.weights,
        input_shape=(opt.img_size, opt.img_size),
        conf_thres=opt.conf_thres,
        iou_thres=opt.iou_thres
    )

    TIMEOUT = 4
    detection_successful = False
    last_detection_time = time.time()

    while not rospy.is_shutdown():

        now = time.time()
        if detection_successful:
            last_detection_time = now

        if now - last_detection_time > TIMEOUT:
            if d2t:
                d2t.publish("start")
            detect_stop = 1

        frames = pipeline.wait_for_frames()
        aligned = align.process(frames)
        color_frame = aligned.get_color_frame()
        depth_frame = aligned.get_depth_frame()
        if not color_frame or not depth_frame:
            continue

        color_img = np.asanyarray(color_frame.get_data())
        depth_img = np.asanyarray(depth_frame.get_data())
        img_rgb = cv2.cvtColor(color_img, cv2.COLOR_BGR2RGB)

        pred = model.infer(img_rgb)
        detection_successful = False

        if pred is not None and len(pred):
            detection_successful = True

            pred[:, :4] = scale_coords(
                (opt.img_size, opt.img_size),
                pred[:, :4],
                img_rgb.shape
            ).round()

            for *xyxy, conf, cls in reversed(pred):
                x1, y1, x2, y2 = [int(v) for v in xyxy]
                x_center = (x1 + x2) / 2
                y_center = (y1 + y2) / 2

                class_id = int(cls.item())

                label = f"{CLASS_NAMES[class_id]} {conf:.2f}"
                cv2.putText(color_img, label, (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)

                depth_value = get_depth_at_center(x_center, y_center, depth_img)
                if depth_value:
                    X, Y, Z = get_3d_coordinates(x_center, y_center, depth_value, intrinsics)
                    cls_pub.publish(str(class_id))  # 숫자로 전달
                    publish_3d_point(X, Y, Z)


                    detect_start = 0
                    while detect_start == 0:
                        rospy.sleep(0.1)

        if detect_stop:
            detection_successful = True

        while detect_stop:
            rospy.sleep(0.1)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    pipeline.stop()
    cv2.destroyAllWindows()


# ============================================
# MAIN
# ============================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--weights', type=str,
                        default=os.path.expanduser('~/transbot_ws/src/yolov5_ros/yolov5/strawberry.trt'))
    parser.add_argument('--img-size', type=int, default=640)
    parser.add_argument('--conf-thres', type=float, default=0.50)
    parser.add_argument('--iou-thres', type=float, default=0.45)
    argv = rospy.myargv(argv=sys.argv)
    opt = parser.parse_args(argv[1:])

    rospy.init_node("yolov5_trt_node", anonymous=True)

    pub_3d = rospy.Publisher("/depth_3d_points", Point, queue_size=10)
    cls_pub = rospy.Publisher("/detected_class", String, queue_size=10)
    d2t = rospy.Publisher("/d2t", String, queue_size=10)

    rospy.Subscriber("/t2d", String, t2d_callback)
    rospy.Subscriber("/m2d", String, m2d_callback)

    capture_video_and_detect(640, 480, 30, opt)
