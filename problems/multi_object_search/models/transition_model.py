# Defines the State/Action/TransitionModel for the 2D Multi-Object Search domain;
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
#
# Action space: Motion U Look U Find
#               Motion Actions scheme 1: South, East, West, North.
#               Motion Actions scheme 2: Left 45deg, Right 45deg, Forward
#               motion actions move the robot deterministically.
#               Look: Interprets sensor input as observation
#               Find: Marks objects observed in the last Look action as
#                     (differs from original paper; reduces action space)
#               It is possible to force "Look" after every N/S/E/W action;
#               then the Look action could be dropped. This is optional behavior.
# 
# Transition: deterministic
import pomdp_py
from ..domain.state import *
from ..domain.action import *

####### Transition Model #######
class MosTransitionModel(pomdp_py.OOTransitionModel):
    """Object-oriented transition model"""
    def __init__(self,
                 dim, sensor, object_ids,
                 epsilon=1e-9, for_env=False):
        """
        for_env (bool): True if this is a robot transition model used by the Environment.
             see RobotTransitionModel for details. 
        """
        self._robot_id = sensor.robot_id
        transition_models = {objid: StaticObjectTransitionModel(objid, epsilon=epsilon)
                             for objid in object_ids}
        transition_models[robot_id] = RobotTransitionModel(sensor,
                                                           dim,
                                                           epsilon=epsilon,
                                                           for_env=for_env)
        super().__init__(transition_models)

    def sample(self, state, action, **kwargs):
        oostate = pomdp_py.OOTransitionModel.sample(self, state, action, **kwargs)
        return M3OOState(self._robot_id, oostate.object_states)

    def argmax(self, state, action, normalized=False, **kwargs):
        oostate = pomdp_py.OOTransitionModel.argmax(self, state, action, **kwargs)
        return M3OOState(self._robot_id, oostate.object_states)
    

class StaticObjectTransitionModel(pomdp_py.TransitionModel):
    """This model assumes the object is static."""
    def __init__(self, objid, epsilon=1e-9):
        self._objid = objid
        self._epsilon = epsilon

    def probability(self, next_object_state, state, action):
        if next_object_state != state.object_states[next_object_state['id']]:
            return self._epsilon
        else:
            return 1.0 - self._epsilon
    
    def sample(self, state, action):
        """Returns next_object_state"""
        return self.argmax(state, action)
    
    def argmax(self, state, action):
        """Returns the most likely next object_state"""
        return copy.deepcopy(state.object_states[self._objid])

    
class RobotTransitionModel(pomdp_py.TransitionModel):
    """We assume that the robot control is perfect and transitions are deterministic."""
    def __init__(self, sensor, dim, epsilon=1e-9):
        """
        dim (tuple): a tuple (width, length) for the dimension of the world
        """
        # this is used to determine objects found for FindAction
        self._sensor = sensor
        self._dim = dim
        self._epsilon = epsilon
        

    def _if_move_by(self, state, action, check_collision=True):
        """Defines the dynamics of robot motion"""
        if not isinstance(action, MotionAction):
            raise ValueError("Cannot move robot with %s action" % str(type(action)))

        robot_pose = state.pose(self._sensor.robot_id)
        rx, ry, rth = robot_pose

        if action.scheme == "xy":
            dx, dy, th = action.motion
            rx += dx
            ry += dy
            rth = th

        elif action.scheme == "vw":
            # odometry motion model
            forward, angle = action.motion
            rth += angle  # angle (radian)
            rx = int(round(rx + forward*math.cos(rth)))
            ry = int(round(ry + forward*math.cos(rth)))
            rth = rth % (2*math.pi)

        if self.valid_pose((rx, ry, rth),
                           self._dim[0], self._dim[1],
                           env_state=env_state,
                           check_collision=check_collision):
            return (rx, ry, rth)
        else:
            return robot_pose  # no change because change results in invalid pose
    

    def probability(self, next_robot_state, state, action):
        if next_robot_state != self.argmax(state, action):
            return self._epsilon
        else:
            return 1.0 - self._epsilon

    def argmax(self, state, action):
        """Returns the most likely next robot_state"""
        if isinstance(state, RobotState):
            robot_state = state
        else:
            robot_state = state.object_states[self._sensor.robot_id]
        # using shallow copy because we don't expect object state to reference other objects.            
        next_robot_state = copy.deepcopy(robot_state)
        next_robot_state['camera_direction'] = None  # camera direction is only not None when looking

        if isinstance(action, MotionAction):
            # motion action
            next_robot_state['pose'] = self._if_move_by(state, action)

        elif isinstance(action, LookAction):
            if action.motion is not None:
                # rotate the robot
                next_robot_state['pose'] = self._if_move_by(state, action)
            next_robot_state['camera_direction'] = action.name
                                                                      
        elif isinstance(action, FindAction):
            # detect;
            object_poses = {objid:state.object_states[objid]['pose']
                            for objid in state.object_states
                            if objid != self._sensor.robot_id}
            # the detect action will mark all objects within the view frustum as detected.
            #   (the RGBD camera is always running and receiving point clouds)
            objects = self._gridworld.objects_within_view_range(robot_state['pose'],
                                                                object_poses, volumetric=self._for_env)
            next_robot_state['objects_found'] = tuple(set(next_robot_state['objects_found']) | set(objects))
        return next_robot_state
    
    def sample(self, state, action):
        """Returns next_robot_state"""
        return self.argmax(state, action)


# Utility functions
def valid_pose(pose, width, length, state=None, check_collision=True):
    """
    Returns True if the given `pose` (x,y) is a valid pose;
    If `check_collision` is True, then the pose is only valid
    if it is not overlapping with any object pose in the environment state.
    """
    x, y = pose[:2]

    # Check collision
    if check_collision and state is not None:
        object_poses = state.object_poses
        for objid in object_poses:
            if (x,y) == object_poses[objid]:
                return False
    return in_boundary(pose, width, length)


def in_boundary(pose, width, length):
    # Check if in boundary
    x,y = pose[:2]
    if x >= 0 and x < width:
        if y >= 0 and y < length:
            if len(pose) == 3:
                th = pose[2]  # radian
                if th < 0 or th > 2*math.pi:
                    return False
            return True
    return False