#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import cv2
import numpy as np
import rospy
from geometry_msgs.msg import Twist
from std_msgs.msg import String

from pyzbar import pyzbar
from pyzbar.pyzbar import ZBarSymbol
import time

DEBUG_SHOW = False  # 디버그 창 On/Off

def d2t_callback(msg):
    global running
    running = 1

# GStreamer 파이프라인
def gstreamer_pipeline(capture_width=640, capture_height=480, 
                       display_width=640, display_height=480, 
                       framerate=30, flip_method=0):
    return (
        "nvarguscamerasrc ! "
        "video/x-raw(memory:NVMM), "
        "width=(int)%d, height=(int)%d, "
        "format=(string)NV12, framerate=(fraction)%d/1 ! "
        "nvvidconv flip-method=%d ! "
        "video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! "
        "videoconvert ! "
        "video/x-raw, format=(string)BGR ! appsink"
        % (capture_width, capture_height, framerate, 
           flip_method, display_width, display_height)
    )

class LineFollower:
    def __init__(self):
        rospy.init_node("line_follower_node", anonymous=True)
        self.cmd_pub = rospy.Publisher("/cmd_vel", Twist, queue_size=10)
        self.command_pub = rospy.Publisher("/t2m", String, queue_size=10)
        self.detect_pub = rospy.Publisher("/t2d", String, queue_size=10)
        rospy.Subscriber('/d2t', String, d2t_callback)

        self.camera_control_active = [True]
        
        self.STATE_LINE = "LINE_TRACING"
        self.STATE_STOP = "STOPPED_BY_ORANGE"
        self.state = self.STATE_LINE
        self.cf = 0
        self.QR_SKIP_FRAMES = 3
        
        self.linear_speed = 0.1
        self.max_angular_speed = 0.7
        self.min_angular_speed = -0.7
        self.Kp = 0.003
        self.last_angular_z = 0.0
        
        self.insert = 0
        self.W = 0
        self.H = 0
        self.M = None
        self.W_ratio = 0.60
        self.H_ratio = 0.60
        
        self.bev_top_y_ratio = 0.45
        self.bev_bot_y_ratio = 0.95
        self.bev_top_dx_ratio = 0.25
        self.bev_bot_dx_ratio = 0.35
        self.roi_y_ratio = 0.55
        
        self.kernel = np.ones((9, 9), np.uint8)
        self.MIN_AREA = 1000
        self.orange_stop = False
        
        self.ignore_orange_until = 0  # 5초 동안 주황색을 무시하는 타이머 변수

    def init_dimensions(self, frame0):
        """BEV 변환 행렬 및 이미지 크기 초기화."""
        H0, W0 = frame0.shape[:2]
        self.W = int(W0 * self.W_ratio)
        self.H = int(H0 * self.H_ratio)
        
        top_y = int(self.H * self.bev_top_y_ratio)
        bot_y = int(self.H * self.bev_bot_y_ratio)
        top_dx = int(self.W * self.bev_top_dx_ratio)
        bot_dx = int(self.W * self.bev_bot_dx_ratio)
        
        src = np.float32([
            [self.W/2 - top_dx, top_y], [self.W/2 + top_dx, top_y],
            [self.W/2 + bot_dx, bot_y], [self.W/2 - bot_dx, bot_y],
        ])
        dst = np.float32([[0,0],[self.W,0],[self.W,self.H],[0,self.H]])
        
        self.M = cv2.getPerspectiveTransform(src, dst)

    def scan_for_orange(self, frame):
        """주황색을 감지하는 함수"""
        # 만약 5초간 주황색을 무시해야 한다면 False를 반환
        if time.time() < self.ignore_orange_until:
            return False
        
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # 확장된 HSV 범위 (주황부터 노란까지)
        lower_orange = np.array([8, 80, 30])
        upper_orange = np.array([28, 255, 230]) # 노란색 상한 (연주황, 노란색 포함)

        # 주황색 범위 내의 부분을 마스크
        mask = cv2.inRange(hsv, lower_orange, upper_orange)
        
        # 마스크에서의 영역을 확인 (윤곽선)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            if cv2.contourArea(contour) > self.MIN_AREA:
                return True  # 주황색을 찾았을 경우
        return False  # 주황색을 찾지 못한 경우

    def preprocess_image(self, frame0):
        proc = cv2.resize(frame0, (self.W, self.H), interpolation=cv2.INTER_AREA)
        bev = cv2.warpPerspective(proc, self.M, (self.W, self.H))
        bev_vis = bev.copy()
        
        bev_gray = cv2.cvtColor(bev, cv2.COLOR_BGR2GRAY)
        
        _, binary_img = cv2.threshold(bev_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        roi_y0 = int(self.H * self.roi_y_ratio)
        binary_img[:roi_y0, :] = 0
        
        return binary_img, bev_vis, proc

    def find_lane_center_centroid(self, bev_gray):
        moments = cv2.moments(bev_gray)
        
        if moments['m00'] > self.MIN_AREA:
            cx = int(moments['m10'] / moments['m00'])
            return cx
        else:
            return None

    def calculate_motor_control(self, cx, frame0):
        twist = Twist()
        
        display_text = ""
        
        if cx is not None:
            error = cx - (self.W / 2.0)
            angular_z = -self.Kp * error
            angular_z = np.clip(angular_z, self.min_angular_speed, self.max_angular_speed)
            
            turn_ratio = abs(angular_z) / self.max_angular_speed
            speed_ratio = max(0.3, 1.0 - turn_ratio)
            
            linear_x = self.linear_speed * speed_ratio
            
            twist.linear.x = linear_x
            twist.angular.z = angular_z
            
            self.last_angular_z = angular_z
            display_text = f"Pos Err:{error:.1f}, Turn:{angular_z:.2f}"
        else:
            twist.linear.x = 0.0
            twist.angular.z = 0.0
            self.last_angular_z = 0.0
            display_text = "LINE NOT FOUND (STOP)"
        
        return twist, display_text

    def publish_and_visualize(self, twist, disp, bev_vis, bev_gray, display_text, cx):
        if self.camera_control_active[0]:
            self.cmd_pub.publish(twist)
        
        control_status = "[ON]" if self.camera_control_active[0] else "[OFF]"
        state_status = f"State: {self.state}"
        
        cv2.putText(disp, f"Control: {control_status}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        cv2.putText(disp, state_status, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0) if self.state == self.STATE_LINE else (0, 0, 255), 2)
        cv2.putText(disp, display_text, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        
        if cx is not None and bev_vis is not None:
            cv2.circle(bev_vis, (cx, int(self.H/2)), 5, (0, 0, 255), -1)
        
        if DEBUG_SHOW:
            cv2.imshow("Frame (orig)", disp)
            cv2.imshow("BEV (Centroid)", bev_vis)
            cv2.imshow("Binary (Cleaned)", bev_gray)

    def process_camera(self):
        global running
        cap = cv2.VideoCapture(gstreamer_pipeline(), cv2.CAP_GSTREAMER)
        if not cap.isOpened():
            print("카메라를 열 수 없습니다.")
            return
        
        while not rospy.is_shutdown():
        
            ret, frame0 = cap.read()
            if not ret:
                break
            
            if self.M is None:
                self.init_dimensions(frame0)
            
            disp = frame0.copy()
            self.frame_counter = 1
            qr_text_result = None
            
            twist = Twist()
            display_text = ""
            bev_vis, bev_gray = None, None
            cx = None
            
            if self.insert == 0:
                self.insert +=1
                self.command_pub.publish('init')
                rospy.sleep(2.0)
                
            # 주황색을 감지하여 멈추는 로직
            if self.scan_for_orange(frame0):
                twist.linear.x = 0.0
                twist.angular.z = 0.0
                self.cmd_pub.publish(twist)
                self.state = self.STATE_STOP
                self.command_pub.publish('home')
                self.detect_pub.publish('start')

                running = 0
                display_text = "ORANGE DETECTED, STOPPED"
                while(running == 0):
                    rospy.sleep(0.1)

                self.command_pub.publish('init')
                rospy.sleep(2.0)
                self.state = self.STATE_LINE
                self.ignore_orange_until = time.time() + 2  # 2초 동안 주황색을 무시


            elif self.state == self.STATE_LINE:
                # 라인 트레이싱 모드
                bev_gray, bev_vis, proc = self.preprocess_image(frame0)
                cx = self.find_lane_center_centroid(bev_gray)
                twist, display_text = self.calculate_motor_control(cx, frame0)
                
                self.publish_and_visualize(twist, disp, bev_vis, bev_gray, display_text, cx)
            

        
        self.cmd_pub.publish(Twist())
        cap.release()
        cv2.destroyAllWindows()
        rospy.signal_shutdown("Camera Closed")

if __name__ == "__main__":
    node = LineFollower()
    node.process_camera()

