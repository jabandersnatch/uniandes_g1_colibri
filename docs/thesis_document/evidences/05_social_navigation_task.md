# Social Navigation Task Evidence

## 5. Social Navigation with LiDAR and Obstacle Avoidance

### 5.1 Task Overview

The social navigation task extends the base locomotion task with:
- RayCaster LiDAR sensor for 360-degree perception
- Moving cylinder obstacles (human-sized)
- LiDAR-based observations for the policy
- Collision avoidance rewards

**File:** `source/.../social_nav_env_cfg.py` (~419 lines)

### 5.2 Configuration Classes

```python
@configclass
class LidarObservationCfg:
    """Configuration for LiDAR-based observations."""
    num_sectors: int = 16        # 360 / 16 = 22.5 per sector
    max_range: float = 10.0      # Maximum detection range
    min_height: float = 0.2      # Above ground
    max_height: float = 2.0      # Below ceiling

@configclass
class ObstacleManagerCfg:
    """Configuration for moving cylinder obstacles."""
    num_cylinders: int = 3
    cylinder_radius: float = 0.3  # Human body width
    cylinder_height: float = 1.8  # Human height
    obstacle_color: tuple = (1.0, 0.5, 0.0)  # Orange

    # Movement parameters
    move_speed_min: float = 0.3  # m/s
    move_speed_max: float = 0.5  # m/s
    waypoint_reach_threshold: float = 0.5

@configclass
class SocialNavRewardsCfg:
    """Configuration for social navigation rewards."""
    human_proximity_weight: float = -0.5
    human_proximity_threshold: float = 1.5  # Social distance
    personal_space_weight: float = -2.0
    personal_space_threshold: float = 0.8   # Personal space
    smooth_trajectory_weight: float = 0.1
```

### 5.3 Environment Configuration

```python
@configclass
class DigitalTwinColibriG1SocialNavEnvCfg(DigitalTwinColibriG1EnvCfg):
    """G1 Social Navigation: LiDAR + Cylinder obstacles + Avoidance."""

    lidar_obs: LidarObservationCfg = LidarObservationCfg()
    obstacles: ObstacleManagerCfg = ObstacleManagerCfg()
    social_rewards: SocialNavRewardsCfg = SocialNavRewardsCfg()

    def __post_init__(self):
        super().__post_init__()

        # Reduced environments for complex task
        self.scene.num_envs = 128
```

### 5.4 RayCaster LiDAR Sensor

```python
# RayCaster LiDAR sensor mounted on torso
self.scene.lidar = RayCasterCfg(
    prim_path="{ENV_REGEX_NS}/Robot/torso_link",
    offset=RayCasterCfg.OffsetCfg(pos=(0.0, 0.0, 0.1)),

    pattern_cfg=patterns.LidarPatternCfg(
        channels=32,                         # Vertical channels
        vertical_fov_range=(-30.0, 30.0),    # Degrees
        horizontal_fov_range=(0.0, 360.0),   # Full 360 surround
        horizontal_res=2.0,                  # 2 resolution = 180 rays/channel
    ),

    max_distance=10.0,
    drift_range=(0.0, 0.0),  # No sensor drift

    # Mesh prim for raycasting
    mesh_prim_paths=["/World/ground"],

    debug_vis=False,  # Disable for training
)
```

**Sensor Specifications:**
- 32 vertical channels
- 360-degree horizontal coverage
- 2-degree horizontal resolution (180 rays per channel)
- 10m maximum range
- Mounted on torso_link for stability

### 5.5 Cylinder Obstacle Spawning

```python
# Spawn multiple cylinders per environment as dynamic obstacles
for i in range(self.obstacles.num_cylinders):
    cylinder_cfg = RigidObjectCfg(
        prim_path=f"{{ENV_REGEX_NS}}/Obstacle_{i}",

        spawn=CylinderCfg(
            radius=self.obstacles.cylinder_radius,   # 0.3m
            height=self.obstacles.cylinder_height,   # 1.8m

            visual_material=PreviewSurfaceCfg(
                diffuse_color=self.obstacles.obstacle_color,  # Orange
                metallic=0.2,
                roughness=0.8,
            ),

            # CRITICAL: Dynamic rigid body (kinematic_enabled=False)
            # Fixes visual update bug in Isaac Sim 4.5/5.0
            rigid_props=RigidBodyPropertiesCfg(
                rigid_body_enabled=True,
                kinematic_enabled=False,  # Dynamic for visual updates
                disable_gravity=True,      # Keep at floor height
                linear_damping=15.0,       # Predictable movement
                angular_damping=15.0,      # Prevent rotation
                max_linear_velocity=1.0,   # Cap speed
            ),
        ),

        init_state=RigidObjectCfg.InitialStateCfg(
            pos=(0.0, 0.0, self.obstacles.spawn_height),  # 1.2m (Colibri floor)
        ),
    )

    setattr(self.scene, f"obstacle_{i}", cylinder_cfg)
```

**Obstacle Specifications:**
- Human-sized cylinders (0.3m radius, 1.8m height)
- Orange color for visibility
- Dynamic rigid bodies with high damping
- Gravity disabled to maintain floor height

