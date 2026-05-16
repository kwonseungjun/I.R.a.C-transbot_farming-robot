#!/usr/bin/env python
# -*- coding: utf-8 -*-

import rospy
from moveit_commander import RobotCommander, PlanningSceneInterface, MoveGroupCommander
from geometry_msgs.msg import Pose

# 초기화 및 ROS 노드 설정
rospy.init_node('pick_place_node', anonymous=True)
robot = RobotCommander()
scene = PlanningSceneInterface()
group_name = "arm"  # 사용자의 로봇 그룹 이름으로 변경 필요
move_group = MoveGroupCommander(group_name)
move_group.set_planner_id("RRT")

# 집기(pick) 함수 정의
def pick():
    # 집기 위치 설정
    pick_pose = Pose()
    pick_pose.position.x = 0.4
    pick_pose.position.y = 0.0
    pick_pose.position.z = 0.4
    pick_pose.orientation.w = 1.0

    # 목표 위치로 이동
    move_group.set_pose_target(pick_pose)
    plan = move_group.go(wait=True)
    move_group.stop()
    move_group.clear_pose_targets()

    rospy.loginfo("Pick action completed.")

# 놓기(place) 함수 정의
def place():
    # 놓기 위치 설정
    place_pose = Pose()
    place_pose.position.x = 0.4
    place_pose.position.y = 0.4
    place_pose.position.z = 0.4
    place_pose.orientation.w = 1.0

    # 목표 위치로 이동
    move_group.set_pose_target(place_pose)
    plan = move_group.go(wait=True)
    move_group.stop()
    move_group.clear_pose_targets()

    rospy.loginfo("Place action completed.")

if __name__ == '__main__':
    try:
        while not rospy.is_shutdown():
            user_input = raw_input("Enter 1 to pick, 2 to place: ").strip()
            if user_input == '1':
                pick()
            elif user_input == '2':
                place()
            else:
                rospy.loginfo("Invalid input, please enter 1 or 2.")
    except rospy.ROSInterruptException:
        pass

