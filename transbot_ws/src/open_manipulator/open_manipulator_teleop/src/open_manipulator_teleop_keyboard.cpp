// open_manipulator_teleop_keyboard.cpp
// Modified for ROS Noetic + parameterized configuration and safety checks
// Place in your open_manipulator_teleop package src/ directory.

#include <ros/ros.h>
#include <sensor_msgs/JointState.h>
#include <open_manipulator_msgs/SetJointPosition.h>
#include <open_manipulator_msgs/SetKinematicsPose.h>

#include <termios.h>
#include <unistd.h>
#include <signal.h>

#include <vector>
#include <string>
#include <iostream>
#include <algorithm>
#include <mutex>
#include <tf2/LinearMath/Quaternion.h>


#define NUM_OF_JOINT 5

class OpenManipulatorTeleop
{
public:
  OpenManipulatorTeleop();
  ~OpenManipulatorTeleop();

  void printText();
  void setGoal(char ch);
  std::vector<double> getPresentJointAngle();
  std::vector<double> getPresentKinematicsPose();

private:
  // ROS
  ros::NodeHandle nh_;
  ros::NodeHandle pnh_;

  // Subscribers and service clients
  ros::Subscriber joint_states_sub_;
  ros::Subscriber kinematics_pose_sub_;

  ros::ServiceClient goal_joint_space_path_client_;
  ros::ServiceClient goal_joint_space_path_from_present_client_;
  ros::ServiceClient goal_task_space_path_from_present_position_only_client_;
  ros::ServiceClient goal_tool_control_client_;
  ros::ServiceClient goal_task_space_path_from_present_client_;
  
  
  // Present states
  std::vector<double> present_joint_angle_;
  std::vector<double> present_kinematic_position_;
  std::mutex state_mutex_;

  // Terminal control
  struct termios oldt_;

  // Parameters (configurable)
  double DELTA_;
  double JOINT_DELTA_;
  double PATH_TIME_;
  std::string joint_state_topic_;
  std::string kinematics_pose_topic_;
  std::string goal_joint_space_path_service_name_;
  std::string goal_joint_space_path_from_present_service_name_;
  std::string goal_task_space_path_from_present_position_only_service_name_;
  std::string goal_tool_control_service_name_;
  std::string end_effector_name_;
  std::vector<std::string> joint_names_;

  // helpers
  void initSubscribers();
  void initClients();
  void jointStatesCallback(const sensor_msgs::JointState::ConstPtr &msg);
  void kinematicsPoseCallback(const open_manipulator_msgs::KinematicsPose::ConstPtr &msg);

  void restoreTerminalSettings(void);
};

OpenManipulatorTeleop::OpenManipulatorTeleop()
: nh_(),
  pnh_("~"),
  present_joint_angle_(NUM_OF_JOINT, 0.0),
  present_kinematic_position_(3, 0.0)
{
  // Load parameters with sensible defaults
  pnh_.param("delta", DELTA_, 0.01);
  pnh_.param("joint_delta", JOINT_DELTA_, 0.1);
  pnh_.param("path_time", PATH_TIME_, 1.0);

  pnh_.param("joint_state_topic", joint_state_topic_, std::string("joint_states"));
  pnh_.param("kinematics_pose_topic", kinematics_pose_topic_, std::string("kinematics_pose"));

  pnh_.param("goal_joint_space_path_service", goal_joint_space_path_service_name_, std::string("goal_joint_space_path"));
  pnh_.param("goal_joint_space_path_from_present_service", goal_joint_space_path_from_present_service_name_, std::string("goal_joint_space_path_from_present"));
  pnh_.param("goal_task_space_path_from_present_position_only_service", goal_task_space_path_from_present_position_only_service_name_, std::string("goal_task_space_path_from_present_position_only"));
  pnh_.param("goal_tool_control_service", goal_tool_control_service_name_, std::string("goal_tool_control"));

  pnh_.param("end_effector_name", end_effector_name_, std::string("gripper"));

  // joint_names: default to joint1..joint4 if not provided
  XmlRpc::XmlRpcValue jnames;
  if (pnh_.getParam("joint_names", jnames) && jnames.getType() == XmlRpc::XmlRpcValue::TypeArray) {
    joint_names_.clear();
    for (int i = 0; i < jnames.size(); ++i) {
      joint_names_.push_back(static_cast<std::string>(jnames[i]));
    }
  } else {
    joint_names_.clear();
    joint_names_.push_back("joint1");
    joint_names_.push_back("joint2");
    joint_names_.push_back("joint3");
    joint_names_.push_back("joint3_5");
    joint_names_.push_back("joint4");
  }

  // Resize present arrays to match joint_names if needed
  present_joint_angle_.assign(joint_names_.size(), 0.0);

  // Init ros comms
  initSubscribers();
  initClients();


  ROS_INFO("OpenManipulator teleoperation using keyboard started");
  ROS_INFO("Parameters: DELTA=%.4f JOINT_DELTA=%.4f PATH_TIME=%.2f", DELTA_, JOINT_DELTA_, PATH_TIME_);
  ROS_INFO("Using services: %s , %s , %s , %s",
           goal_joint_space_path_service_name_.c_str(),
           goal_joint_space_path_from_present_service_name_.c_str(),
           goal_task_space_path_from_present_position_only_service_name_.c_str(),
           goal_tool_control_service_name_.c_str());
}

