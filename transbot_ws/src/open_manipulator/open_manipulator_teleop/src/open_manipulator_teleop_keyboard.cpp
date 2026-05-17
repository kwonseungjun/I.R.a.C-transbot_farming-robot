/*******************************************************************************
* Copyright 2018 ROBOTIS CO., LTD.
*
* Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
*
* http://www.apache.org/licenses/LICENSE-2.0
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
    initPublisher();
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
}
void OpenManipulatorTeleop::initSubscriber()
{
    joint_states_sub_ = node_handle_.subscribe("joint_states", 10, &OpenManipulatorTeleop::jointStatesCallback, this);
    kinematics_pose_sub_ = node_handle_.subscribe("kinematics_pose", 10, &OpenManipulatorTeleop::kinematicsPoseCallback, this);

    t2m_sub_ = node_handle_.subscribe("t2m", 10, &OpenManipulatorTeleop::t2mCommandCallback, this);
    d2m_sub_ = node_handle_.subscribe("/depth_3d_points", 10, &OpenManipulatorTeleop::d2mCommandCallback, this);
    cls_sub_ = node_handle_.subscribe("/detected_class", 10, &OpenManipulatorTeleop::clsCommandCallback, this);

}
// 새로운 퍼블리셔 초기화 함수 구현
void OpenManipulatorTeleop::initPublisher()
{
    m2t_pub_ = node_handle_.advertise<std_msgs::String>("/m2t", 10);
    m2d_pub_ = node_handle_.advertise<std_msgs::String>("/m2d", 10);

    ROS_INFO("Publishers initialized for /m2d and /m2t.");
}
void OpenManipulatorTeleop::clsCommandCallback(const std_msgs::String::ConstPtr& msg)
{
    if (msg->data == "ripe")
        detect_class = "ripe";
    else if (msg->data == "rotten")
        detect_class = "rotten";
    else
        detect_class = "unknown";
}
// [추가] 외부 토픽을 수신했을 때 호출될 콜백 함수입니다.
void OpenManipulatorTeleop::t2mCommandCallback(const std_msgs::String::ConstPtr& msg)
{

    std_msgs::String pub_msg;

    if (msg->data == "init")     //주행
    {
        setGoal('1');
        setGoal('f');
        ROS_INFO("주행모드");
    }
    if (msg->data == "home")    //작동
    {
        setGoal('2');
        setGoal('g');
        ROS_INFO("작동모드");
    }
    if (msg->data == "grip_open")
    {
        setGoal('g');

        ROS_INFO("그리퍼 오픈");
    }
    if (msg->data == "grip_close")
    {
        setGoal('f');

        ROS_INFO("그리퍼 클로즈");
    }
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

void OpenManipulatorTeleop::d2mCommandCallback(const geometry_msgs::Point::ConstPtr& msg)
{
    std::vector<double> goalPose;  goalPose.resize(3, 0.0);
    std_msgs::String pub_msg;


    double path_time = 2.0;
    double x = msg->x + 0.130;
    double y = msg->y + 0.0282;
    double z = msg->z + 0.052;
    printf("%.3lf %.3lf %.3lf\n", x, y, z);

    goalPose.at(0) = x - getPresentKinematicsPose().at(0) - 0.03;
    goalPose.at(1) = y - getPresentKinematicsPose().at(1);
    goalPose.at(2) = z - getPresentKinematicsPose().at(2);

    setTaskSpacePathFromPresentPositionOnly(goalPose, path_time);

    ros::Duration(2.0).sleep();


    path_time = 1.0;

    goalPose.at(0) = 0.03;
    goalPose.at(1) = 0;
    goalPose.at(2) = 0;

    setTaskSpacePathFromPresentPositionOnly(goalPose, path_time);

    ros::Duration(1.0).sleep();


    setGoal('f');

    ros::Duration(1.0).sleep();


    goalPose.at(0) = 0;
    goalPose.at(1) = 0;
    goalPose.at(2) = -0.03;

    setTaskSpacePathFromPresentPositionOnly(goalPose, path_time);
    ros::Duration(1.0).sleep();


    goalPose.at(0) = -0.03;
    goalPose.at(1) = 0;
    goalPose.at(2) = 0;

    setTaskSpacePathFromPresentPositionOnly(goalPose, path_time);
    ros::Duration(1.0).sleep();

    if(detect_class == 0)
    {
		setGoal('3');
		ros::Duration(4.0).sleep();
	}
	else
	{
	    setGoal('4');
	    ros::Duration(4.0).sleep();
	}	
		
	path_time = 1.0;
	goalPose.at(0) = 0;
	goalPose.at(1) = 0;
	goalPose.at(2) = -0.05;
    setTaskSpacePathFromPresentPositionOnly(goalPose, path_time);
	ros::Duration(1.0).sleep();
		
		
	setGoal('g');
	ros::Duration(1.0).sleep();
		
	goalPose.at(2) = 0.05;
	setTaskSpacePathFromPresentPositionOnly(goalPose, path_time);
	ros::Duration(1.0).sleep();
	
		
    pub_msg.data = "start";
    m2d_pub_.publish(pub_msg);
}

void OpenManipulatorTeleop::setGoal(char ch)
{
    // ... (기존과 동일)
    std::vector<double> goalPose;  goalPose.resize(3, 0.0);
    std::vector<double> goalJoint; goalJoint.resize(NUM_OF_JOINT, 0.0);

    if (ch == 'g' || ch == 'G')
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
    else if (ch == '2')     //작동모드
    {
        printf("input : 2 \thome pose\n");
        std::vector<std::string> joint_name;
        std::vector<double> joint_angle;
        double path_time = 2.0;

        joint_name.push_back("joint1"); joint_angle.push_back(0.0);
        joint_name.push_back("joint2"); joint_angle.push_back(-0.684);
        joint_name.push_back("joint3"); joint_angle.push_back(0.658);
        joint_name.push_back("joint4"); joint_angle.push_back(-0.091);
        setJointSpacePath(joint_name, joint_angle, path_time);
    }
    else if (ch == '1')    //주행모드
    {
        printf("input : 1 \tinit pose\n");

        std::vector<std::string> joint_name;
        std::vector<double> joint_angle;
        double path_time = 2.0;
        joint_name.push_back("joint1"); joint_angle.push_back(0.0);
        joint_name.push_back("joint2"); joint_angle.push_back(-1.43);
        joint_name.push_back("joint3"); joint_angle.push_back(1.247);
        joint_name.push_back("joint4"); joint_angle.push_back(0.212);
        setJointSpacePath(joint_name, joint_angle, path_time);
    }
    else if (ch == '3')    //회수모드
    {
        printf("input : 1 \tinit pose\n");

        std::vector<std::string> joint_name;
        std::vector<double> joint_angle;
        double path_time = 4.0;
        joint_name.push_back("joint1"); joint_angle.push_back(-1.569);
        joint_name.push_back("joint2"); joint_angle.push_back(0.006);
        joint_name.push_back("joint3"); joint_angle.push_back(0.416);
        joint_name.push_back("joint4"); joint_angle.push_back(1.023);
        setJointSpacePath(joint_name, joint_angle, path_time);
    }
    else if (ch == '4')    //처모드
    {
        printf("input : 1 \tinit pose\n");

        std::vector<std::string> joint_name;
        std::vector<double> joint_angle;
        double path_time = 4.0;
        joint_name.push_back("joint1"); joint_angle.push_back(1.569);
        joint_name.push_back("joint2"); joint_angle.push_back(0.006);
        joint_name.push_back("joint3"); joint_angle.push_back(0.416);
        joint_name.push_back("joint4"); joint_angle.push_back(1.023);
        setJointSpacePath(joint_name, joint_angle, path_time);
    }
}

void OpenManipulatorTeleop::restoreTerminalSettings(void)
{
    tcsetattr(0, TCSANOW, &oldt_);  /* Apply saved settings */
}

int main(int argc, char** argv)
{
    // Init ROS node
    ros::init(argc, argv, "open_manipulator_teleop_keyboard");
    OpenManipulatorTeleop openManipulatorTeleop;

    while (ros::ok())
    {
        ros::spinOnce();
    }

    return 0;
}
