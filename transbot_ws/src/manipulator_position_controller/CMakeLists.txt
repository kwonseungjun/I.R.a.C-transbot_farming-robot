cmake_minimum_required(VERSION 3.0.2)
project(manipulator_position_controller)

find_package(catkin REQUIRED COMPONENTS
  rospy
  std_msgs
  geometry_msgs
  moveit_commander
  moveit_msgs
  actionlib
  tf
  sensor_msgs
)

catkin_package()

include_directories(${catkin_INCLUDE_DIRS})