OpenManipulatorTeleop::~OpenManipulatorTeleop()
{
  restoreTerminalSettings();
  ROS_INFO("Terminate OpenManipulator Teleop");
  // Let ROS shutdown where appropriate (main handles ros::shutdown if desired)
}

void OpenManipulatorTeleop::initClients()
{
  goal_joint_space_path_client_ = nh_.serviceClient<open_manipulator_msgs::SetJointPosition>(goal_joint_space_path_service_name_);
  goal_joint_space_path_from_present_client_ = nh_.serviceClient<open_manipulator_msgs::SetJointPosition>(goal_joint_space_path_from_present_service_name_);
  goal_task_space_path_from_present_position_only_client_ = nh_.serviceClient<open_manipulator_msgs::SetKinematicsPose>(goal_task_space_path_from_present_position_only_service_name_);
  goal_tool_control_client_ = nh_.serviceClient<open_manipulator_msgs::SetJointPosition>(goal_tool_control_service_name_);
  
  goal_task_space_path_from_present_client_ = nh_.serviceClient<open_manipulator_msgs::SetKinematicsPose>("goal_task_space_path_from_present"); //||\\

  // Wait for services (non-blocking long wait would stall startup; use small wait with warning)
  ros::Duration wait_for(0.5);
  if (!goal_joint_space_path_client_.waitForExistence(wait_for)) {
    ROS_WARN("Service '%s' not available at startup (will attempt at call time)", goal_joint_space_path_service_name_.c_str());
  }
  if (!goal_joint_space_path_from_present_client_.waitForExistence(wait_for)) {
    ROS_WARN("Service '%s' not available at startup (will attempt at call time)", goal_joint_space_path_from_present_service_name_.c_str());
  }
  if (!goal_task_space_path_from_present_position_only_client_.waitForExistence(wait_for)) {
    ROS_WARN("Service '%s' not available at startup (will attempt at call time)", goal_task_space_path_from_present_position_only_service_name_.c_str());
  }
  if (!goal_tool_control_client_.waitForExistence(wait_for)) {
    ROS_WARN("Service '%s' not available at startup (will attempt at call time)", goal_tool_control_service_name_.c_str());
  }
}

void OpenManipulatorTeleop::initSubscribers()
{
  joint_states_sub_ = nh_.subscribe(joint_state_topic_, 10, &OpenManipulatorTeleop::jointStatesCallback, this);
  kinematics_pose_sub_ = nh_.subscribe(kinematics_pose_topic_, 10, &OpenManipulatorTeleop::kinematicsPoseCallback, this);
}

