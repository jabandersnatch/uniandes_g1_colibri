# ROS2 Sim2Sim Integration Evidence

## 3. Sim2Sim ROS2 Bridge Implementation

### 3.1 Architecture Overview

The sim2sim implementation follows a **unified single-node ROS2 architecture**, merging publishers and subscribers into one node for simplicity and reliability.

**Design Pattern:** Single ROS2 node combining all functionality
**Reference Implementation:** `isaac-go2-ros2` (CLeARoboticsLab)
**Target Compatibility:** Unitree G1 real robot

### 3.2 ROS2 Bridge Implementation

**File:** `ros2/colibri_g1_ros2_bridge.py` (~675 lines)

```python
class ColibriG1RobotDataManager(Node):
    """Unified ROS2 node for Colibri G1 sim2sim integration.

    Combines publishers and subscribers into a single node, eliminating
    threading complexity while maintaining full functionality.

    Publishes:
        - /lowstate (unitree_hg/LowState): Motor states + IMU @ 50 Hz
        - /utlidar/cloud (sensor_msgs/PointCloud2): LiDAR @ 15 Hz
        - /ground_truth/pose, /twist: Ground truth @ 50 Hz
        - /colibri_g1/goal_marker: Goal visualization @ 1 Hz
        - Navigation metrics and camera images

    Subscribes:
        - /lowcmd (unitree_hg/LowCmd): Motor commands
        - /cmd_vel (geometry_msgs/Twist): Velocity commands
    """
```

### 3.3 Published Topics (Developed from Scratch)

#### 3.3.1 Unitree-Pattern Topics (Real Robot Compatible)

| Topic | Message Type | Rate | Description |
|-------|--------------|------|-------------|
| `/lowstate` | `unitree_hg/LowState` | 50 Hz | 35 motor states + IMU |
| `/utlidar/cloud` | `sensor_msgs/PointCloud2` | 15 Hz | RTX LiDAR point cloud |
| `/ground_truth/pose` | `geometry_msgs/PoseStamped` | 50 Hz | World pose |
| `/ground_truth/twist` | `geometry_msgs/TwistStamped` | 50 Hz | World twist |
| `/clock` | `rosgraph_msgs/Clock` | Sim rate | Simulation time (OmniGraph) |
| `/tf` | `tf2_msgs/TFMessage` | 50 Hz | Transform tree |

#### 3.3.2 Custom Navigation Topics

| Topic | Message Type | Rate | Description |
|-------|--------------|------|-------------|
| `/colibri_g1/goal_marker` | `visualization_msgs/Marker` | 1 Hz | Goal visualization (color-coded) |
| `/colibri_g1/navigation/goal_pose` | `geometry_msgs/PoseStamped` | 1 Hz | Goal position |
| `/colibri_g1/navigation/distance_to_goal` | `std_msgs/Float32` | 1 Hz | Distance metric |
| `/colibri_g1/navigation/status` | `std_msgs/String` | 1 Hz | "approaching" or "reached" |
| `/front_cam/color_image` | `sensor_msgs/Image` | 50 Hz | RGB camera |
| `/front_cam/depth_image` | `sensor_msgs/Image` | 50 Hz | Depth camera |

### 3.4 Key Implementation Components

#### 3.4.1 OmniGraph Clock Publisher

```python
def _create_ros_time_graph(self):
    """Create OmniGraph for publishing /clock with simulation time."""
    keys = og.Controller.Keys
    og.Controller.edit(
        {"graph_path": "/ClockActionGraph", "evaluator_name": "execution"},
        {
            keys.CREATE_NODES: [
                ("ReadSimTime", "isaacsim.core.nodes.IsaacReadSimulationTime"),
                ("OnPlaybackTick", "omni.graph.action.OnPlaybackTick"),
                ("PublishClock", "isaacsim.ros2.bridge.ROS2PublishClock"),
            ],
            keys.CONNECT: [
                ("OnPlaybackTick.outputs:tick", "PublishClock.inputs:execIn"),
                ("ReadSimTime.outputs:simulationTime", "PublishClock.inputs:timeStamp"),
            ],
            keys.SET_VALUES: [
                ("PublishClock.inputs:topicName", "/clock"),
            ],
        },
    )
```

#### 3.4.2 Unitree LowState Publishing

