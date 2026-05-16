#!/usr/bin/env python
# -*- coding: utf-8 -*-

import rospy, sys
from time import sleep
import moveit_commander
from geometry_msgs.msg import PoseStamped
from moveit_commander import MoveGroupCommander, PlanningSceneInterface

if __name__ == "__main__":
    # 初始化move_group的API Initialize move_group API
    moveit_commander.roscpp_initialize(sys.argv)
    # 初始化ROS节点 Initialize the ROS node
    rospy.init_node('attached_object_py')
    # 初始化场景对象 Initialize the scene object
    scene = PlanningSceneInterface()
    # 初始化机械臂 Initialize the robotic arm
    transbot = MoveGroupCommander('arm')
    # 当运动规划失败后，允许重新规划 When motion planning fails, re-planning is allowed
    transbot.allow_replanning(True)
    transbot.set_planning_time(5)
    # 尝试规划的次数 Number of planning attempts
    transbot.set_num_planning_attempts(10)
    # 设置允许目标位置误差 Set the allowable target position error
    transbot.set_goal_position_tolerance(0.01)
    # 设置允许目标姿态误差 Set the allowable target attitude error
    transbot.set_goal_orientation_tolerance(0.01)
    # 设置允许目标误差 Set the allowable target error
    transbot.set_goal_tolerance(0.01)
    # 设置最大速度 Set maximum speed
    transbot.set_max_velocity_scaling_factor(1.0)
    # 设置最大加速度 Set maximum acceleration
    transbot.set_max_acceleration_scaling_factor(1.0)
    # 设置"pose1"为目标点 Set "pose1" as the target point
    transbot.set_named_target("pose1")
    transbot.go()
    sleep(0.5)
    # 设置桌面的高度 Set the height of the desktop
    table_ground = 0.12
    # 设置障碍物的三维尺寸[长宽高] Set the 3D size of obstacles [length, width, and height]
    table_size = [0.1, 0.2, 0.01]
    floor_size = [1, 0.5, 0.01]
    # 将table加入场景当中 Add the table to the scene
    table_pose = PoseStamped()
    table_pose.header.frame_id = 'base_footprint'
    table_pose.pose.position.x = 0.36
    table_pose.pose.position.y = 0
    table_pose.pose.position.z = table_ground + table_size[2] / 2.0
    table_pose.pose.orientation.w = 1.0
    scene.add_box('table', table_pose, table_size)
    floor_pose = PoseStamped()
    floor_pose.header.frame_id = 'base_footprint'
    scene.add_box('floor', floor_pose, floor_size)
    rospy.sleep(2)
    target_joints1 = [-1.35, 1.35]
    target_joints2 = [-3.0, 3.0]
    while not rospy.is_shutdown():
        transbot.set_joint_value_target(target_joints1)
        transbot.go()
        sleep(0.5)
        transbot.set_joint_value_target(target_joints2)
        transbot.go()
        sleep(0.5)
        # 设置随机目标点 Set random target points
        transbot.set_random_target()
        # Start
        transbot.go()
        sleep(0.5)
    moveit_commander.roscpp_shutdown()
    moveit_commander.os._exit(0)

