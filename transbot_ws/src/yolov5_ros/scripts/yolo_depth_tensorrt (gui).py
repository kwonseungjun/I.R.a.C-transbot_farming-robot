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
import torch  # NMS용

# TensorRT 관련 라이브러리
import tensorrt as trt
import pycuda.driver as cuda
import pycuda.autoinit

# =========================
# 클래스 이름
# =========================
CLASS_NAMES = ['ripe', 'unripe', 'rotten']

# =========================
# 전역 플래그
# =========================
detect_start = 1  # 다른 노드에서 인식 재개 허용
detect_stop = 1   # 다른 노드에서 정지 요청

pub_3d = None     # 3D 좌표 publish
d2t = None        # detection → task 알림

# YOLOv5 경로 설정
YOLOV5_DIR = os.path.expanduser('~/transbot_ws/src/yolov5_ros/yolov5')
if YOLOV5_DIR not in sys.path:
    sys.path.append(YOLOV5_DIR)

from utils.general import non_max_suppression, scale_coords
from utils.datasets import letterbox  # ✅ letterbox 전처리 사용


# =========================
# TensorRT YOLOv5 클래스
# =========================
class TrtYOLOv5:
    def __init__(self, engine_file_path, input_shape=(640, 640),
                 conf_thres=0.5, iou_thres=0.5):
        """
        engine_file_path: .trt / .engine 파일 경로
        input_shape: (h, w) - 엔진 입력 크기 (ex. 640x640)
        """
        self.input_h, self.input_w = input_shape
        self.conf_thres = conf_thres
        self.iou_thres = iou_thres

        # =========================
        # YOLOv5 stride, anchors
        # =========================
        self.strides = [8, 16, 32]

        # model.model[-1].anchors (네가 보낸 값)
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
        
        # =========================
        # ★ anchor_grid = anchors * stride (픽셀 단위)
        # =========================
        self.anchor_grids = []
        for i, s in enumerate(self.strides):
            self.anchor_grids.append(self.anchors[i] * s)
        # anchor_grids[i] shape: (3, 2)
        
        # TensorRT 로거 및 런타임
        self.logger = trt.Logger(trt.Logger.WARNING)
        self.runtime = trt.Runtime(self.logger)

        # 엔진 로드
        if not os.path.exists(engine_file_path):
            rospy.logerr(f"[TrtYOLOv5] 엔진 파일을 찾을 수 없습니다: {engine_file_path}")
            raise FileNotFoundError(engine_file_path)

        with open(engine_file_path, "rb") as f:
            engine_data = f.read()
            self.engine = self.runtime.deserialize_cuda_engine(engine_data)

        if self.engine is None:
            rospy.logerr("[TrtYOLOv5] 엔진 디시리얼라이즈 실패")
            raise RuntimeError("Failed to load TensorRT engine")

        self.context = self.engine.create_execution_context()

        # 입출력 버퍼 + 출력 shape 저장
        self.inputs, self.outputs, self.bindings, self.stream, self.output_shapes = self.allocate_buffers()
        self.input_dtype = self.inputs[0]["host"].dtype  # ✅ FP16 엔진이면 host도 FP16

        # ===== dtype 정보 로그 =====
        out_dtype = self.outputs[0]["host"].dtype
        rospy.loginfo(f"[TrtYOLOv5] 첫 번째 출력 버퍼 dtype: {out_dtype}")

        try:
            fp16_fast = self.engine.has_fast_fp16
            int8_fast = self.engine.has_fast_int8
        except AttributeError:
            fp16_fast = False
            int8_fast = False

        rospy.loginfo(f"[TrtYOLOv5] FP16 가속 지원 여부: {fp16_fast}")
        rospy.loginfo(f"[TrtYOLOv5] INT8 가속 지원 여부: {int8_fast}")
        rospy.loginfo("[TrtYOLOv5] TensorRT 엔진 로드 완료")
        rospy.loginfo(f"[TrtYOLOv5] 입력 크기: {self.input_w}x{self.input_h}")

    def allocate_buffers(self):
        inputs, outputs, bindings = [], [], []
        output_shapes = []
        stream = cuda.Stream()

        for binding in self.engine:
            binding_shape = self.engine.get_binding_shape(binding)
            # batch=1 가정 (Jetson Nano에서 동적 배치 안 씀)
            size = trt.volume(binding_shape)
            dtype = trt.nptype(self.engine.get_binding_dtype(binding))

            host_mem = cuda.pagelocked_empty(size, dtype)
            device_mem = cuda.mem_alloc(host_mem.nbytes)

            bindings.append(int(device_mem))
            if self.engine.binding_is_input(binding):
                inputs.append({"host": host_mem, "device": device_mem})
                rospy.loginfo(f"[TrtYOLOv5] 입력 바인딩: {binding}, shape={binding_shape}, dtype={dtype}")
            else:
                outputs.append({"host": host_mem, "device": device_mem})
                output_shapes.append(binding_shape)
                rospy.loginfo(f"[TrtYOLOv5] 출력 바인딩: {binding}, shape={binding_shape}, dtype={dtype}")

        return inputs, outputs, bindings, stream, output_shapes

    def _decode_single(self, x, anchor_grid, stride):
        """
        x: (1,3,ny,nx,no)
        anchor_grid: anchors * stride
        stride: 8/16/32
        """
        bs, na, ny, nx, no = x.shape

        # Sigmoid
        x = x.sigmoid()

        # grid 생성
        yv, xv = torch.meshgrid(
            torch.arange(ny),
            torch.arange(nx),
        )
        grid = torch.stack((xv, yv), 2).float().to(x.device)
        grid = grid.view(1, 1, ny, nx, 2)

        # anchor_grid reshape
        anchor_grid = anchor_grid.to(x.device).view(1, na, 1, 1, 2)

        # center x, y
        x[..., 0:2] = (x[..., 0:2] * 2.0 - 0.5 + grid) * stride

        # width, height
        x[..., 2:4] = ((x[..., 2:4] * 2.0) ** 2) * anchor_grid

        return x.view(1, -1, no)

    def infer(self, image):

        # ----- 전처리 -----
        img = letterbox(image, (self.input_h, self.input_w), stride=32, auto=False)[0]
        img = img.transpose((2, 0, 1))
        img = np.ascontiguousarray(img).astype(self.input_dtype)
        img /= np.array(255.0, dtype=self.input_dtype)

        np.copyto(self.inputs[0]["host"], img.ravel())
        cuda.memcpy_htod_async(self.inputs[0]["device"], self.inputs[0]["host"], self.stream)

        # ----- TRT 실행 -----
        self.context.execute_async_v2(self.bindings, self.stream.handle, None)

        for out in self.outputs:
            cuda.memcpy_dtoh_async(out["host"], out["device"], self.stream)
        self.stream.synchronize()

        # ----- 디코딩 -----
        decoded = []
        for i, out in enumerate(self.outputs):

            shape = self.output_shapes[i]
            x = torch.from_numpy(np.array(out["host"]).reshape(shape)).float()

            # ⭐ anchor_grid + stride 정확히 적용 ⭐
            decoded.append(
                self._decode_single(x, self.anchor_grids[i], self.strides[i])
            )

        # 전체 스케일 concat
        pred = torch.cat(decoded, dim=1)

        # NMS
        det = non_max_suppression(pred, self.conf_thres, self.iou_thres)[0]
        return det

