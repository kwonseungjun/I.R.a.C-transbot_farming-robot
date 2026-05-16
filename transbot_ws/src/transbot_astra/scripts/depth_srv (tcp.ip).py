#!/usr/bin/env python
import rospy
from sensor_msgs.msg import Image
import ros_numpy
import numpy as np
import socket
import threading
import json
import signal
import sys

# ASTRA 카메라 intrinsic 예시 (실제 값으로 교체 필요)
fx = 0  # focal length x
fy = 0  # focal length y
cx = 0  # optical center x
cy = 0  # optical center y
depth_scale = 0.001  # mm → m

HOST = '127.0.0.1'
PORT = 5005

class Depth3DCalculator:
    def __init__(self):
        rospy.init_node("depth_3d_calculator", anonymous=True)
        self.sub_depth = rospy.Subscriber("/camera/depth/image_raw", Image, self.depth_callback)

        # TCP 수신용
        self.bboxes = []  # [{'class':0,'x_center':..., 'y_center':...}, ...]
        self.bbox_lock = threading.Lock()
        self.tcp_thread_stop = False
        self.client_sock = None

        self.tcp_thread = threading.Thread(target=self.tcp_server)
        self.tcp_thread.daemon = True
        self.tcp_thread.start()

        # Ctrl+C 종료 처리
        signal.signal(signal.SIGINT, self.cleanup)
        signal.signal(signal.SIGTERM, self.cleanup)

    def tcp_server(self):
        """YOLO에서 보내는 바운딩 박스 좌표 수신"""
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((HOST, PORT))
        self.server_sock.listen(1)
        print(f"TCP server listening on {HOST}:{PORT}")

        while not rospy.is_shutdown() and not self.tcp_thread_stop:
            try:
                self.client_sock, addr = self.server_sock.accept()
                print(f"Client connected: {addr}")
                buffer = ''
                self.client_sock.settimeout(None)
                while not rospy.is_shutdown() and not self.tcp_thread_stop:
                    data = self.client_sock.recv(1024)
                    if not data:
                        break
                    buffer += data.decode('utf-8')
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        try:
                            bbox = json.loads(line)
                            with self.bbox_lock:
                                self.bboxes.append(bbox)
                                if len(self.bboxes) > 10:
                                    self.bboxes.pop(0)
                        except json.JSONDecodeError:
                            print("JSON decode error")
            except Exception as e:
                if not self.tcp_thread_stop:
                    print(f"TCP server exception: {e}")
            finally:
                if self.client_sock:
                    try:
                        self.client_sock.close()
                        print("Client disconnected")
                    except:
                        pass
                    self.client_sock = None

    def depth_callback(self, msg):
        """Depth 이미지 수신 시, 바운딩 박스 좌표와 결합해 3D 좌표 계산"""
        depth_image = ros_numpy.numpify(msg)
        with self.bbox_lock:
            for bbox in self.bboxes:
                x_pixel = int(bbox['x_center'])
                y_pixel = int(bbox['y_center'])
                if x_pixel < 0 or x_pixel >= depth_image.shape[1] or y_pixel < 0 or y_pixel >= depth_image.shape[0]:
                    continue
                samples = [
                    depth_image[max(y_pixel-3,0), max(x_pixel-3,0)],
                    depth_image[min(y_pixel+3,depth_image.shape[0]-1), max(x_pixel-3,0)],
                    depth_image[max(y_pixel-3,0), min(x_pixel+3,depth_image.shape[1]-1)],
                    depth_image[min(y_pixel+3,depth_image.shape[0]-1), min(x_pixel+3,depth_image.shape[1]-1)],
                    depth_image[y_pixel, x_pixel]
                ]
                valid_samples = [d for d in samples if 40 < d < 80000]
                if not valid_samples:
                    continue
                z = sum(valid_samples) / len(valid_samples) * depth_scale
                X = (x_pixel - cx) * z / fx
                Y = (y_pixel - cy) * z / fy
                print(f"3D Point: class={bbox['class']} X={X:.3f}, Y={Y:.3f}, Z={z:.3f} m")

    def cleanup(self, signal_received=None, frame=None):
        """ROS 종료 및 Ctrl+C 시 호출"""
        print("Shutting down Depth3DCalculator...")
        self.tcp_thread_stop = True
        try:
            if self.client_sock:
                self.client_sock.close()
            if self.server_sock:
                self.server_sock.close()
            print("TCP server and client sockets closed.")
        except Exception as e:
            print(f"Error closing sockets: {e}")
        if self.tcp_thread.is_alive():
            self.tcp_thread.join()
        print("TCP server thread stopped.")
        rospy.signal_shutdown("Shutdown signal received")
        sys.exit(0)

if __name__ == "__main__":
    calculator = Depth3DCalculator()
    rospy.spin()

