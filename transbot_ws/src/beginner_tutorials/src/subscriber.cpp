#include "ros/ros.h"
#include "std_msgs/String.h"

// "chatter" 토픽에서 메시지를 수신했을 때 호출될 콜백 함수
void chatterCallback(const std_msgs::String::ConstPtr& msg)
{
  // 수신한 메시지를 화면에 출력
  ROS_INFO("I heard: [%s]", msg->data.c_str());
}

int main(int argc, char **argv)
{
  // ROS 노드 초기화. 노드 이름은 "listener"로 지정합니다.
  ros::init(argc, argv, "listener");

  // 노드 핸들 생성
  ros::NodeHandle n;

  // "chatter" 토픽을 구독하는 Subscriber 설정
  // 메시지를 받으면 chatterCallback 함수를 호출합니다.
  ros::Subscriber sub = n.subscribe("chatter", 1000, chatterCallback);

  // 콜백 함수가 호출되기를 무한정 대기
  ros::spin();

  return 0;
}
