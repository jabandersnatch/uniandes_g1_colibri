# Sim2Sim ROS2 Integration - Architecture & Design

## Overview

This document describes the ROS2 integration layer for the Colibri G1 digital twin, enabling sim2sim transfer testing and future sim2real deployment. The implementation follows a **hybrid approach**: start with minimal functionality, validate thoroughly, then add complexity incrementally.

**Goal**: Enable the trained navigation policy to communicate via ROS2 topics, allowing:
1. External monitoring of robot state (odometry, joint states)
2. External goal setting (via ROS2 topics)
3. Sim2sim transfer testing (two Isaac Lab instances or Isaac Lab ↔ Mujoco)
4. Foundation for sim2real deployment to physical Colibri G1 robot

## Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Isaac Sim Environment                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         Colibri G1 Robot (Unitree G1 Model)           │ │
│  │  - 29 DOF joint control                               │ │
│  │  - Trained navigation policy                           │ │
│  │  - Custom ColibriBuilding.usd scene                    │ │
│  └─────────────────┬──────────────────────────────────────┘ │
│                    │                                         │
│  ┌─────────────────▼──────────────────────────────────────┐ │
│  │          ROS2 Bridge (RobotDataManager)               │ │
│  │  Publishers:                                           │ │
│  │    - /colibri_g1/odom (50 Hz)                        │ │
│  │    - /colibri_g1/joint_states (50 Hz)                │ │
│  │    - /colibri_g1/goal_marker (1 Hz)                  │ │
│  │    - /colibri_g1/navigation/status (10 Hz)           │ │
│  │    - /clock (simulation time)                         │ │
│  │                                                        │ │
│  │  Subscribers:                                          │ │
│  │    - /colibri_g1/cmd_vel (optional override)         │ │
│  │                                                        │ │
│  │  TF Broadcaster:                                       │ │
│  │    - map → base_link                                  │ │
│  │    - base_link → sensor frames (future)              │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          │ ROS2 Network
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
   ┌────▼────┐      ┌────▼────┐      ┌────▼────┐
   │ RViz2   │      │ rqt     │      │ Second  │
   │ Visual  │      │ Metrics │      │ Sim     │
   └─────────┘      └─────────┘      └─────────┘
```

### Navigation System Integration

The ROS2 bridge integrates with the existing **Point-to-Point Navigation System** (Phase 1-5):

```
Goal Command Generator (SimpleGoalCommand)
    │
    ├─→ Goal position (2D: x, y)
    │   └─→ Published as /colibri_g1/goal_marker (visualization)
    │   └─→ Published as /colibri_g1/navigation/goal_pose
    │
    ├─→ Goal-Directed Velocity Commands (GoalDirectedVelocityCommand)
    │   └─→ Velocity always points toward goal
    │   └─→ Distance-based speed scaling
    │   └─→ Published as /colibri_g1/navigation/cmd_vel (monitoring)
    │
    └─→ Trained Navigation Policy
        └─→ Inputs: [goal_pos, base_vel, gravity, joint_states, ...]
        └─→ Outputs: [joint_position_targets]
        └─→ Published as /colibri_g1/joint_states
```

**Key Insight**: The navigation system is **autonomous** - it generates goals internally and publishes them for visualization. External goal commands can be added later without disrupting the core architecture.

---

## ROS2 Topic Structure

### Published Topics

#### `/colibri_g1/odom` (nav_msgs/Odometry)
**Frequency**: 50 Hz
**Frame ID**: `map`
**Child Frame ID**: `base_link`

**Content**:
- **Pose**: 3D position (x, y, z) + orientation (quaternion)
- **Twist**: Linear velocity (vx, vy, vz) + angular velocity (wx, wy, wz)
- **Covariance**: Set to zeros (perfect simulation knowledge)

**Source**: `env.scene["robot"].data.root_state_w[:, :7]` (position + orientation)

#### `/colibri_g1/joint_states` (sensor_msgs/JointState)
**Frequency**: 50 Hz

**Content**:
- **names**: 29 joint names (G1 humanoid joints)
- **position**: Joint angles (rad)
- **velocity**: Joint velocities (rad/s)
- **effort**: Joint torques (Nm) - optional

**Source**: `env.scene["robot"].data.joint_pos`, `env.scene["robot"].data.joint_vel`

**Joint Order** (Unitree G1 29-DOF):
```
Lower Body (12):
  - left_hip_pitch_joint, left_hip_roll_joint, left_hip_yaw_joint
  - left_knee_joint
  - left_ankle_pitch_joint, left_ankle_roll_joint
  - right_hip_pitch_joint, right_hip_roll_joint, right_hip_yaw_joint
  - right_knee_joint
  - right_ankle_pitch_joint, right_ankle_roll_joint