# =========================
# 카메라 관련 함수
# =========================
def configure_camera(width, height, fps):
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.depth, width, height, rs.format.z16, fps)
    config.enable_stream(rs.stream.color, width, height, rs.format.bgr8, fps)
    pipeline.start(config)
    return pipeline


def get_camera_intrinsics(pipeline, align):
    frames = pipeline.wait_for_frames()
    aligned_frames = align.process(frames)
    color_frame = aligned_frames.get_color_frame()
    color_profile = color_frame.profile.as_video_stream_profile()
    intrinsics = color_profile.get_intrinsics()
    print("--- Color camera intrinsics (USED FOR 3D) ---")
    print(f"fx: {intrinsics.fx}, fy: {intrinsics.fy}")
    print(f"cx: {intrinsics.ppx}, cy: {intrinsics.ppy}")
    print(f"width: {intrinsics.width}, height: {intrinsics.height}")
    return intrinsics


def get_3d_coordinates(x, y, depth_value, intrinsics):
    fx, fy = intrinsics.fx, intrinsics.fy
    cx, cy = intrinsics.ppx, intrinsics.ppy

    Z = depth_value / 1000.0  # m
    X = - (x - cx) * Z / fx
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
    if pub_3d is None:
        return
    point = Point()
    point.y = X
    point.z = Y
    point.x = Z
    pub_3d.publish(point)


# =========================
# 콜백 함수
# =========================
def m2d_callback(msg):
    rospy.sleep(2.0)
    global detect_start
    detect_start = 1


def t2d_callback(msg):
    rospy.sleep(2.0)
    global detect_stop
    detect_stop = 0


