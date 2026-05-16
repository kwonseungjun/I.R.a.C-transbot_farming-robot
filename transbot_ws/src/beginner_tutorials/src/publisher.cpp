#include "ros/ros.h"
#include "std_msgs/String.h"
#include <sstream>

int main(int argc, char **argv)
{
  // ROS 노드 초기화. 노드 이름은 "talker"로 지정합니다.
  ros::init(argc, argv, "talker");

  // 노드 핸들 생성
  ros::NodeHandle n;

  // "chatter" 토픽에 std_msgs::String 타입의 메시지를 발행하는 Publisher 설정
  // 큐(queue) 크기는 1000입니다.
  ros::Publisher chatter_pub = n.advertise<std_msgs::String>("chatter", 1000);

  // 1초에 10번 (10Hz) 메시지를 보내도록 주기 설정
  ros::Rate loop_rate(10);

  int count = 0;
  while (ros::ok()) // ROS가 실행 중인 동안 반복
  {
    // 메시지 객체 생성
    std_msgs::String msg;
    std::stringstream ss;
    ss << "hello world " << count;
    msg.data = ss.str();

    // 메시지 내용 출력 및 발행
    ROS_INFO("%s", msg.data.c_str());
    chatter_pub.publish(msg);

    // 콜백 함수 처리 대기
    ros::spinOnce();

    // 설정한 주기에 맞춰 대기
    loop_rate.sleep();
    ++count;
  }
  return 0;
}