Torso (1):
  - torso_joint

Upper Body (16):
  - left_shoulder_pitch_joint, left_shoulder_roll_joint, left_shoulder_yaw_joint
  - left_elbow_pitch_joint
  - left_wrist_roll_joint, left_wrist_pitch_joint, left_wrist_yaw_joint
  - right_shoulder_pitch_joint, right_shoulder_roll_joint, right_shoulder_yaw_joint
  - right_elbow_pitch_joint
  - right_wrist_roll_joint, right_wrist_pitch_joint, right_wrist_yaw_joint
  - waist_yaw_joint, waist_roll_joint
```

#### `/colibri_g1/pose` (geometry_msgs/PoseStamped)
**Frequency**: 50 Hz
**Frame ID**: `map`

**Content**: Simplified pose (position + orientation) without velocity

**Use Case**: Lightweight topic for position-only subscribers

#### `/colibri_g1/goal_marker` (visualization_msgs/Marker)
**Frequency**: 1 Hz (only on goal changes)
**Frame ID**: `map`

**Content**:
- **Type**: `SPHERE` (visualization_msgs/Marker.SPHERE = 2)
- **Scale**: 0.3m diameter (goal reach threshold)
- **Color**:
  - Green (RGBA: 0, 1, 0, 0.6) when goal is far (> 0.3m)
  - Blue (RGBA: 0, 0, 1, 0.6) when goal is reached (< 0.3m)
- **Position**: 3D goal position in world frame

**Source**: `env.command_manager.get_command("goal_position")`

#### `/colibri_g1/navigation/goal_pose` (geometry_msgs/PoseStamped)
**Frequency**: On goal update
**Frame ID**: `map`

**Content**: Goal position as PoseStamped for standard ROS2 navigation tools

#### `/colibri_g1/navigation/distance_to_goal` (std_msgs/Float32)
**Frequency**: 10 Hz

**Content**: Euclidean distance to current goal (meters)

**Use Case**: Monitoring, metrics, debugging

#### `/colibri_g1/navigation/status` (std_msgs/String)
**Frequency**: On status change

**Content**: Navigation state machine status
- `"approaching"`: Moving toward goal (distance > 0.3m)
- `"reached"`: Goal reached (distance < 0.3m)
- `"transitioning"`: Smooth interpolation to new goal (1.5s duration)

#### `/clock` (rosgraph_msgs/Clock)
**Frequency**: 50 Hz

**Content**: Simulation time (monotonic, synchronized with Isaac Sim)

**Use Case**: Ensure all ROS2 nodes use simulation time, not wall clock

### Subscribed Topics

#### `/colibri_g1/cmd_vel` (geometry_msgs/Twist)
**Optional Override**: Disabled by default, can be enabled via config

**Content**:
- **linear.x**: Forward velocity command (m/s)
- **linear.y**: Lateral velocity command (m/s)
- **angular.z**: Yaw velocity command (rad/s)

**Behavior**: If enabled, overrides autonomous `GoalDirectedVelocityCommand` with external commands

**Use Case**: Manual teleoperation, testing, debugging

---

## TF Tree Structure

### Static Transforms

```
map (world frame)
 │
 └─ base_link (robot base)
     │
     ├─ imu_link (future: IMU sensor frame)
     │
     ├─ front_camera_link (future: RGB/depth camera)
     │   └─ front_camera_optical_frame
     │
     └─ lidar_link (future: LiDAR sensor frame)
```

### Dynamic Transforms

**map → base_link**:
- **Translation**: Robot position (x, y, z) from `env.scene["robot"].data.root_pos_w`
- **Rotation**: Robot orientation (quaternion) from `env.scene["robot"].data.root_quat_w`
- **Update Rate**: 50 Hz
- **Publisher**: `tf2_ros.TransformBroadcaster`

**Future Sensor Frames**:
- Defined in sensor configuration (Phase 4)
- Static relative to `base_link`

---

## Configuration System

### YAML Configuration (`cfg/ros2_sim.yaml`)

```yaml
# Simulation Settings
num_envs: 1                    # Single robot for sim2sim
freq: 50                       # Control frequency (Hz)
episode_length_s: null         # Infinite (no auto-reset)