# =========================
# 메인 캡처 + 추론 루프
# =========================
def capture_video_and_detect(width=640, height=480, fps=30, opt=None):
    global detect_start, detect_stop

    pipeline = configure_camera(width, height, fps)
    align = rs.align(rs.stream.color)
    intrinsics = get_camera_intrinsics(pipeline, align)

    # TensorRT YOLOv5 모델 로드
    trt_model = TrtYOLOv5(
        engine_file_path=opt.weights,
        input_shape=(opt.img_size, opt.img_size),
        conf_thres=opt.conf_thres,
        iou_thres=opt.iou_thres,
    )

    TIMEOUT_SECONDS = 5.0
    last_detection_time = time.time()

    try:
        while not rospy.is_shutdown():
            current_time = time.time()

            # 타임아웃: 일정 시간 동안 감지가 없으면 d2t로 신호 보내기
            if current_time - last_detection_time > TIMEOUT_SECONDS:
                if d2t is not None:
                    d2t.publish("start")
                detect_stop = 1

            # 프레임 획득
            frames = pipeline.wait_for_frames()
            aligned_frames = align.process(frames)
            color_frame = aligned_frames.get_color_frame()
            depth_frame = aligned_frames.get_depth_frame()
            if not color_frame or not depth_frame:
                continue

            color_image = np.asanyarray(color_frame.get_data())
            depth_image = np.asanyarray(depth_frame.get_data())

            # BGR → RGB (네트워크 입력용)
            img0 = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)

            # TensorRT 추론
            pred = trt_model.infer(img0)

            if pred is not None and len(pred):
                last_detection_time = current_time

                # bbox를 원본 이미지 크기로 스케일 복구
                pred[:, :4] = scale_coords(
                    (opt.img_size, opt.img_size),
                    pred[:, :4],
                    img0.shape
                ).round()

                for *xyxy, conf, cls in reversed(pred):
                    x1, y1, x2, y2 = [int(x) for x in xyxy]
                    x_center = (x1 + x2) / 2.0
                    y_center = (y1 + y2) / 2.0

                    # 클래스 이름 매핑
                    class_id = int(cls.item()) if torch.is_tensor(cls) else int(cls)
                    if 0 <= class_id < len(CLASS_NAMES):
                        class_name = CLASS_NAMES[class_id]
                    else:
                        class_name = f"id{class_id}"

                    # 바운딩 박스 + 라벨
                    cv2.rectangle(color_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    label = f"{class_name} {float(conf):.2f}"
                    cv2.putText(color_image, label, (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                    # Depth → 3D
                    depth_value = get_depth_at_center(x_center, y_center, depth_image)
                    if depth_value is not None and depth_value > 0:
                        X, Y, Z = get_3d_coordinates(x_center, y_center, depth_value, intrinsics)
                        
                        # 3D 좌표 publish (기존)
                        publish_3d_point(X, Y, Z)
                        
                        # 클래스 이름 publish (추가)
                        cls_pub.publish(class_name)
 

            # 디버그용 영상 표시
            cv2.imshow("color", color_image)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        pipeline.stop()
        cv2.destroyAllWindows()


# =========================
# 메인
# =========================
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--weights',
        type=str,
        default=os.path.expanduser(
            '~/transbot_ws/src/yolov5_ros/yolov5/strawberry.trt'
        ),
        help='TensorRT 엔진 파일 경로 (.trt / .engine)'
    )
    parser.add_argument('--source', type=str, default='0')
    parser.add_argument('--img-size', type=int, default=640)
    parser.add_argument('--conf-thres', type=float, default=0.50)
    parser.add_argument('--iou-thres', type=float, default=0.45)
    parser.add_argument('--device', default='0')

    argv = rospy.myargv(argv=sys.argv)
    opt = parser.parse_args(argv[1:])

    rospy.init_node('yolov5_trt_node', anonymous=True)

    pub_3d = rospy.Publisher('/depth_3d_points', Point, queue_size=10)   # 3D 좌표 퍼블리셔
    d2t = rospy.Publisher('/d2t', String, queue_size=10)                 # detection → task 알림
    cls_pub = rospy.Publisher('/detected_class', String, queue_size=10)  # 클래스 이름 퍼블리셔
    rospy.Subscriber('/t2d', String, t2d_callback)                       # task → detection 알림
    rospy.Subscriber('/m2d', String, m2d_callback)                       # 메인 → detection 알림

    rospy.loginfo("[Main] YOLOv5 TensorRT + Depth 노드 시작")

    capture_video_and_detect(width=640, height=480, fps=30, opt=opt)