```python
def _publish_lowstate(self, robot_data):
    """Publish /lowstate with motor states and IMU data.

    Matches the real G1 robot's /lowstate topic format.
    """
    msg = LowState()

    # Version and mode
    msg.version = [0, 0]
    msg.mode_pr = 0  # PR mode (ankle)
    msg.mode_machine = 0
    msg.tick = self.clock_msg.clock.sec * 1000 + ...

    # IMU State
    root_state = robot_data.root_state_w[0]
    quat = root_state[3:7]
    msg.imu_state.quaternion[0] = float(quat[0].item())  # w
    msg.imu_state.quaternion[1] = float(quat[1].item())  # x
    msg.imu_state.quaternion[2] = float(quat[2].item())  # y
    msg.imu_state.quaternion[3] = float(quat[3].item())  # z

    # Gyroscope (angular velocity)
    ang_vel = root_state[10:13]
    msg.imu_state.gyroscope[0] = float(ang_vel[0].item())
    ...

    # Motor States (29 active DOFs, padded to 35)
    joint_pos = robot_data.joint_pos[0]
    joint_vel = robot_data.joint_vel[0]

    for i in range(G1_NUM_MOTORS):  # 35
        motor = MotorState()
        if i < len(joint_pos):
            motor.mode = 1  # Enabled
            motor.q = float(joint_pos[i].item())
            motor.dq = float(joint_vel[i].item())
            ...
        msg.motor_state[i] = motor

    self.lowstate_pub.publish(msg)
```

#### 3.4.3 LiDAR Point Cloud Publishing

```python
def _publish_lidar(self):
    """Publish /utlidar/cloud point cloud (Unitree naming convention)."""
    lidar_data = self.lidar_annotators[0].get_data()
    points = lidar_data["data"].reshape(-1, 3)

    # Filter by distance
    distances = np.linalg.norm(points, axis=1)
    valid_mask = (distances >= min_range) & (distances <= max_range)
    filtered_points = points[valid_mask]

    # Create PointCloud2 message
    fields = [
        PointField(name="x", offset=0, datatype=PointField.FLOAT32, count=1),
        PointField(name="y", offset=4, datatype=PointField.FLOAT32, count=1),
        PointField(name="z", offset=8, datatype=PointField.FLOAT32, count=1),
    ]

    msg = point_cloud2.create_cloud(header, fields, filtered_points)
    self.lidar_pub.publish(msg)
```

#### 3.4.4 Goal Marker with Color Change

```python
def _publish_goal_marker(self, robot_data, env, current_time):
    """Publish goal marker with color indicating reached status."""
    goal_pos_w = goal_cmd_term.goal_pos_w[0]
    distance = compute_euclidean_distance(robot_pos[:2], goal_pos_w[:2])

    marker = Marker()
    marker.type = Marker.SPHERE
    marker.pose.position = torch_to_ros_point(goal_pos_w)
    marker.scale.x = marker.scale.y = marker.scale.z = 0.3

    if distance > 0.3:
        marker.color.r, marker.color.g, marker.color.b = 0.0, 1.0, 0.0  # Green
    else:
        marker.color.r, marker.color.g, marker.color.b = 0.0, 0.0, 1.0  # Blue

    self.goal_marker_pub.publish(marker)
```

### 3.5 Sim2Sim Entry Point

**File:** `sim2sim/isaac_colibri_g1_ros2.py` (~235 lines)

```python
@hydra.main(config_path=FILE_PATH, config_name="ros2_sim", version_base=None)
def run_sim2sim(cfg):
    """Run sim2sim with ROS2 bridge."""

    # Environment setup
    env_cfg = DigitalTwinColibriG1EnvCfg_PLAY()
    env_cfg.scene.num_envs = cfg.num_envs  # Single robot
    env_cfg.episode_length_s = 10000.0  # Continuous operation

    env = ManagerBasedRLEnv(cfg=env_cfg)

    # Initialize sensors
    sensor_manager = SensorManager(cfg.num_envs)
    if cfg.sensor.enable_lidar:
        lidar_annotators = sensor_manager.add_rtx_lidar(cfg)
    if cfg.sensor.enable_camera:
        cameras = sensor_manager.add_camera(cfg)

    # Load trained policy
    policy = load_trained_policy(cfg.policy.checkpoint, env, cfg.policy.device)

    # Initialize ROS2
    rclpy.init()
    ros2_manager = ColibriG1RobotDataManager(env, cfg, lidar_annotators, cameras)

    # Simulation loop
    obs = env.observation_manager.compute()
    while simulation_app.is_running():
        with torch.inference_mode():
            actions = policy_inference(policy, obs, cfg.policy.deterministic)
            obs, _, _, _, _ = env.step(actions)
            ros2_manager.publish_data()
            rclpy.spin_once(ros2_manager, timeout_sec=0)
```

### 3.6 Policy Loading

