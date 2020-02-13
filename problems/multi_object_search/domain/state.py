# Defines the State for the 2D Multi-Object Search domain;
#
# Origin: Multi-Object Search using Object-Oriented POMDPs (ICRA 2019)
# (extensions: action space changes,
#              different sensor model,
#              gridworld instead of topological graph)
#
# Description: Multi-Object Search in a 2D grid world.
#
# State space: S1 X S2 X ... Sn X Sr
#              where Si (1<=i<=n) is the object state, with attribute "pose" (x,y)
#              and Sr is the state of the robot, with attribute "pose" (x,y) and
#              "objects_found" (set).

import pomdp_py
import math

###### States ######
class ObjectState(pomdp_py.ObjectState):
    def __init__(self, objid, objclass, pose):
        super().__init__(objclass, {"pose":pose, "id":objid})
    def __str__(self):
        return '%s%s' % (str(self.objclass), str(self.pose))
    @property
    def pose(self):
        return self.attributes['pose']
    @property
    def objid(self):
        return self.attributes['id']

class RobotState(pomdp_py.ObjectState):
    def __init__(self, robot_id, pose, objects_found, camera_direction):
        """Note: camera_direction is None unless the robot is looking at a direction,
        in which case camera_direction is the string e.g. look+x, or 'look'"""
        super().__init__("robot", {"id":robot_id,
                                   "pose":pose,  # x,y,th
                                   "objects_found": objects_found,
                                   "camera_direction": camera_direction})
    def __str__(self):
        return 'RobotState(%s%s|%s)' % (str(self.objclass), str(self.pose), str(self.objects_found))
    def __repr__(self):
        return str(self)
    @property
    def pose(self):
        return self.attributes['pose']
    @property
    def robot_pose(self):
        return self.attributes['pose']
    @property
    def objects_found(self):
        return self.attributes['objects_found']

class MosOOState(pomdp_py.OOState):
    def __init__(self, object_states):
        super().__init__(object_states)
    def object_pose(self, objid):
        return self.object_states[objid]["pose"]
    def pose(self, objid):
        return self.object_pose(objid)
    @property
    def object_poses(self):
        return {objid:self.object_states[objid]['pose']
                for objid in self.object_states
                if objid != self._robot_id}
    def __str__(self):
        return 'MosOOState(%d)%s' % (str(self.object_states))
    def __repr__(self):
        return str(self)