# Scene Settings
scene:
  env_spacing: 0.0             # No spacing needed (single robot)
  num_envs: 1
  camera_follow: true          # Camera tracks robot

# ROS2 Settings
ros2:
  namespace: "colibri_g1"      # Topic namespace
  publish_tf: true             # Enable TF broadcasting
  publish_clock: true          # Publish simulation time
  publish_rate: 50             # Hz (for odometry, joint states)
  goal_marker_rate: 1          # Hz (for goal visualization)
  enable_cmd_vel_override: false  # Allow external velocity commands

# Policy Settings
policy:
  checkpoint: "logs/rsl_rl/isaac-colibri-g1-v0/2024-01-15_10-30-00/model_10000.pt"
  device: "cuda"               # or "cpu"
  deterministic: true          # No exploration noise during deployment

# Sensor Settings (Phase 4+)
sensor:
  enable_camera: false         # RGB/depth camera
  enable_lidar: false          # 2D/3D LiDAR
  camera:
    width: 640
    height: 480
    fov: 90                    # degrees
  lidar:
    type: "2d"                 # or "3d"
    range: 10.0                # meters
    resolution: 0.01           # meters

# Environment Settings (reuse existing)
environment:
  use_custom_usd: true
  usd_path: "assets/colivriLab/ColibriBuilding.usd"

# Debug Settings
debug:
  visualize_goals: true        # Show goal markers in Isaac Sim
  print_diagnostics: false     # Print ROS2 publish rates
  record_video: false          # Record simulation video
```

### Hydra Integration

The ROS2 sim2sim uses Hydra for configuration management (consistent with training scripts):

```python
@hydra.main(config_path="../cfg", config_name="ros2_sim", version_base=None)
def run_sim2sim(cfg: DictConfig):
    # Configuration loaded automatically
    # Can override via CLI: python sim2sim/isaac_colibri_g1_ros2.py num_envs=1 debug.print_diagnostics=true
```

---

## Policy Loading & Inference

### Loading Trained Checkpoints

**Checkpoint Structure** (RSL-RL):
```python
checkpoint = torch.load("model_10000.pt")
# checkpoint contains:
#   - "model_state_dict": ActorCritic network weights
#   - "optimizer_state_dict": Optimizer state (not needed for inference)
#   - "iteration": Training iteration number
```

**Loading Process**:
```python
def load_trained_policy(checkpoint_path: str, obs_dim: int, act_dim: int, device: str):
    """Load RSL-RL PPO policy for inference"""
    from rsl_rl.modules import ActorCritic
    from digital_twin_colibri_g1.tasks.manager_based.digital_twin_colibri_g1.agents import ColibriG1PPORunnerCfg

    # Create policy network with same architecture as training
    agent_cfg = ColibriG1PPORunnerCfg()
    policy = ActorCritic(
        num_actor_obs=obs_dim,
        num_critic_obs=obs_dim,
        num_actions=act_dim,
        **agent_cfg.policy
    ).to(device)

    # Load weights
    checkpoint = torch.load(checkpoint_path, map_location=device)
    policy.load_state_dict(checkpoint["model_state_dict"])
    policy.eval()  # Set to evaluation mode (disables dropout, etc.)

    return policy
```

**Observation Dimension**:
- Defined by environment config
- Includes: base velocities (6), projected gravity (3), velocity commands (3), joint positions (29), joint velocities (29), actions (29), goal position (2)
- **Total**: ~101 dimensions (verify from environment config)

**Action Dimension**:
- 29 (joint position targets for G1 humanoid)

### Inference Loop

```python
while simulation_app.is_running():
    with torch.inference_mode():
        # 1. Get observations from environment
        obs_dict = env.get_observations()
        obs = obs_dict["policy"]  # Shape: (1, obs_dim)

        # 2. Run policy inference
        actions = policy.act_inference(obs)  # Shape: (1, 29)

        # 3. Step environment
        env.step(actions)

        # 4. Publish ROS2 data
        ros2_bridge.publish_data()
        rclpy.spin_once(ros2_bridge, timeout_sec=0)

        # 5. Maintain loop rate
        time.sleep(max(0, sim_dt - elapsed_time))
