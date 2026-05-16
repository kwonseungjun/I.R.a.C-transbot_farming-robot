#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import cv2
import numpy as np
import rospy
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import cv2
import numpy as np
import rospy
from geometry_msgs.msg import Twist
from std_msgs.msg import String

DEBUG_SHOW = True # 디버그 창 On/Off

#  GStreamer 파이프라인 
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
        rospy.init_node("line_follower_keyboard", anonymous=True)
        self.cmd_pub = rospy.Publisher("/cmd_vel", Twist, queue_size=10)
        self.command_pub = rospy.Publisher("/manipulator_command", String, queue_size=10)
        self.camera_control_active = [True]  # 카메라 제어 on/off flag
        self.last_direction = "STRAIGHT"

    def process_camera(self):
        cap = cv2.VideoCapture(gstreamer_pipeline(), cv2.CAP_GSTREAMER)
        if not cap.isOpened():
            print("카메라를 열 수 없습니다.")
            return

        last_direction = self.last_direction

        while not rospy.is_shutdown():
            ret, frame0 = cap.read()
            if not ret:
                print("프레임을 가져올 수 없습니다.")
                break

            H0, W0 = frame0.shape[:2]
            disp = frame0.copy()  # 화면에 사다리꼴 표시

            # 다운스케일 - 가까운 두꺼운 선을 얇게 보이도록
            W = int(W0 * 0.60)
            H = int(H0 * 0.60)
            proc = cv2.resize(frame0, (W, H), interpolation=cv2.INTER_AREA)

            # 버드아이뷰 - 원근/기울기 보정
            top_y = int(H * 0.55)
            bot_y = int(H * 0.98)
            top_dx = int(W * 0.18)
            bot_dx = int(W * 0.60)
            src = np.float32([
                [W/2 - top_dx, top_y],   # LT
                [W/2 + top_dx, top_y],   # RT
                [W/2 + bot_dx, bot_y],   # RB
                [W/2 - bot_dx, bot_y],   # LB
            ])
            dst = np.float32([[0,0],[W,0],[W,H],[0,H]])
            M  = cv2.getPerspectiveTransform(src, dst)
            bev = cv2.warpPerspective(proc, M, (W, H))
            src_poly = src.astype(np.int32)

            # ROI - 화면의 하단부 사용
            roi_y0 = int(H * 0.55)   # 하단 45% 사용
            y_proj = int(H * 0.75)   # 방향 판단선 -하단에서 25% 위
            bev_gray = cv2.cvtColor(bev, cv2.COLOR_BGR2GRAY)
            bev_gray = cv2.GaussianBlur(bev_gray, (5,5), 0)

            # 에지 기반 1차 시도 (Canny → HoughP)
            v = np.median(bev_gray[roi_y0:]) if roi_y0 < H else np.median(bev_gray)
            lo = int(max(0, (1.0 - 0.33) * v))
            hi = int(min(255, (1.0 + 0.33) * v))
            edges = cv2.Canny(bev_gray, lo, hi)
            edges[:roi_y0, :] = 0  # 상단 제거

            thresh = 40
            min_len = max(20, W // 8)
            max_gap = max(10, W // 20)
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, thresh,
                                    minLineLength=min_len, maxLineGap=max_gap)

            x_hits = []
            bev_vis = bev.copy()

            if lines is not None:
                for x1, y1_l, x2, y2_l in lines[:, 0]:
                    dx, dy = (x2 - x1), (y2_l - y1_l)
                    if dx == 0 and dy == 0:
                        continue
                    angle_deg = abs(np.degrees(np.arctan2(dy, dx)))
                    if angle_deg < 15:   # 거의 수평선 제외
                        continue
                    # y=y_proj에서의 교점
                    if dx != 0:
                        m = dy / float(dx)
                        if m != 0:
                            x_at = (y_proj - y1_l) / m + x1
                        else:
                            x_at = x1
                    else:
                        x_at = x1
                    if 0 <= x_at < W:
                        x_hits.append(x_at)
                        cv2.line(bev_vis, (x1, y1_l), (x2, y2_l), (0,255,255), 2)

            # 선을 얇게 인식
            if not x_hits:
                _, bin_inv = cv2.threshold(bev_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                k = cv2.getStructuringElement(cv2.MORPH_RECT, (5,5))
                bin_inv = cv2.morphologyEx(bin_inv, cv2.MORPH_OPEN, k, iterations=1)
                bin_inv = cv2.erode(bin_inv, k, iterations=1)
                bin_inv[:roi_y0, :] = 0
                row = bin_inv[y_proj, :]
                xs = np.where(row > 0)[0]
                if xs.size > 0:
                    x_hits.append(float(xs.mean()))
                # 시각화용 오버레이
                bev_vis = cv2.addWeighted(bev_vis, 1.0, cv2.cvtColor(bin_inv, cv2.COLOR_GRAY2BGR), 0.3, 0)

            # 방향 감지
            if x_hits:
                x_mean = float(np.mean(x_hits))
                cx = W / 2.0
                pos_err = (x_mean - cx) / (W / 2.0)
                if pos_err > 0.08:
                    direction = "RIGHT"
                elif pos_err < -0.08:
                    direction = "LEFT"
                else:
                    direction = "STRAIGHT"
            else:
                direction = last_direction

            last_direction = direction
            self.last_direction = direction

            # 시각화 - 다운스케일 보정 및 원본에 사다리꼴 표시
            src_on_orig = (src_poly / 0.60).astype(np.int32)
            cv2.polylines(disp, [src_on_orig], True, (0,0,255), 2)
            cv2.putText(disp, direction, (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,0,0), 2)

            # BEV 가이드라인
            cv2.line(bev_vis, (0, y_proj), (W-1, y_proj), (255, 0, 255), 1)
            third_w = W // 3
            cv2.line(bev_vis, (third_w, roi_y0), (third_w, H-1), (0,255,0), 1)
            cv2.line(bev_vis, (2*third_w, roi_y0), (2*third_w, H-1), (0,255,0), 1)
            for xh in x_hits:
                cv2.circle(bev_vis, (int(xh), y_proj), 4, (0,0,255), -1)

            if DEBUG_SHOW:
                cv2.imshow("Frame (orig) + SRC trapezoid", disp)
                cv2.imshow("BEV (proc)", bev_vis)

            # 제어 - 카메라 모드일 때만
            if self.camera_control_active[0]:
                twist = Twist()
                if direction == "LEFT":
                    twist.linear.x = 0.0
                    twist.angular.z = 1.0
                elif direction == "RIGHT":
                    twist.linear.x = 0.0
                    twist.angular.z = -1.0
                else:
                    twist.linear.x = -0.2
                    twist.angular.z = 0.0
                self.cmd_pub.publish(twist)

            # 키 입력
            key = cv2.waitKey(1) & 0xFF
            if key == ord('k'):
                self.command_pub.publish("init")
                print("Sending 'init' command to manipulator...")
            elif key == ord('j'):
                self.command_pub.publish("home")
                print("Sending 'home' command to manipulator...")
            elif key == ord('m'):
                self.camera_control_active[0] = not self.camera_control_active[0]
                print("Camera control:", self.camera_control_active[0])
            elif key == ord('q'):
                break

        # 종료 처리
        self.cmd_pub.publish(Twist())  # stop
        cap.release()
        cv2.destroyAllWindows()
        rospy.signal_shutdown("Camera closed")

#  실행부
if __name__ == "__main__":
    node = LineFollower()
    node.process_camera()