void OpenManipulatorTeleop::jointStatesCallback(const sensor_msgs::JointState::ConstPtr &msg)
{
  std::vector<double> temp_angle;
  temp_angle.assign(joint_names_.size(), 0.0);

  // Map incoming joint states by name
  for (size_t i = 0; i < msg->name.size(); ++i)
  {
    for (size_t j = 0; j < joint_names_.size(); ++j)
    {
      if (msg->name[i] == joint_names_[j]) {
        if (i < msg->position.size()) temp_angle[j] = msg->position[i];
      }
    }
  }

  {
    std::lock_guard<std::mutex> guard(state_mutex_);
    present_joint_angle_ = temp_angle;
  }
}

void OpenManipulatorTeleop::kinematicsPoseCallback(const open_manipulator_msgs::KinematicsPose::ConstPtr &msg)
{
  std::vector<double> temp_position(3, 0.0);
  temp_position[0] = msg->pose.position.x;
  temp_position[1] = msg->pose.position.y;
  temp_position[2] = msg->pose.position.z;

  {
    std::lock_guard<std::mutex> guard(state_mutex_);
    present_kinematic_position_ = temp_position;
  }
}

std::vector<double> OpenManipulatorTeleop::getPresentJointAngle()
{
  std::lock_guard<std::mutex> guard(state_mutex_);
  return present_joint_angle_;
}

std::vector<double> OpenManipulatorTeleop::getPresentKinematicsPose()
{
  std::lock_guard<std::mutex> guard(state_mutex_);
  return present_kinematic_position_;
}

// Service wrappers with safety: try to call; if not available, warn and return false
bool callSetJointSpacePathFromPresent(ros::ServiceClient &client,
                                      const std::vector<std::string> &joint_name,
                                      const std::vector<double> &joint_angle,
                                      double path_time)
{
  if (!client.exists()) {
    ROS_WARN("Service not available for SetJointSpacePathFromPresent");
    return false;
  }
  open_manipulator_msgs::SetJointPosition srv;
  srv.request.joint_position.joint_name = joint_name;
  srv.request.joint_position.position = joint_angle;
  srv.request.path_time = path_time;
  if (client.call(srv)) {
    return srv.response.is_planned;
  }
  ROS_WARN("Service call failed (SetJointSpacePathFromPresent)");
  return false;
}

bool callSetTaskSpacePathFromPresent(
  ros::ServiceClient &client,
  const std::string &planning_group,
  const std::vector<double> &pose, // [x y z roll pitch]
  double path_time)
{
  open_manipulator_msgs::SetKinematicsPose srv;

  srv.request.planning_group = planning_group;

  // position
  srv.request.kinematics_pose.pose.position.x = pose[0];
  srv.request.kinematics_pose.pose.position.y = pose[1];
  srv.request.kinematics_pose.pose.position.z = pose[2];

  // orientation (RPY → quaternion)
  tf2::Quaternion q;
  q.setRPY(pose[3], pose[4], 0.0); // yaw 버림

  srv.request.kinematics_pose.pose.orientation.x = q.x();
  srv.request.kinematics_pose.pose.orientation.y = q.y();
  srv.request.kinematics_pose.pose.orientation.z = q.z();
  srv.request.kinematics_pose.pose.orientation.w = q.w();

  srv.request.path_time = path_time;

  return client.call(srv);
}


bool callSetJointSpacePath(ros::ServiceClient &client,
                           const std::vector<std::string> &joint_name,
                           const std::vector<double> &joint_angle,
                           double path_time)
{
  if (!client.exists()) {
    ROS_WARN("Service not available for SetJointSpacePath");
    return false;
  }
  open_manipulator_msgs::SetJointPosition srv;
  srv.request.joint_position.joint_name = joint_name;
  srv.request.joint_position.position = joint_angle;
  srv.request.path_time = path_time;
  if (client.call(srv)) {
    return srv.response.is_planned;
  }
  ROS_WARN("Service call failed (SetJointSpacePath)");
  return false;
}

bool callSetToolControl(ros::ServiceClient &client,
                        const std::string &tool_name,
                        const std::vector<double> &joint_angle)
{
  if (!client.exists()) {
    ROS_WARN("Service not available for SetToolControl");
    return false;
  }
  open_manipulator_msgs::SetJointPosition srv;
  srv.request.joint_position.joint_name.push_back(tool_name);
  srv.request.joint_position.position = joint_angle;
  if (client.call(srv)) {
    return srv.response.is_planned;
  }
  ROS_WARN("Service call failed (SetToolControl)");
  return false;
}