```

**Key Differences from Training**:
- No exploration noise (`deterministic=True`)
- No gradient computation (`torch.inference_mode()`)
- Single environment (`num_envs=1`)
- Infinite episode length (no auto-reset)

---

## ROS2 Bridge Implementation

### RobotDataManager Node

**File**: `ros2/colibri_g1_ros2_bridge.py`

**Inspiration**: `isaac-go2-ros2/ros2/g1_ros2_bridge.py` (basic structure)

**Class Structure**:
```python
class RobotDataManager(Node):
    def __init__(self, env, cfg):
        super().__init__('colibri_g1_ros2_bridge')

        # Store references
        self.env = env
        self.cfg = cfg
        self.robot = env.scene["robot"]

        # Initialize publishers
        self._init_publishers()

        # Initialize subscribers
        self._init_subscribers()

        # Initialize TF broadcaster
        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)

        # State tracking
        self.last_goal_pos = None
        self.last_goal_marker_time = 0

    def _init_publishers(self):
        """Create ROS2 publishers"""
        self.odom_pub = self.create_publisher(
            Odometry, f'{self.cfg.ros2.namespace}/odom', 10
        )
        self.joint_states_pub = self.create_publisher(
            JointState, f'{self.cfg.ros2.namespace}/joint_states', 10
        )
        # ... (more publishers)

    def _init_subscribers(self):
        """Create ROS2 subscribers"""
        if self.cfg.ros2.enable_cmd_vel_override:
            self.cmd_vel_sub = self.create_subscription(
                Twist,
                f'{self.cfg.ros2.namespace}/cmd_vel',
                self._cmd_vel_callback,
                10
            )

    def publish_data(self):
        """Publish all robot data (called every simulation step)"""
        current_time = self.env.sim_time  # Use simulation time

        # Publish high-frequency topics (50 Hz)
        self._publish_odometry(current_time)
        self._publish_joint_states(current_time)
        self._publish_pose(current_time)
        self._publish_transforms(current_time)

        # Publish low-frequency topics (conditionally)
        if self._should_publish_goal_marker(current_time):
            self._publish_goal_marker(current_time)
            self._publish_navigation_metrics(current_time)

    def _publish_odometry(self, current_time):
        """Publish /colibri_g1/odom"""
        msg = Odometry()
        msg.header.stamp = self._to_ros_time(current_time)
        msg.header.frame_id = "map"
        msg.child_frame_id = "base_link"

        # Get robot state
        root_state = self.robot.data.root_state_w[0]  # (13,): pos(3), quat(4), lin_vel(3), ang_vel(3)

        # Position + orientation
        msg.pose.pose.position.x = float(root_state[0])
        msg.pose.pose.position.y = float(root_state[1])
        msg.pose.pose.position.z = float(root_state[2])
        msg.pose.pose.orientation.w = float(root_state[3])
        msg.pose.pose.orientation.x = float(root_state[4])
        msg.pose.pose.orientation.y = float(root_state[5])
        msg.pose.pose.orientation.z = float(root_state[6])

        # Velocities
        msg.twist.twist.linear.x = float(root_state[7])
        msg.twist.twist.linear.y = float(root_state[8])
        msg.twist.twist.linear.z = float(root_state[9])
        msg.twist.twist.angular.x = float(root_state[10])
        msg.twist.twist.angular.y = float(root_state[11])
        msg.twist.twist.angular.z = float(root_state[12])

        self.odom_pub.publish(msg)
```

**Key Implementation Details**:
1. **Time Synchronization**: Use `env.sim_time` (Isaac Sim time), not `time.time()` (wall clock)
2. **Frame Consistency**: All poses in `map` frame, velocities in `base_link` frame
3. **Tensor → Scalar Conversion**: Use `float()` to convert PyTorch tensors to Python floats
4. **Efficient Publishing**: Only publish goal markers when goal changes (not every step)

---

## Environment Configuration Reuse

### Using Existing Play Mode as Base

The sim2sim environment **reuses** the existing `DigitalTwinColibriG1EnvCfg_PLAY` configuration with minimal modifications:

```python
from digital_twin_colibri_g1.tasks.manager_based.digital_twin_colibri_g1 import (
    DigitalTwinColibriG1EnvCfg_PLAY
)