```python
def load_trained_policy(checkpoint_path: str, env, device: str = "cuda"):
    """Load trained RSL-RL policy for inference."""
    from rsl_rl.runners import OnPolicyRunner
    from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper

    # Create agent configuration
    agent_cfg = ColibriG1PPORunnerCfg()
    agent_cfg.device = device

    # Wrap environment for RSL-RL
    wrapped_env = RslRlVecEnvWrapper(env)

    # Create runner and load checkpoint
    runner = OnPolicyRunner(wrapped_env, agent_cfg.to_dict(), log_dir=None, device=device)
    runner.load(checkpoint_path)

    # Get inference policy
    return runner.get_inference_policy(device=device)
```

### 3.7 Sensor Manager Implementation

**File:** `sensors/colibri_g1_sensors.py` (~250 lines)

```python
class SensorManager:
    """Manages sensors for the Colibri G1 humanoid robot."""

    def add_rtx_lidar(self, cfg) -> list:
        """Add RTX LiDAR sensor to G1 robot.

        Config: Hesai_XT32_SD10 (32-channel, 10Hz rotation)
        Mount: torso_link with [0.2, 0, 0.4] offset
        """
        for env_idx in range(self.num_envs):
            _, sensor = omni.kit.commands.execute(
                "IsaacSensorCreateRtxLidar",
                path="/lidar",
                parent=f"/World/envs/env_{env_idx}/Robot/{parent_link}",
                config=config_name,
                translation=tuple(translation),
                orientation=Gf.Quatd(*orientation),
            )

            annotator = rep.AnnotatorRegistry.get_annotator(
                "RtxSensorCpuIsaacCreateRTXLidarScanBuffer"
            )
            hydra_texture = rep.create.render_product(sensor.GetPath(), [1, 1])
            annotator.attach(hydra_texture.path)
            self.lidar_annotators.append(annotator)

        return self.lidar_annotators

    def add_camera(self, cfg) -> list:
        """Add RGB/Depth camera to G1 robot."""
        from isaacsim.sensors.camera import Camera

        for env_idx in range(self.num_envs):
            camera = Camera(
                prim_path=f"/World/envs/env_{env_idx}/Robot/{parent_link}/{frame_id}",
                translation=np.array(translation),
                frequency=freq,
                resolution=(width, height),
            )
            camera.initialize()
            camera.set_focal_length(1.5)
            self.cameras.append(camera)

        return self.cameras
```

### 3.8 Configuration System

**File:** `cfg/ros2_sim.yaml` (~131 lines)

```yaml
# Simulation Settings
num_envs: 1
freq: 50

# ROS2 Settings
ros2:
  namespace: "colibri_g1"
  use_unitree_topics: true
  lowstate_rate: 50
  control_mode: "lowcmd"
  publish_tf: true
  publish_clock: true

# Policy Settings
policy:
  checkpoint: "logs/rsl_rl/g1_flat/2025-11-11_10-29-02/model_900.pt"
  device: "cuda"
  deterministic: true

# Sensor Settings
sensor:
  enable_camera: true
  enable_lidar: true

  camera:
    width: 640
    height: 480
    frame_id: "front_cam"
    parent_link: "torso_link"

  lidar:
    config: "Hesai_XT32_SD10"
    parent_link: "torso_link"
    frame_id: "lidar_link"
    publish_rate: 15
```

### 3.9 TF Tree Structure

```
map
 └── base_link (dynamic, from robot root state)
      ├── lidar_link (static transform from config)
      └── front_cam (static transform from config)
```

### 3.10 Subscriber Callbacks

```python
def _lowcmd_callback(self, msg: LowCmd):
    """Handle motor-level commands from /lowcmd."""
    for i in range(min(G1_ACTIVE_DOFS, G1_NUM_MOTORS)):
        self.joint_targets[i] = msg.motor_cmd[i].q
        self.stiffness[i] = msg.motor_cmd[i].kp
        self.damping[i] = msg.motor_cmd[i].kd
    self.use_external_control = True

def _cmd_vel_callback(self, msg: Twist):
    """Handle velocity commands from /cmd_vel."""
    self.cmd_vel_linear[0] = msg.linear.x
    self.cmd_vel_linear[1] = msg.linear.y
    self.cmd_vel_angular[2] = msg.angular.z
    self.use_cmd_vel = True
```

### 3.11 Key Design Decisions

1. **Unified Single-Node Architecture**: Avoids threading complexity of separate pub/sub nodes
2. **Unitree Topic Patterns**: `/lowstate`, `/lowcmd`, `/utlidar/cloud` for real robot compatibility
3. **OmniGraph for Clock**: Uses Isaac Sim's native graph for accurate simulation time
4. **Rate-Limited Publishing**: LiDAR at 15 Hz, markers at 1 Hz to reduce bandwidth
5. **Static TF for Sensors**: Sensors have fixed transforms relative to base_link
6. **CycloneDDS Middleware**: Required for Unitree robot communication
