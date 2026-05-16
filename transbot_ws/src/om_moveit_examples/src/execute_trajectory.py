#! /usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import copy
import rospy
import moveit_commander
import moveit_msgs.msg
import geometry_msgs.msg
from std_msgs.msg import Bool


names1 = 'position1'  # a부품
values1 = [-0.4, 0.4, -0.3, 1.3]
names2 = 'position2'  # b부품
values2 = [0.4, 0.4, -0.3, 1.3]
names3 = 'position3'  # 터틀봇 위치
values3 = [-1.4, 0.4, -0.4, 1.4]

turtlebot_arrived = False

def turtlebot_arrival_callback(msg):
    global turtlebot_arrived
    turtlebot_arrived = msg.data
    if turtlebot_arrived:
        print("TurtleBot has arrived!")

def open_gripper():
    gripper_group_variable_values[0] = -0.006
    gripper_group.set_joint_value_target(gripper_group_variable_values)
    gripper_group.go()
    gripper_group.stop()
    gripper_group.clear_pose_targets()
    rospy.sleep(1)

def close_gripper():
    gripper_group_variable_values[0] = 0.006
    gripper_group.set_joint_value_target(gripper_group_variable_values)
    gripper_group.go()
    gripper_group.stop()
    gripper_group.clear_pose_targets()
    rospy.sleep(1)

def move_home():
    arm_group.set_named_target("home")
    arm_group.go()
    arm_group.stop()
    arm_group.clear_pose_targets()
    rospy.sleep(1)

def move_position1():
    arm_group.set_named_target(names1)
    arm_group.go()
    arm_group.stop()
    arm_group.clear_pose_targets()
    rospy.sleep(1)
def move_position3():
    arm_group.set_named_target(names3)
    arm_group.go()
    arm_group.stop()
    arm_group.clear_pose_targets()
    rospy.sleep(1)

def main():
    global turtlebot_arrived
    moveit_commander.roscpp_initialize(sys.argv)
    rospy.init_node('move_group_python_execute_trajectory', anonymous=True)

    global arm_group, gripper_group, gripper_group_variable_values
    robot = moveit_commander.RobotCommander()
    scene = moveit_commander.PlanningSceneInterface()
    arm_group = moveit_commander.MoveGroupCommander("arm")
    gripper_group = moveit_commander.MoveGroupCommander("gripper")
    display_trajectory_publisher = rospy.Publisher('/move_group/display_planned_path', moveit_msgs.msg.DisplayTrajectory, queue_size=1)
    arm_group.set_planner_id("RRTConnectkConfigDefault")
    arm_group.set_planning_time(10)

    
    arm_group.remember_joint_values(names1, values1)
    arm_group.remember_joint_values(names2, values2)
    arm_group.remember_joint_values(names3, values3)
    
    gripper_group_variable_values = gripper_group.get_current_joint_values()
     
    rospy.Subscriber('/turtlebot_arrival', Bool, turtlebot_arrival_callback)

    move_home()
    open_gripper()

    while not rospy.is_shutdown():
        if turtlebot_arrived:
            move_position1()
            close_gripper()
            move_home()
            move_position3()
            open_gripper()
            rospy.sleep(3)
            move_home()
            turtlebot_arrived = False
    moveit_commander.roscpp_shutdown()

if __name__ == '__main__':
    main()