class DigitalTwinColibriG1EnvCfg_ROS2(DigitalTwinColibriG1EnvCfg_PLAY):
    """Sim2sim ROS2 configuration - extends play mode for continuous operation"""

    def __post_init__(self):
        super().__post_init__()

        # Override for sim2sim
        self.scene.num_envs = 1                # Single robot only
        self.episode_length_s = float('inf')   # Never auto-reset

        # Keep existing scene/assets/rewards (no changes needed!)
```

**What We Reuse** (No modifications):
- ✅ ColibriBuilding.usd scene
- ✅ SimpleGoalCommand (autonomous goal generation)
- ✅ GoalDirectedVelocityCommand (velocity always points toward goal)
- ✅ Navigation rewards (goal distance, heading alignment)
- ✅ Locomotion rewards (velocity tracking, joint acceleration, etc.)
- ✅ Observation space (includes goal position)

**What We Change**:
- num_envs: 512 → 1 (single robot)
- episode_length_s: 30s → ∞ (continuous operation)

**Why This Works**:
- Play mode already disables randomization (suitable for deployment)
- All MDP components (commands, rewards, observations) are modular
- Policy checkpoint is compatible (same observation/action space)

---

## Design Decisions & Rationale

### 1. Autonomous Goal Generation (Not External ROS2 Goals)

**Decision**: Keep existing `SimpleGoalCommand` system for Phase 1-3

**Rationale**:
- ✅ Already proven to work (Phase 1-5 complete)
- ✅ No need to rebuild goal management logic
- ✅ ROS2 topics used for **visualization only** (monitoring, not control)
- ✅ Simpler testing (robot navigates autonomously)
- ✅ External goal commands can be added later without breaking existing system

**Future Extension Path**:
- Add subscriber to `/colibri_g1/goal` (geometry_msgs/PoseStamped)
- Add config flag: `use_external_goals: true/false`
- If external goal received, override internal `SimpleGoalCommand`

### 2. Single Robot Mode (num_envs=1)

**Decision**: Sim2sim uses only 1 parallel environment

**Rationale**:
- ✅ Realistic deployment scenario (one robot, one policy)
- ✅ Easier ROS2 topic management (no multi-robot namespacing)
- ✅ Lower GPU memory (important for Docker deployment)
- ✅ Matches real robot deployment constraints

**Contrast with Training**: Training uses 512 parallel envs for sample efficiency, but deployment needs only 1

### 3. Docker-First Development

**Decision**: Build Docker container before native development

**Rationale**:
- ✅ Solves ROS2 Humble installation on Arch Linux
- ✅ Reproducible environment (same setup for all developers)
- ✅ Simplifies Isaac Sim 5.0 + ROS2 dependency management
- ✅ Easy deployment to multiple machines (sim2sim testing)
- ✅ Prepares for cloud deployment (future)

**Trade-off**: Slower iteration vs. more stable environment (Docker wins for ROS2)

### 4. Isaac Sim 5.0 + ROS2 Humble

**Decision**: Target latest Isaac Sim with stable ROS2

**Rationale**:
- ✅ Isaac Sim 5.0 has improved ROS2 OmniGraph nodes (better than 4.5)
- ✅ ROS2 Humble is LTS (Long-Term Support until 2027)
- ✅ Future-proof for sim2real deployment
- ✅ Better documentation and community support

**Migration Path**: Repo was built on Isaac Sim <5.0, so expect minor code updates for OmniGraph changes

### 5. Reuse Existing Scene & Assets

**Decision**: No new USD scenes, use ColibriBuilding.usd

**Rationale**:
- ✅ Policy was trained in this environment (maximum transfer accuracy)
- ✅ No need to rebuild environment assets
- ✅ Faster development (focus on ROS2 bridge, not scene design)
- ✅ Consistent with "play mode" philosophy (visualize trained policy)

**Future Extension**: Can add sensor-rich environments (obstacles, dynamic objects) in Phase 5+

---

## Testing Strategy

### Phase 1: ROS2 Communication

**Test 1**: Topic Publishing
```bash
# Terminal 1: Launch sim2sim
python sim2sim/isaac_colibri_g1_ros2.py

# Terminal 2: Check topics exist
ros2 topic list
# Expected: /colibri_g1/odom, /colibri_g1/joint_states, /colibri_g1/pose, /clock

# Terminal 3: Check frequencies
ros2 topic hz /colibri_g1/odom
# Expected: ~50 Hz

