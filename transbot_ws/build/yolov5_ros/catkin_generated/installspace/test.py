#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TensorRT YOLOv5 Object Detection with ROS and Depth Integration
For Jetson Nano + Astra Pro Camera
"""

import argparse
import time
from pathlib import Path
import numpy as np
import cv2
import tensorrt as trt
import pycuda.driver as cuda
import pycuda.autoinit

# ROS imports
import rospy
from sensor_msgs.msg import Image, CameraInfo
from vision_msgs.msg import Detection2DArray, Detection2D, BoundingBox2D, ObjectHypothesisWithPose
from geometry_msgs.msg import Pose2D, Point
from std_msgs.msg import Header
from cv_bridge import CvBridge, CvBridgeError

# Astra Pro camera for depth
try:
    from openni import openni2
    from openni import _openni2 as c_api
    ASTRA_AVAILABLE = True
except ImportError:
    ASTRA_AVAILABLE = False
    print("Warning: OpenNI2 not available. Depth functionality will be disabled.")


class TRTYOLOv5:
    """TensorRT YOLOv5 inference engine"""
    
    def __init__(self, engine_path, class_names, conf_thres=0.25, iou_thres=0.45):
        self.conf_thres = conf_thres
        self.iou_thres = iou_thres
        self.class_names = class_names
        
        # TensorRT 로거 및 런타임 초기화
        self.logger = trt.Logger(trt.Logger.WARNING)
        self.runtime = trt.Runtime(self.logger)
        
        # 엔진 파일 로드
        with open(engine_path, 'rb') as f:
            self.engine = self.runtime.deserialize_cuda_engine(f.read())
        
        self.context = self.engine.create_execution_context()
        
        # 입력/출력 바인딩 정보 추출
        self.input_shape = None
        self.output_shape = None
        self.bindings = []
        self.host_inputs = []
        self.host_outputs = []
        self.cuda_inputs = []
        self.cuda_outputs = []
        
        for binding in self.engine:
            binding_idx = self.engine.get_binding_index(binding)
            size = trt.volume(self.engine.get_binding_shape(binding_idx))
            dtype = trt.nptype(self.engine.get_binding_dtype(binding_idx))
            
            # 호스트 메모리 할당
            host_mem = cuda.pagelocked_empty(size, dtype)
            # GPU 메모리 할당
            cuda_mem = cuda.mem_alloc(host_mem.nbytes)
            
            self.bindings.append(int(cuda_mem))
            
            if self.engine.binding_is_input(binding_idx):
                self.input_shape = self.engine.get_binding_shape(binding_idx)
                self.host_inputs.append(host_mem)
                self.cuda_inputs.append(cuda_mem)
            else:
                self.output_shape = self.engine.get_binding_shape(binding_idx)
                self.host_outputs.append(host_mem)
                self.cuda_outputs.append(cuda_mem)
        
        # CUDA 스트림 생성
        self.stream = cuda.Stream()
        
        print(f"Engine loaded: {engine_path}")
        print(f"Input shape: {self.input_shape}")
        print(f"Output shape: {self.output_shape}")
    
    def preprocess(self, img):
        """이미지 전처리"""
        img_h, img_w = img.shape[:2]
        input_h, input_w = self.input_shape[2], self.input_shape[3]
        
        # Letterbox resize
        r = min(input_h / img_h, input_w / img_w)
        new_w, new_h = int(img_w * r), int(img_h * r)
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        # Padding
        dw, dh = (input_w - new_w) // 2, (input_h - new_h) // 2
        padded = cv2.copyMakeBorder(resized, dh, input_h - new_h - dh, dw, 
                                    input_w - new_w - dw, cv2.BORDER_CONSTANT, 
                                    value=(114, 114, 114))
        
        # Normalize and transpose
        blob = padded.astype(np.float32) / 255.0
        blob = blob.transpose(2, 0, 1)  # HWC -> CHW
        blob = np.expand_dims(blob, axis=0)  # Add batch dimension
        blob = np.ascontiguousarray(blob)
        
        return blob, r, dw, dh
    
    def infer(self, img):
        """TensorRT 추론"""
        blob, r, dw, dh = self.preprocess(img)
        
        # 입력 데이터를 GPU로 복사
        np.copyto(self.host_inputs[0], blob.ravel())
        cuda.memcpy_htod_async(self.cuda_inputs[0], self.host_inputs[0], self.stream)
        
        # 추론 실행
        self.context.execute_async_v2(bindings=self.bindings, stream_handle=self.stream.handle)
        
        # 결과를 CPU로 복사
        cuda.memcpy_dtoh_async(self.host_outputs[0], self.cuda_outputs[0], self.stream)
        self.stream.synchronize()
        
        # 출력 재구성
        output = self.host_outputs[0].reshape(self.output_shape)
        
        # 후처리
        detections = self.postprocess(output, img.shape[:2], r, dw, dh)
        
        return detections
    
    def postprocess(self, output, img_shape, ratio, dw, dh):
        """후처리 (NMS 적용)"""
        output = output[0]  # Remove batch dimension
        
        # Confidence threshold 적용
        conf_mask = output[:, 4] >= self.conf_thres
        output = output[conf_mask]
        
        if len(output) == 0:
            return []
        
        # xywh -> xyxy 변환
        boxes = output[:, :4]
        boxes_xyxy = np.zeros_like(boxes)
        boxes_xyxy[:, 0] = boxes[:, 0] - boxes[:, 2] / 2  # x1
        boxes_xyxy[:, 1] = boxes[:, 1] - boxes[:, 3] / 2  # y1
        boxes_xyxy[:, 2] = boxes[:, 0] + boxes[:, 2] / 2  # x2
        boxes_xyxy[:, 3] = boxes[:, 1] + boxes[:, 3] / 2  # y2
        
        # 원본 이미지 좌표로 변환
        boxes_xyxy[:, [0, 2]] = (boxes_xyxy[:, [0, 2]] - dw) / ratio
        boxes_xyxy[:, [1, 3]] = (boxes_xyxy[:, [1, 3]] - dh) / ratio
        
        # 클래스 확률
        class_confs = output[:, 5:]
        class_ids = np.argmax(class_confs, axis=1)
        confidences = output[:, 4] * np.max(class_confs, axis=1)
        
        # NMS
        indices = cv2.dnn.NMSBoxes(boxes_xyxy.tolist(), confidences.tolist(), 
                                    self.conf_thres, self.iou_thres)
        
        detections = []
        if len(indices) > 0:
            indices = indices.flatten()
            for idx in indices:
                x1, y1, x2, y2 = boxes_xyxy[idx]
                x1, y1 = max(0, int(x1)), max(0, int(y1))
                x2, y2 = min(img_shape[1], int(x2)), min(img_shape[0], int(y2))
                
                detections.append({
                    'bbox': [x1, y1, x2, y2],
                    'class_id': int(class_ids[idx]),
                    'class_name': self.class_names[int(class_ids[idx])],
                    'confidence': float(confidences[idx])
                })
        
        return detections


class DepthEstimator:
    """Astra Pro 카메라를 이용한 Depth 측정"""
    
    def __init__(self):
        if not ASTRA_AVAILABLE:
            rospy.logwarn("OpenNI2 not available. Depth estimation disabled.")
            self.enabled = False
            return
        
        self.enabled = True
        openni2.initialize()
        
        try:
            self.device = openni2.Device.open_any()
            self.depth_stream = self.device.create_depth_stream()
            self.depth_stream.start()
            rospy.loginfo("Astra Pro depth stream initialized")
        except Exception as e:
            rospy.logerr(f"Failed to initialize depth stream: {e}")
            self.enabled = False
    
    def get_depth(self, x, y):
        """특정 픽셀의 depth 값 반환 (mm 단위)"""
        if not self.enabled:
            return None
        
        try:
            frame = self.depth_stream.read_frame()
            frame_data = frame.get_buffer_as_uint16()
            depth_array = np.ndarray((frame.height, frame.width), dtype=np.uint16, 
                                     buffer=frame_data)
            
            if 0 <= y < depth_array.shape[0] and 0 <= x < depth_array.shape[1]:
                return depth_array[y, x]
        except Exception as e:
            rospy.logerr(f"Depth reading error: {e}")
        
        return None
    
    def cleanup(self):
        if self.enabled:
            self.depth_stream.stop()
            openni2.unload()


class YOLOv5ROSNode:
    """ROS 노드 클래스"""
    
    def __init__(self):
        rospy.init_node('yolov5_ros', anonymous=True)
        
        # 파라미터 로드
        engine_path = rospy.get_param('~engine_path', 'yolov5s.engine')
        class_names_path = rospy.get_param('~class_names', 'coco.names')
        conf_thres = rospy.get_param('~conf_threshold', 0.25)
        iou_thres = rospy.get_param('~iou_threshold', 0.45)
        self.camera_topic = rospy.get_param('~camera_topic', '/camera/color/image_raw')
        self.use_depth = rospy.get_param('~use_depth', True)
        
        # 클래스 이름 로드
        with open(class_names_path, 'r') as f:
            class_names = [line.strip() for line in f.readlines()]
        
        # TensorRT 모델 초기화
        self.detector = TRTYOLOv5(engine_path, class_names, conf_thres, iou_thres)
        
        # Depth estimator 초기화
        if self.use_depth:
            self.depth_estimator = DepthEstimator()
        else:
            self.depth_estimator = None
        
        # CV Bridge
        self.bridge = CvBridge()
        
        # Publishers
        self.detection_pub = rospy.Publisher('~detections', Detection2DArray, queue_size=10)
        self.image_pub = rospy.Publisher('~detection_image', Image, queue_size=10)
        
        # Subscriber
        self.image_sub = rospy.Subscriber(self.camera_topic, Image, self.image_callback, 
                                          queue_size=1, buff_size=2**24)
        
        # 통계
        self.frame_count = 0
        self.total_time = 0
        
        rospy.loginfo("YOLOv5 TensorRT ROS Node initialized")
    
    def image_callback(self, msg):
        """이미지 콜백"""
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        except CvBridgeError as e:
            rospy.logerr(f"CV Bridge error: {e}")
            return
        
        # 추론
        start_time = time.time()
        detections = self.detector.infer(cv_image)
        inference_time = time.time() - start_time
        
        # 통계 업데이트
        self.frame_count += 1
        self.total_time += inference_time
        avg_fps = self.frame_count / self.total_time
        
        # Detection 메시지 생성
        detection_msg = Detection2DArray()
        detection_msg.header = msg.header
        
        # 시각화 이미지
        vis_image = cv_image.copy()
        
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            class_name = det['class_name']
            confidence = det['confidence']
            
            # Depth 측정
            depth_str = ""
            if self.depth_estimator and self.depth_estimator.enabled:
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                depth = self.depth_estimator.get_depth(cx, cy)
                if depth is not None and depth > 0:
                    depth_m = depth / 1000.0  # mm to m
                    depth_str = f" {depth_m:.2f}m"
            
            # ROS Detection 메시지
            detection = Detection2D()
            detection.header = msg.header
            
            # BoundingBox2D
            detection.bbox.center.x = (x1 + x2) / 2.0
            detection.bbox.center.y = (y1 + y2) / 2.0
            detection.bbox.size_x = x2 - x1
            detection.bbox.size_y = y2 - y1
            
            # Hypothesis
            hypothesis = ObjectHypothesisWithPose()
            hypothesis.id = det['class_id']
            hypothesis.score = confidence
            detection.results.append(hypothesis)
            
            detection_msg.detections.append(detection)
            
            # 시각화
            color = (0, 255, 0)
            cv2.rectangle(vis_image, (x1, y1), (x2, y2), color, 2)
            label = f"{class_name} {confidence:.2f}{depth_str}"
            cv2.putText(vis_image, label, (x1, y1 - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # FPS 표시
        cv2.putText(vis_image, f"FPS: {avg_fps:.1f}", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        # Publish
        self.detection_pub.publish(detection_msg)
        
        try:
            image_msg = self.bridge.cv2_to_imgmsg(vis_image, "bgr8")
            self.image_pub.publish(image_msg)
        except CvBridgeError as e:
            rospy.logerr(f"CV Bridge error: {e}")
    
    def cleanup(self):
        if self.depth_estimator:
            self.depth_estimator.cleanup()


def main():
    try:
        node = YOLOv5ROSNode()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
    finally:
        if 'node' in locals():
            node.cleanup()


if __name__ == '__main__':
    main()