### 5.6 Cylinder Movement System (Events)

**File:** `source/.../mdp/events.py` (~162 lines)

```python
def update_cylinder_obstacles(
    env: ManagerBasedEnv,
    env_ids: torch.Tensor,
    obstacle_cfg_name: str = "obstacles",
):
    """Update cylinder positions using random waypoint navigation.

    Called every physics step (50 Hz) to move obstacles autonomously.
    """
    cfg = getattr(env.cfg, obstacle_cfg_name)

    # Initialize waypoint buffers on first call
    if not hasattr(env, "_obstacle_waypoints"):
        env._obstacle_waypoints = torch.zeros(
            (env.num_envs, cfg.num_cylinders, 3), device=env.device
        )
        env._obstacle_speeds = (
            torch.rand((env.num_envs, cfg.num_cylinders), device=env.device)
            * (cfg.move_speed_max - cfg.move_speed_min)
            + cfg.move_speed_min
        )
        _sample_waypoints(env, cfg, torch.arange(env.num_envs, device=env.device))

    dt = env.step_dt

    for i in range(cfg.num_cylinders):
        obstacle = env.scene[f"obstacle_{i}"]
        pos = obstacle.data.root_pos_w[env_ids].clone()

        # Check waypoint reached
        dist = torch.norm(pos[:, :2] - env._obstacle_waypoints[env_ids, i, :2], dim=-1)
        reached_mask = dist < cfg.waypoint_reach_threshold

        if reached_mask.any():
            _sample_waypoints(env, cfg, env_ids[reached_mask], cylinder_idx=i)

        # Compute direction and update position
        direction = env._obstacle_waypoints[env_ids, i, :2] - pos[:, :2]
        direction = direction / torch.norm(direction, dim=-1, keepdim=True).clamp(min=1e-6)

        speed = env._obstacle_speeds[env_ids, i].unsqueeze(1)
        pos[:, :2] += direction * speed * dt
        pos[:, 2] = cfg.spawn_height

        # Write to simulation
        root_state = obstacle.data.root_state_w[env_ids].clone()
        root_state[:, :3] = pos
        obstacle.write_root_pose_to_sim(root_state[:, :7], env_ids=env_ids)
```

**Movement Behavior:**
- Random waypoint navigation within spawn area
- Speed varies between 0.3-0.5 m/s (slow walk)
- Waypoint resampled when reached (0.5m threshold)
- Updated every physics step (50 Hz)

**Event Registration:**
```python
self.events.update_obstacles = EventTermCfg(
    func=mdp.update_cylinder_obstacles,
    mode="interval",
    interval_range_s=(0.02, 0.02),  # 50 Hz
    params={"obstacle_cfg_name": "obstacles"},
)
```

### 5.7 LiDAR Observation Function

**File:** `source/.../mdp/observations.py` (~91 lines)

```python
def lidar_sector_distances(
    env: ManagerBasedRLEnv,
    num_sectors: int = 16,
    max_range: float = 10.0,
) -> torch.Tensor:
    """Convert LiDAR rays to angular sectors with minimum distance.

    Divides 360 FoV into num_sectors angular bins.
    Returns minimum distance per sector, normalized to [0, 1].
    """
    sensor: RayCaster = env.scene.sensors["lidar"]

    ray_hits_w = sensor.data.ray_hits_w      # (num_envs, num_rays, 3)
    sensor_pos_w = sensor.data.pos_w         # (num_envs, 3)
    sensor_quat_w = sensor.data.quat_w       # (num_envs, 4)

    # Compute distances
    distances = torch.norm(ray_hits_w - sensor_pos_w.unsqueeze(1), dim=-1)

    # Transform to sensor body frame
    ray_hits_relative = ray_hits_w - sensor_pos_w.unsqueeze(1)
    ray_hits_b = quat_rotate_inverse(sensor_quat_w.unsqueeze(1), ray_hits_relative)

    # Compute angles and map to sectors
    angles = torch.atan2(ray_hits_b[..., 1], ray_hits_b[..., 0])
    angles = (angles + torch.pi) % (2 * torch.pi)  # [0, 2pi]

    sector_size = 2 * torch.pi / num_sectors
    sector_indices = (angles / sector_size).long() % num_sectors

    # Find minimum distance per sector
    sector_distances = torch.full((env.num_envs, num_sectors), max_range, device=env.device)

    for sector_idx in range(num_sectors):
        sector_mask = (sector_indices == sector_idx)
        for env_idx in range(env.num_envs):
            env_sector_rays = distances[env_idx, sector_mask[env_idx]]
            if env_sector_rays.numel() > 0:
                sector_distances[env_idx, sector_idx] = env_sector_rays.min()

    return sector_distances / max_range  # Normalize to [0, 1]
```

**Observation Output:**
- Shape: `(num_envs, 16)` - one value per sector
- Range: `[0, 1]` - normalized distance
- 0.0 = obstacle at sensor
- 1.0 = no obstacle within max_range

### 5.8 Collision Avoidance Rewards

**File:** `source/.../mdp/rewards.py`