ros2 topic hz /colibri_g1/joint_states
# Expected: ~50 Hz
```

**Test 2**: TF Tree
```bash
ros2 run tf2_ros tf2_echo map base_link
# Expected: Transform updates at 50 Hz with valid position/orientation

ros2 run tf2_tools view_frames
# Expected: Generates PDF with map → base_link tree
```

**Test 3**: Message Content
```bash
ros2 topic echo /colibri_g1/joint_states --once
# Expected: 29 joint names + positions + velocities

ros2 topic echo /colibri_g1/odom --once
# Expected: Valid position, orientation, velocities
```

### Phase 2: Policy Performance

**Test 4**: Navigation Quality
- Launch RViz2 with `rviz/colibri_g1.rviz`
- Observe robot navigating to green goal markers
- Verify goals turn blue when reached
- Confirm smooth locomotion (no falling, natural gait)

**Test 5**: Policy Metrics
```bash
ros2 topic echo /colibri_g1/navigation/distance_to_goal
# Expected: Value decreases as robot approaches goal

ros2 topic echo /colibri_g1/navigation/status
# Expected: "approaching" → "reached" → "transitioning" cycle
```

**Test 6**: Compare to Training Performance
- Measure goal reach rate in sim2sim
- Compare to training logs (expected: similar or better due to deterministic policy)
- Verify episode length is stable (robot doesn't fall)

### Phase 3: Sim2Sim Transfer

**Test 7**: Two Isaac Lab Instances
- Launch first Isaac Lab with ROS2 bridge (publishes state)
- Launch second Isaac Lab as receiver (subscribes to cmd_vel, mimics actions)
- Verify synchronized behavior

**Test 8**: Isaac Lab → Mujoco (Optional)
- Export policy to ONNX/TorchScript
- Load in Mujoco with ROS2 bridge
- Send cmd_vel from Isaac Lab → Mujoco executes
- Compare trajectories (visual similarity test)

### Phase 4: Stress Testing

**Test 9**: Long-Duration Stability
- Run for 1+ hour continuous operation
- Monitor for memory leaks, crashes, performance degradation
- Check ROS2 queue saturation (rqt_graph)

**Test 10**: Real-Time Factor (RTF)
- Measure sim_dt / wall_clock_dt
- Target: RTF ≥ 0.8 (80% real-time)
- If RTF < 0.5, reduce sensor load or num_envs

---

## Performance Considerations

### GPU Memory Usage

**Estimated Memory**:
- Isaac Sim GUI: ~2-3 GB
- Single G1 robot: ~500 MB
- Policy network: ~50 MB
- USD scene: ~200 MB
- **Total**: ~3-4 GB (should fit on most modern GPUs)

**Optimization Tips**:
- Use `--headless` mode if GUI not needed (saves ~1 GB)
- Reduce scene complexity if GPU limited
- Use CPU for policy inference if GPU maxed (slower, but possible)

### Real-Time Factor (RTF)

**Target**: RTF ≥ 0.8 (simulation runs at least 80% of real-time)

**Factors Affecting RTF**:
- Simulation time step (`sim.dt = 0.005s` typical)
- Decimation (`decimation = 4` → control at 50 Hz)
- Rendering interval (`render_interval = decimation`)
- ROS2 publishing overhead (~1-2ms per publish cycle)

**Optimization**:
```python
# Increase decimation (lower control frequency)
env_cfg.decimation = 8  # 25 Hz instead of 50 Hz

# Reduce rendering frequency
env_cfg.sim.render_interval = 16  # Render every 16 sim steps

# Disable expensive sensors
cfg.sensor.enable_camera = False
cfg.sensor.enable_lidar = False
```

### ROS2 Message Latency

**Typical Latencies** (localhost):
- Odometry: <1 ms (small message, high priority)
- Joint states: <2 ms (larger message, 29 DOF)
- Goal marker: <5 ms (infrequent, low priority)

**Network Deployment** (Docker → Host):
- Add ~5-10 ms latency (Docker bridge network)
- Use `network_mode: host` in docker-compose to minimize latency

---

## Future Extensions

### Phase 4: Sensor Integration

**Cameras** (RGB + Depth):
- Add `front_camera` to scene config
- Publish `sensor_msgs/Image` (RGB, depth)
- Publish `sensor_msgs/CameraInfo` (intrinsics)
- Add TF: `base_link` → `front_camera_link`

**LiDAR** (2D or 3D):
- Add RTX LiDAR sensor
- Publish `sensor_msgs/PointCloud2` or `sensor_msgs/LaserScan`
- Add TF: `base_link` → `lidar_link`

**References**: `isaac-go2-ros2/g1/g1_sensors.py`

### Phase 5: External Goal Commands

**Subscribe to Navigation Goals**:
```python
# In RobotDataManager.__init__
self.goal_sub = self.create_subscription(
    PoseStamped,
    f'{self.cfg.ros2.namespace}/goal',
    self._goal_callback,
    10
)