bool callSetTaskSpacePathFromPresentPositionOnly(ros::ServiceClient &client,
                                                 const std::string &planning_group,
                                                 const std::vector<double> &kinematics_pose,
                                                 double path_time)
{
  if (!client.exists()) {
    ROS_WARN("Service not available for SetTaskSpacePathFromPresentPositionOnly");
    return false;
  }
  open_manipulator_msgs::SetKinematicsPose srv;
  srv.request.planning_group = planning_group;
  srv.request.kinematics_pose.pose.position.x = kinematics_pose.at(0);
  srv.request.kinematics_pose.pose.position.y = kinematics_pose.at(1);
  srv.request.kinematics_pose.pose.position.z = kinematics_pose.at(2);
  srv.request.path_time = path_time;
  if (client.call(srv)) {
    return srv.response.is_planned;
  }
  ROS_WARN("Service call failed (SetTaskSpacePathFromPresentPositionOnly)");
  return false;
}

void OpenManipulatorTeleop::printText()
{
  std::vector<double> joints = getPresentJointAngle();
  std::vector<double> pose = getPresentKinematicsPose();

  printf("\n");
  printf("---------------------------\n");
  printf("Control Your OpenManipulator!\n");
  printf("---------------------------\n");
  printf("w/s/a/d/z/x : move in task space (x/y/z +/-)\n");
  printf("y/h u/j i/k o/l : increase/decrease joint 1/2/3/4\n");
  printf("g : gripper open, f : gripper close\n");
  printf("1 : init pose, 2 : home pose\n");
  printf("q to quit\n");
  printf("---------------------------\n");
  // Print according to configured joint names
  printf("Present Joint Angles:\n");
  for (size_t i = 0; i < joint_names_.size(); ++i) {
    printf(" %s: %.3lf", joint_names_[i].c_str(), (i < joints.size() ? joints[i] : 0.0));
  }
  printf("\n");
  printf("Present Kinematics Position X: %.3lf Y: %.3lf Z: %.3lf\n",
         (pose.size()>0?pose[0]:0.0),
         (pose.size()>1?pose[1]:0.0),
         (pose.size()>2?pose[2]:0.0));
  printf("---------------------------\n");
}