```python
def lidar_obstacle_proximity(
    env: ManagerBasedRLEnv,
    threshold: float = 1.5,
    std: float = 0.5,
) -> torch.Tensor:
    """Penalize obstacles within threshold using exponential kernel.

    Formula: exp(-(distance / std)^2) when distance < threshold, else 0
    """
    sensor = env.scene.sensors["lidar"]
    ray_hits_w = sensor.data.ray_hits_w
    sensor_pos_w = sensor.data.pos_w

    distances = torch.norm(ray_hits_w - sensor_pos_w.unsqueeze(1), dim=-1)
    min_distance = distances.min(dim=-1).values

    # Exponential penalty (closer = higher penalty)
    penalty = torch.exp(-torch.square(min_distance / std))

    # Only apply within threshold
    penalty = torch.where(min_distance < threshold, penalty, torch.zeros_like(penalty))

    return penalty
```

**Reward Configuration:**
```python
# Warning-level proximity (1.5m)
self.rewards.obstacle_proximity_warning = RewTerm(
    func=mdp.lidar_obstacle_proximity,
    weight=-0.5,  # Gentle penalty
    params={"threshold": 1.5, "std": 0.5},
)

# Critical proximity (0.8m - personal space)
self.rewards.obstacle_proximity_critical = RewTerm(
    func=mdp.lidar_obstacle_proximity,
    weight=-2.0,  # Strong penalty
    params={"threshold": 0.8, "std": 0.3},
)

# Smooth trajectory reward
self.rewards.smooth_trajectory = RewTerm(
    func=mdp.smooth_trajectory_reward,
    weight=0.1,
)
```

### 5.9 Smooth Trajectory Reward

```python
def smooth_trajectory_reward(env: ManagerBasedRLEnv) -> torch.Tensor:
    """Reward smooth, non-jerky movements.

    Penalizes rapid action changes for comfortable robot behavior.
    """
    actions = env.action_manager.action
    prev_actions = env.action_manager.prev_action

    action_diff = torch.sum(torch.abs(actions - prev_actions), dim=1)
    smoothness = torch.exp(-0.1 * action_diff)

    return smoothness
```

### 5.10 PPO Configuration for Social Navigation

**File:** `source/.../agents/rsl_rl_ppo_cfg.py`

```python
@configclass
class ColibriG1SocialNavPPORunnerCfg(G1FlatPPORunnerCfg):
    """PPO config for social navigation task."""

    def __post_init__(self):
        super().__post_init__()

        self.experiment_name = "colibri_g1_social_nav"

        # Larger network for LiDAR processing
        self.policy.actor_hidden_dims = [512, 512, 256, 128]
        self.policy.critic_hidden_dims = [512, 512, 256, 128]

        # Extended training
        self.max_iterations = 3000
        self.algorithm.learning_rate = 5e-4
        self.save_interval = 100

        # Higher entropy for exploration
        self.algorithm.entropy_coef = 0.01
        self.algorithm.clip_param = 0.2
```

### 5.11 Observation Space Extension

**Base + Social Nav Observations:**

| Component | Dimensions | Source |
|-----------|------------|--------|
| Base observations | ~125 | Inherited from base task |
| LiDAR sectors | 16 | Custom `lidar_sector_distances()` |
| **Total** | **~141** | |

```python
# Add LiDAR observations to policy
self.observations.policy.lidar_sectors = ObsTerm(
    func=mdp.lidar_sector_distances,
    params={
        "num_sectors": self.lidar_obs.num_sectors,  # 16
        "max_range": self.lidar_obs.max_range,      # 10.0
    },
)
```

### 5.12 Training Commands

```bash
# Train social navigation
python scripts/rsl_rl/train.py --task=Isaac-Colibri-G1-SocialNav-v0 \
    --num_envs 128 --headless --max_iterations 3000

# Evaluate with visualization
python scripts/rsl_rl/play.py --task=Isaac-Colibri-G1-SocialNav-Play-v0 \
    --num_envs 4 --real-time
```

### 5.13 Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| RayCaster LiDAR | Complete | 32-channel, 360-degree |
| Cylinder Obstacles | Complete | 3 per env, random movement |
| LiDAR Observations | Complete | 16-sector representation |
| `lidar_obstacle_proximity()` | Complete | Uses actual LiDAR data |
| `smooth_trajectory_reward()` | Complete | Action difference penalty |
| `human_proximity_penalty()` | Placeholder | Returns zeros |
| `personal_space_violation()` | Placeholder | Returns zeros |

### 5.14 Known Issues and Future Work

1. **Visual Update Bug**: Isaac Sim 4.5/5.0 kinematic bodies don't update visually. Solution: Use dynamic bodies with `disable_gravity=True`.

2. **Placeholder Rewards**: `human_proximity_penalty()` and `personal_space_violation()` return dummy values. These were designed for animated humans (IRA) which proved incompatible with Isaac Lab.

3. **IRA Incompatibility**: The `omni.anim.people` extension (IRA) doesn't work with Isaac Lab's parallel environment architecture. Cylinder obstacles were implemented as the replacement.

4. **Observation Efficiency**: The sector-based LiDAR observation uses nested loops. Could be optimized with vectorized scatter operations.