def _goal_callback(self, msg: PoseStamped):
    """Override internal goal with external command"""
    if self.cfg.ros2.enable_external_goals:
        # Convert PoseStamped to 2D goal position
        goal_x = msg.pose.position.x
        goal_y = msg.pose.position.y

        # Update command manager
        self.env.command_manager._commands["goal_position"].goal_pos[:] = torch.tensor([goal_x, goal_y])
```

**Integration with RViz2**:
- Use "2D Nav Goal" tool in RViz2
- Publishes to `/colibri_g1/goal`
- Robot immediately changes trajectory toward new goal

### Phase 6: Hierarchical Navigation with ROS2

**Two-Policy Setup**:
1. **Low-level**: Frozen locomotion policy (joint control)
2. **High-level**: Navigation policy (velocity commands) → **published via ROS2**

**ROS2 Topics**:
- `/colibri_g1/high_level/cmd_vel` (nav policy output)
- `/colibri_g1/low_level/joint_commands` (locomotion policy output)

**Use Case**: Decouple navigation learning from locomotion (Phase 6 in PHASES.md)

### Phase 7: Sim2Real Deployment

**Real Robot Bridge** (unitree_sdk2):
- Replace Isaac Lab env with real robot API
- Subscribe to same `/colibri_g1/cmd_vel` topic
- Publish same `/colibri_g1/odom` topic
- **Policy inference unchanged** (same checkpoint, same ROS2 interface)

**Safety Layer**:
- Add velocity limits
- Emergency stop subscriber
- Collision detection
- Battery monitoring

**References**:
- `isaac-go2-ros2/` (similar deployment pattern)
- `unitree_rl_lab/deploy/robots/g1/` (C++ sim2real)

---

## References

### Isaac Sim ROS2 Documentation
- [Isaac Sim 5.0 ROS2 Integration](https://docs.isaacsim.omniverse.nvidia.com/latest/ros2_tutorials/ros2_landing_page.html)
- [OmniGraph ROS2 Bridge](https://docs.isaacsim.omniverse.nvidia.com/latest/ros2_tutorials/tutorial_ros2_omnigraph.html)
- [ROS2 Messages](https://docs.isaacsim.omniverse.nvidia.com/latest/ros2_tutorials/tutorial_ros2_messages.html)

### Related Implementations
- `isaac-go2-ros2/ros2/g1_ros2_bridge.py` (basic ROS2 bridge structure)
- `isaac-go2-ros2/ros2/go2_ros2_bridge.py` (sensor integration example)
- `IsaacLab/source/isaaclab_tasks/manager_based/navigation/` (hierarchical navigation)

### ROS2 Packages Used
- `rclpy`: Python ROS2 client library
- `tf2_ros`: Transform broadcasting
- `geometry_msgs`: Pose, Twist messages
- `nav_msgs`: Odometry
- `sensor_msgs`: JointState, Image, PointCloud2
- `visualization_msgs`: Marker (goal visualization)
- `std_msgs`: Float32, String (metrics)

---

## Summary

The Sim2Sim ROS2 integration provides:

1. **Full State Observability**: Odometry, joint states, goal positions published at 50 Hz
2. **Autonomous Navigation**: Reuses proven goal-directed system from Phase 1-5
3. **Visualization**: RViz2 support with goal markers, TF tree, robot model
4. **Extensibility**: Clean architecture for adding sensors, external goals, sim2real deployment
5. **Docker Deployment**: Reproducible environment for development and testing
6. **Future-Proof**: Built on Isaac Sim 5.0 and ROS2 Humble (LTS)

**Next Steps**: See [DOCKER_SETUP.md](DOCKER_SETUP.md) for containerization guide and [PHASES.md](PHASES.md) for Phase 6 implementation details.
