/*******************************************************************************
* Copyright 2018 ROBOTIS CO., LTD.
*
* Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
*
*     http://www.apache.org/licenses/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.
*******************************************************************************/

/* Authors: Darby Lim, Hye-Jong KIM, Ryan Shim, Yong-Ho Na */

#include "open_manipulator_teleop/open_manipulator_teleop_keyboard.h"

OpenManipulatorTeleop::OpenManipulatorTeleop()
    : node_handle_(""),
    priv_node_handle_("~")
{
    /************************************************************
    ** Initialize variables
    ************************************************************/
    present_joint_angle_.resize(NUM_OF_JOINT);
    present_kinematic_position_.resize(3);

    /************************************************************
    ** Initialize ROS Subscribers and Clients
    ************************************************************/
    initSubscriber();
    initClient();

    disableWaitingForEnter(); //제거할 것
    ROS_INFO("OpenManipulator teleoperation using keyboard start");
}

OpenManipulatorTeleop::~OpenManipulatorTeleop()
{
    restoreTerminalSettings();
    ROS_INFO("Terminate OpenManipulator Joystick");
    ros::shutdown();
}

void OpenManipulatorTeleop::initClient()
{
    goal_joint_space_path_client_ = node_handle_.serviceClient<open_manipulator_msgs::SetJointPosition>("goal_joint_space_path");
    goal_joint_space_path_from_present_client_ = node_handle_.serviceClient<open_manipulator_msgs::SetJointPosition>("goal_joint_space_path_from_present");
    goal_task_space_path_from_present_position_only_client_ = node_handle_.serviceClient<open_manipulator_msgs::SetKinematicsPose>("goal_task_space_path_from_present_position_only");
    goal_tool_control_client_ = node_handle_.serviceClient<open_manipulator_msgs::SetJointPosition>("goal_tool_control");
    //토픽 추가
}

void OpenManipulatorTeleop::initSubscriber()
{
    joint_states_sub_ = node_handle_.subscribe("joint_states", 10, &OpenManipulatorTeleop::jointStatesCallback, this);
    kinematics_pose_sub_ = node_handle_.subscribe("kinematics_pose", 10, &OpenManipulatorTeleop::kinematicsPoseCallback, this);
    ros::Subscriber sub = n.subscribe("chatter", 1000, chatterCallback);
}
void chatterCallback(const std_msgs::String::ConstPtr& msg)     //토픽 테스트
{
    // 수신한 메시지를 화면에 출력
    ROS_INFO("I heard: [%s]", msg->data.c_str());
}

void OpenManipulatorTeleop::jointStatesCallback(const sensor_msgs::JointState::ConstPtr& msg)
{
    std::vector<double> temp_angle;
    temp_angle.resize(NUM_OF_JOINT);
    for (std::vector<int>::size_type i = 0; i < msg->name.size(); i++)
    {
        if (!msg->name.at(i).compare("joint1"))  temp_angle.at(0) = (msg->position.at(i));
        else if (!msg->name.at(i).compare("joint2"))  temp_angle.at(1) = (msg->position.at(i));
        else if (!msg->name.at(i).compare("joint3"))  temp_angle.at(2) = (msg->position.at(i));
        else if (!msg->name.at(i).compare("joint4"))  temp_angle.at(3) = (msg->position.at(i));
    }
    present_joint_angle_ = temp_angle;
}

void OpenManipulatorTeleop::kinematicsPoseCallback(const open_manipulator_msgs::KinematicsPose::ConstPtr& msg)
{
    std::vector<double> temp_position;
    temp_position.push_back(msg->pose.position.x);
    temp_position.push_back(msg->pose.position.y);
    temp_position.push_back(msg->pose.position.z);
    present_kinematic_position_ = temp_position;
}

std::vector<double> OpenManipulatorTeleop::getPresentJointAngle()
{
    return present_joint_angle_;
}

std::vector<double> OpenManipulatorTeleop::getPresentKinematicsPose()
{
    return present_kinematic_position_;
}

