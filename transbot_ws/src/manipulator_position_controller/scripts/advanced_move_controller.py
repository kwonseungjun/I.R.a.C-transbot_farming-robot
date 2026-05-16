#!/usr/bin/env python3
"""Advanced move controller node."""
import rospy, threading, time, random, sys
from geometry_msgs.msg import PointStamped, PoseStamped
from std_msgs.msg import String
try:
    from moveit_commander import MoveGroupCommander, roscpp_initialize, roscpp_shutdown
except Exception as e:
    rospy.logerr('moveit_commander import failed: %s', e)
    raise
from copy import deepcopy

class AdvancedMoveController(object):
    def __init__(self):
        rospy.init_node('advanced_move_controller', anonymous=False)
        roscpp_initialize(sys.argv)
        self.move_group_name = rospy.get_param('~move_group', 'manipulator')
        self.reference_frame = rospy.get_param('~reference_frame', 'base_link')
        self.pos_tolerance = rospy.get_param('~pos_tolerance', 0.01)
        self.ori_tolerance = rospy.get_param('~ori_tolerance', 0.1)
        self.max_retries = rospy.get_param('~max_retries', 5)
        self.retry_perturb = rospy.get_param('~retry_perturb', 0.01)
        self.workspace_limits = rospy.get_param('~workspace_limits', {
            'min_x': -1.0, 'max_x': 1.0, 'min_y': -1.0, 'max_y': 1.0, 'min_z': 0.0, 'max_z': 1.5
        })
        self.group = MoveGroupCommander(self.move_group_name)
        rospy.loginfo('Using move group: %s', self.move_group_name)
        self.group.set_goal_position_tolerance(self.pos_tolerance)
        self.group.set_goal_orientation_tolerance(self.ori_tolerance)
        self.queue = []
        self.lock = threading.Lock()
        self.worker = threading.Thread(target=self._worker); self.worker.daemon=True; self.worker.start()
        self.status_pub = rospy.Publisher('manipulator_move_status', String, queue_size=5)
        rospy.Subscriber('target_pose', PoseStamped, self._pose_cb, queue_size=5)
        rospy.Subscriber('target_position', PointStamped, self._point_cb, queue_size=5)
        rospy.on_shutdown(self._on_shutdown)
        rospy.loginfo('advanced_move_controller ready')

    def _publish_status(self, text):
        rospy.loginfo(text)
        self.status_pub.publish(String(text))

    def _pose_cb(self, msg):
        if not msg.header.frame_id:
            msg.header.frame_id = self.reference_frame
        with self.lock:
            self.queue.append(msg)
        self._publish_status('Queued Pose target')

    def _point_cb(self, msg):
        pose = PoseStamped(); pose.header = msg.header
        if not pose.header.frame_id: pose.header.frame_id = self.reference_frame
        pose.pose.position.x = msg.point.x; pose.pose.position.y = msg.point.y; pose.pose.position.z = msg.point.z
        try:
            pose.pose.orientation = self.group.get_current_pose().pose.orientation
        except:
            pose.pose.orientation.w = 1.0
        with self.lock:
            self.queue.append(pose)
        self._publish_status('Queued Point target')

    def _within_workspace(self, p):
        w = self.workspace_limits; pos = p.pose.position
        return (w['min_x'] <= pos.x <= w['max_x'] and w['min_y'] <= pos.y <= w['max_y'] and w['min_z'] <= pos.z <= w['max_z'])

    def _worker(self):
        rate = rospy.Rate(10)
        while not rospy.is_shutdown():
            task=None
            with self.lock:
                if self.queue: task = deepcopy(self.queue.pop(0))
            if not task:
                rate.sleep(); continue
            if not self._within_workspace(task):
                self._publish_status('Rejected: outside workspace')
                continue
            ok = self._attempt_move(task)
            self._publish_status('Completed' if ok else 'Failed')
            time.sleep(0.3)

    def _attempt_move(self, target):
        for attempt in range(self.max_retries):
            rospy.loginfo('Attempt %d/%d', attempt+1, self.max_retries)
            self.group.set_pose_target(target)
            try:
                plan = self.group.plan()
            except Exception as e:
                rospy.logwarn('plan failed: %s', e); plan=None
            valid = plan and hasattr(plan,'joint_trajectory') and len(plan.joint_trajectory.points)>0
            if valid:
                try:
                    ok = self.group.go(wait=True)
                    self.group.stop(); self.group.clear_pose_targets()
                    if ok: return True
                except Exception as e:
                    rospy.logwarn('execution error: %s', e)
            target = self._perturb(target)
        return False

    def _perturb(self, t):
        p = deepcopy(t)
        p.pose.position.x += random.uniform(-self.retry_perturb, self.retry_perturb)
        p.pose.position.y += random.uniform(-self.retry_perturb, self.retry_perturb)
        p.pose.position.z += random.uniform(-self.retry_perturb, self.retry_perturb)
        w = self.workspace_limits; pos = p.pose.position
        pos.x = max(min(pos.x, w['max_x']), w['min_x'])
        pos.y = max(min(pos.y, w['max_y']), w['min_y'])
        pos.z = max(min(pos.z, w['max_z']), w['min_z'])
        return p

    def _on_shutdown(self):
        roscpp_shutdown()

if __name__=='__main__':
    try:
        AdvancedMoveController(); rospy.spin()
    except rospy.ROSInterruptException:
        pass