void OpenManipulatorTeleop::setGoal(char ch)
{
  std::vector<double> goalPose(3, 0.0);
  std::vector<double> goal_Pose(5, 0.0);
  std::vector<double> goalJoint(joint_names_.size(), 0.0);

  // Local helpers to call services via member clients
  auto &c1 = goal_joint_space_path_from_present_client_;
  auto &c2 = goal_joint_space_path_client_;
  auto &c3 = goal_task_space_path_from_present_position_only_client_;
  auto &c4 = goal_tool_control_client_;
  auto &c5 = goal_task_space_path_from_present_client_;

  if (ch == 'w' || ch == 'W')
  {
    ROS_INFO("input: w (increase x)");
    goalPose.at(0) = DELTA_;
    callSetTaskSpacePathFromPresentPositionOnly(c3, end_effector_name_, goalPose, PATH_TIME_);
  }
  else if (ch == 's' || ch == 'S')
  {
    ROS_INFO("input: s (decrease x)");
    goalPose.at(0) = -DELTA_;
    callSetTaskSpacePathFromPresentPositionOnly(c3, end_effector_name_, goalPose, PATH_TIME_);
  }
  else if (ch == 'a' || ch == 'A')
  {
    ROS_INFO("input: a (increase y)");
    goalPose.at(1) = DELTA_;
    callSetTaskSpacePathFromPresentPositionOnly(c3, end_effector_name_, goalPose, PATH_TIME_);
  }
  else if (ch == 'd' || ch == 'D')
  {
    ROS_INFO("input: d (decrease y)");
    goalPose.at(1) = -DELTA_;
    callSetTaskSpacePathFromPresentPositionOnly(c3, end_effector_name_, goalPose, PATH_TIME_);
  }
  else if (ch == 'z' || ch == 'Z')
  {
    ROS_INFO("input: z (increase z)");
    goalPose.at(2) = DELTA_;
    callSetTaskSpacePathFromPresentPositionOnly(c3, end_effector_name_, goalPose, PATH_TIME_);
  }
  else if (ch == 'x' || ch == 'X')
  {
    ROS_INFO("input: x (decrease z)");
    goalPose.at(2) = -DELTA_;
    callSetTaskSpacePathFromPresentPositionOnly(c3, end_effector_name_, goalPose, PATH_TIME_);
  }
  else if (ch == 'y' || ch == 'Y')
  {
    ROS_INFO("input: y (increase joint 1)");
    if (joint_names_.size() >= 4) goalJoint.at(0) = JOINT_DELTA_;
    callSetJointSpacePathFromPresent(c1, joint_names_, goalJoint, PATH_TIME_);
  }
  else if (ch == 'h' || ch == 'H')
  {
    ROS_INFO("input: h (decrease joint 1)");
    if (joint_names_.size() >= 1) goalJoint.at(0) = -JOINT_DELTA_;
    callSetJointSpacePathFromPresent(c1, joint_names_, goalJoint, PATH_TIME_);
  }
  else if (ch == 'u' || ch == 'U')
  {
    ROS_INFO("input: u (increase joint 2)");
    if (joint_names_.size() >= 2) goalJoint.at(1) = JOINT_DELTA_;
    callSetJointSpacePathFromPresent(c1, joint_names_, goalJoint, PATH_TIME_);
  }
  else if (ch == 'j' || ch == 'J')
  {
    ROS_INFO("input: j (decrease joint 2)");
    if (joint_names_.size() >= 2) goalJoint.at(1) = -JOINT_DELTA_;
    callSetJointSpacePathFromPresent(c1, joint_names_, goalJoint, PATH_TIME_);
  }
  else if (ch == 'i' || ch == 'I')
  {
    ROS_INFO("input: i (increase joint 3)");
    if (joint_names_.size() >= 3) goalJoint.at(2) = JOINT_DELTA_;
    callSetJointSpacePathFromPresent(c1, joint_names_, goalJoint, PATH_TIME_);
  }
  else if (ch == 'k' || ch == 'K')
  {
    ROS_INFO("input: k (decrease joint 3)");
    if (joint_names_.size() >= 3) goalJoint.at(2) = -JOINT_DELTA_;
    callSetJointSpacePathFromPresent(c1, joint_names_, goalJoint, PATH_TIME_);
  }
  else if (ch == 'o' || ch == 'O')
  {
    ROS_INFO("input: o (increase joint 4)");
    if (joint_names_.size() >= 4) goalJoint.at(3) = JOINT_DELTA_;
    callSetJointSpacePathFromPresent(c1, joint_names_, goalJoint, PATH_TIME_);
  }
  else if (ch == 'l' || ch == 'L')
  {
    ROS_INFO("input: l (decrease joint 4)");
    if (joint_names_.size() >= 4) goalJoint.at(3) = -JOINT_DELTA_;
    callSetJointSpacePathFromPresent(c1, joint_names_, goalJoint, PATH_TIME_);
  }
  else if (ch == 'p' || ch == 'P')
  {
    ROS_INFO("input: o (increase joint 5)");
    if (joint_names_.size() >= 5) goalJoint.at(4) = JOINT_DELTA_;
    callSetJointSpacePathFromPresent(c1, joint_names_, goalJoint, PATH_TIME_);
  }
  else if (ch == ';' || ch == ':')
  {
    ROS_INFO("input: l (decrease joint 5)");
    if (joint_names_.size() >= 5) goalJoint.at(4) = -JOINT_DELTA_;
    callSetJointSpacePathFromPresent(c1, joint_names_, goalJoint, PATH_TIME_);
  }
  else if (ch == 'g' || ch == 'G')
  {
    ROS_INFO("input: g (open gripper)");
    std::vector<double> joint_angle;
    joint_angle.push_back(0.01);
    callSetToolControl(c4, end_effector_name_, joint_angle);
  }
  else if (ch == 'f' || ch == 'F')
  {
    ROS_INFO("input: f (close gripper)");
    std::vector<double> joint_angle;
    joint_angle.push_back(-0.01);
    callSetToolControl(c4, end_effector_name_, joint_angle);
  }
  

  else if (ch == '2')
  {
    ROS_INFO("input: 2 (home pose)");
    std::vector<double> joint_angle;
    std::vector<std::string> names = joint_names_;
    double path_time = 2.0;

    // If size mismatch, fill with zeros
    joint_angle.assign(names.size(), 0.0);
    if (names.size() >= 1) joint_angle[0] = 0.0;
    if (names.size() >= 2) joint_angle[1] = -1.05;
    if (names.size() >= 3) joint_angle[2] = 0.35;
    if (names.size() >= 4) joint_angle[3] = 0.35;
    if (names.size() >= 5) joint_angle[4] = 0.70;

    callSetJointSpacePath(c2, names, joint_angle, path_time);
  }
  
  else if (ch == '1')
  {
    ROS_INFO("input: 1 (init pose)");
    std::vector<double> joint_angle;
    std::vector<std::string> names = joint_names_;
    double path_time = 2.0;
    joint_angle.assign(names.size(), 0.0);
    callSetJointSpacePath(c2, names, joint_angle, path_time);
  }
  
  else if (ch == 'r' || ch == 'R')
  {
    goal_Pose[0] = getPresentKinematicsPose().at(0);
    goal_Pose[1] = getPresentKinematicsPose().at(1);
    goal_Pose[2] = getPresentKinematicsPose().at(2);
    goal_Pose[3] = 0.05;
    goal_Pose[4] = 0.0;
    callSetTaskSpacePathFromPresent(c5, end_effector_name_, goal_Pose, PATH_TIME_);
  }
  
  else if (ch == 't' || 'T')
  {
    goal_Pose[0] = getPresentKinematicsPose().at(0);
    goal_Pose[1] = getPresentKinematicsPose().at(1);
    goal_Pose[2] = getPresentKinematicsPose().at(2);
    goal_Pose[3] = -0.05;
    goal_Pose[4] = 0.0;
    callSetTaskSpacePathFromPresent(c5, end_effector_name_, goal_Pose, PATH_TIME_);
  }
  
  
  else if (ch == '0')
  {
        double path_time = 2.0;
        double x = 0.0;
        double y = 0.0;
        double z = 0.0;
        printf("input: x y z");
        printf("x : -0.5~0.6 y : -0.5~0.5 z : 0.05 ~ 0.6");

            scanf("%lf %lf %lf", &x, &y, &z);

        goalPose.at(0) = x - getPresentKinematicsPose().at(0);
        goalPose.at(1) = y - getPresentKinematicsPose().at(1);
        goalPose.at(2) = z - getPresentKinematicsPose().at(2);

    callSetTaskSpacePathFromPresentPositionOnly(c3, end_effector_name_, goalPose, PATH_TIME_);
    }
}

// Terminal helpers
void OpenManipulatorTeleop::restoreTerminalSettings(void)
{
  tcsetattr(0, TCSANOW, &oldt_);
}

// Main
int main(int argc, char **argv)
{
  ros::init(argc, argv, "open_manipulator_teleop_keyboard");
  OpenManipulatorTeleop teleop_node;

  char ch;
  teleop_node.printText();
  while (ros::ok())
  {
    // Non-blocking getchar pattern:
    fd_set set;
    struct timeval timeout;
    FD_ZERO(&set);
    FD_SET(0, &set);
    timeout.tv_sec = 0;
    timeout.tv_usec = 100000; // 100ms

    int rv = select(1, &set, NULL, NULL, &timeout);
    if (rv > 0) {
      ch = std::getchar();
      if (ch == 'q') break;
      teleop_node.setGoal(ch);
      teleop_node.printText();
    }
    ros::spinOnce();
  }

  ros::shutdown();
  return 0;
}