bool OpenManipulatorTeleop::setJointSpacePathFromPresent(std::vector<std::string> joint_name, std::vector<double> joint_angle, double path_time)
{
    open_manipulator_msgs::SetJointPosition srv;
    srv.request.joint_position.joint_name = joint_name;
    srv.request.joint_position.position = joint_angle;
    srv.request.path_time = path_time;

    if (goal_joint_space_path_from_present_client_.call(srv))
    {
        return srv.response.is_planned;
    }
    return false;
}

bool OpenManipulatorTeleop::setJointSpacePath(std::vector<std::string> joint_name, std::vector<double> joint_angle, double path_time)
{
    open_manipulator_msgs::SetJointPosition srv;
    srv.request.joint_position.joint_name = joint_name;
    srv.request.joint_position.position = joint_angle;
    srv.request.path_time = path_time;

    if (goal_joint_space_path_client_.call(srv))
    {
        return srv.response.is_planned;
    }
    return false;
}

bool OpenManipulatorTeleop::setToolControl(std::vector<double> joint_angle)
{
    open_manipulator_msgs::SetJointPosition srv;
    srv.request.joint_position.joint_name.push_back(priv_node_handle_.param<std::string>("end_effector_name", "gripper"));
    srv.request.joint_position.position = joint_angle;

    if (goal_tool_control_client_.call(srv))
    {
        return srv.response.is_planned;
    }
    return false;
}

bool OpenManipulatorTeleop::setTaskSpacePathFromPresentPositionOnly(std::vector<double> kinematics_pose, double path_time)
{
    open_manipulator_msgs::SetKinematicsPose srv;
    srv.request.planning_group = priv_node_handle_.param<std::string>("end_effector_name", "gripper");
    srv.request.kinematics_pose.pose.position.x = kinematics_pose.at(0);
    srv.request.kinematics_pose.pose.position.y = kinematics_pose.at(1);
    srv.request.kinematics_pose.pose.position.z = kinematics_pose.at(2);
    srv.request.path_time = path_time;

    if (goal_task_space_path_from_present_position_only_client_.call(srv))
    {
        return srv.response.is_planned;
    }
    return false;
}

void OpenManipulatorTeleop::printText()
{
    printf("\n");
    printf("---------------------------\n");
    printf("Control Your OpenManipulator!\n");
    printf("---------------------------\n");
    printf("w : increase x axis in task space\n");
    printf("s : decrease x axis in task space\n");
    printf("a : increase y axis in task space\n");
    printf("d : decrease y axis in task space\n");
    printf("z : increase z axis in task space\n");
    printf("x : decrease z axis in task space\n");
    printf("\n");
    printf("g : gripper open\n");
    printf("f : gripper close\n");
    printf("       \n");
    printf("0 : xyz select\n");
    printf("1 : init pose\n");
    printf("2 : home pose\n");
    printf("       \n");
    printf("q to quit\n");
    printf("---------------------------\n");
    printf("Present Joint Angle J1: %.3lf J2: %.3lf J3: %.3lf J4: %.3lf\n",
        getPresentJointAngle().at(0),
        getPresentJointAngle().at(1),
        getPresentJointAngle().at(2),
        getPresentJointAngle().at(3));
    printf("Present Kinematics Position X: %.3lf Y: %.3lf Z: %.3lf\n",
        getPresentKinematicsPose().at(0),
        getPresentKinematicsPose().at(1),
        getPresentKinematicsPose().at(2));
    printf("---------------------------\n");

}

