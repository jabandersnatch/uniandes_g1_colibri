# Copyright (c) 2022-2025, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
PPO training configuration for Colibri G1 Digital Twin.

This configuration inherits from G1's proven PPO settings and allows
for customization specific to the Colibri environment if needed.
"""

from isaaclab.utils import configclass

# Import G1's proven PPO configuration
from isaaclab_tasks.manager_based.locomotion.velocity.config.g1.agents.rsl_rl_ppo_cfg import (
    G1FlatPPORunnerCfg,
)


@configclass
class ColibriG1PPORunnerCfg(G1FlatPPORunnerCfg):
    """
    PPO runner configuration for Colibri G1 task.

    Inherits from G1's flat terrain PPO config and customizes for Colibri.
    """

    def __post_init__(self):
        super().__post_init__()

        # Customize experiment name
        self.experiment_name = "colibri_g1_digital_twin"

        # ============================================
        # OPTIONAL CUSTOMIZATIONS
        # ============================================

        # You can override any hyperparameters here if needed
        # For example:

        # Learning rate
        # self.algorithm.learning_rate = 1e-4

        # Network architecture
        # self.policy.actor_hidden_dims = [512, 256, 128]
        # self.policy.critic_hidden_dims = [512, 256, 128]

        # Training iterations
        # self.max_iterations = 2000

        # Save interval
        # self.save_interval = 100


# For backward compatibility, you can keep the original name
PPORunnerCfg = ColibriG1PPORunnerCfg


@configclass
class ColibriG1SocialNavPPORunnerCfg(G1FlatPPORunnerCfg):
    """
    PPO runner configuration for Colibri G1 Social Navigation task.

    This configuration extends the base G1 PPO config for social navigation:
    - Larger network to handle additional obstacle observations
    - Adjusted hyperparameters for the more complex task
    - Extended training iterations for learning avoidance behaviors

    The social navigation task adds (+11 observations):
    - 8 hybrid sector distances (LiDAR + cylinder combined)
    - 3 direct cylinder distances
    - Obstacle proximity rewards (social distance)
    - Personal space penalties (safety)
    - Smooth trajectory rewards (comfort)
    """

    def __post_init__(self):
        super().__post_init__()

        # Customize experiment name
        self.experiment_name = "colibri_g1_social_nav"

        # ============================================
        # NETWORK ARCHITECTURE
        # ============================================

        # Larger network to handle additional LiDAR observations
        # Base G1 config uses [512, 256, 128], we increase for spatial processing
        self.policy.actor_hidden_dims = [512, 512, 256, 128]
        self.policy.critic_hidden_dims = [512, 512, 256, 128]

        # ============================================
        # TRAINING PARAMETERS
        # ============================================

        # Extended training for the more complex social navigation task
        self.max_iterations = 3000

        # Slightly lower learning rate for more stable learning
        # with the additional social navigation rewards
        self.algorithm.learning_rate = 5e-4

        # More frequent saves to track social behavior learning
        self.save_interval = 100

        # ============================================
        # PPO-SPECIFIC PARAMETERS
        # ============================================

        # Increased entropy coefficient to encourage exploration
        # of diverse social navigation strategies
        self.algorithm.entropy_coef = 0.01

        # Clip range for more stable updates
        self.algorithm.clip_param = 0.2