void OpenManipulatorTeleop::setGoal(char ch)
{
    std::vector<double> goalPose;  goalPose.resize(3, 0.0);
    std::vector<double> goalJoint; goalJoint.resize(NUM_OF_JOINT, 0.0);

    if (ch == 'w' || ch == 'W')
    {
        printf("input : w \tincrease(++) x axis in task space\n");
        goalPose.at(0) = DELTA;
        setTaskSpacePathFromPresentPositionOnly(goalPose, PATH_TIME);
    }
    else if (ch == 's' || ch == 'S')
    {
        printf("input : s \tdecrease(--) x axis in task space\n");
        goalPose.at(0) = -DELTA;
        setTaskSpacePathFromPresentPositionOnly(goalPose, PATH_TIME);
    }
    else if (ch == 'a' || ch == 'A')
    {
        printf("input : a \tincrease(++) y axis in task space\n");
        goalPose.at(1) = DELTA;
        setTaskSpacePathFromPresentPositionOnly(goalPose, PATH_TIME);
    }
    else if (ch == 'd' || ch == 'D')
    {
        printf("input : d \tdecrease(--) y axis in task space\n");
        goalPose.at(1) = -DELTA;
        setTaskSpacePathFromPresentPositionOnly(goalPose, PATH_TIME);
    }
    else if (ch == 'z' || ch == 'Z')
    {
        printf("input : z \tincrease(++) z axis in task space\n");
        goalPose.at(2) = DELTA;
        setTaskSpacePathFromPresentPositionOnly(goalPose, PATH_TIME);
    }
    else if (ch == 'x' || ch == 'X')
    {
        printf("input : x \tdecrease(--) z axis in task space\n");
        goalPose.at(2) = -DELTA;
        setTaskSpacePathFromPresentPositionOnly(goalPose, PATH_TIME);
    }
    else if (ch == 'g' || ch == 'G')
    {
        printf("input : g \topen gripper\n");
        std::vector<double> joint_angle;

        joint_angle.push_back(0.01);
        setToolControl(joint_angle);
    }
    else if (ch == 'f' || ch == 'F')
    {
        printf("input : f \tclose gripper\n");
        std::vector<double> joint_angle;
        joint_angle.push_back(-0.01);
        setToolControl(joint_angle);
    }
    else if (ch == '2')
    {
        printf("input : 2 \thome pose\n");
        std::vector<std::string> joint_name;
        std::vector<double> joint_angle;
        double path_time = 2.0;

        joint_name.push_back("joint1"); joint_angle.push_back(0.0);
        joint_name.push_back("joint2"); joint_angle.push_back(-1.05);
        joint_name.push_back("joint3"); joint_angle.push_back(0.35);
        joint_name.push_back("joint4"); joint_angle.push_back(0);
        setJointSpacePath(joint_name, joint_angle, path_time);
    }
    else if (ch == '1')
    {
        printf("input : 1 \tinit pose\n");

        std::vector<std::string> joint_name;
        std::vector<double> joint_angle;
        double path_time = 2.0;
        joint_name.push_back("joint1"); joint_angle.push_back(0.0);
        joint_name.push_back("joint2"); joint_angle.push_back(0.0);
        joint_name.push_back("joint3"); joint_angle.push_back(0.0);
        joint_name.push_back("joint4"); joint_angle.push_back(0.0);
        setJointSpacePath(joint_name, joint_angle, path_time);
    }
    else if (ch == '0')
    {
        printf("input : 0 \thome pose\n");
        std::vector<std::string> joint_name;
        std::vector<double> joint_angle;
        double path_time = 2.0;

        joint_name.push_back("joint1"); joint_angle.push_back(0.0);
        joint_name.push_back("joint2"); joint_angle.push_back(1.376);
        joint_name.push_back("joint3"); joint_angle.push_back(-1.402);
        joint_name.push_back("joint4"); joint_angle.push_back(0.1290);
        setJointSpacePath(joint_name, joint_angle, path_time);
    }
}



int main(int argc, char** argv)
{
    // Init ROS node
    ros::init(argc, argv, "open_manipulator_teleop_keyboard");
    OpenManipulatorTeleop openManipulatorTeleop;

    char ch;

    openManipulatorTeleop.printText();
    while (ros::ok() && (ch = std::getchar()) != 'q')
    {
        ros::spinOnce();    //콜백 확인
        openManipulatorTeleop.printText();
        ros::spinOnce();
        openManipulatorTeleop.setGoal(ch);
    }

    return 0;
}
