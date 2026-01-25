# Copyright (c) 2022-2025, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Colibri G1 Digital Twin Locomotion Tasks.

Task Variants:
    - Isaac-Colibri-G1-v0: Base goal-directed locomotion
    - Isaac-Colibri-G1-Play-v0: Visualization variant
    - Isaac-Colibri-G1-SocialNav-v0: Social navigation (LiDAR + Cylinder obstacles + Avoidance rewards)
    - Isaac-Colibri-G1-SocialNav-Play-v0: Social navigation visualization

Note: People-based tasks (Isaac-Colibri-G1-People-*) deprecated - IRA doesn't work with IsaacLab.
"""

import gymnasium as gym

from . import agents
from .digital_twin_colibri_g1_env_cfg import (
    DigitalTwinColibriG1EnvCfg,
    DigitalTwinColibriG1EnvCfg_PLAY,
)
from .social_nav_env_cfg import (
    DigitalTwinColibriG1SocialNavEnvCfg,
    DigitalTwinColibriG1SocialNavEnvCfg_PLAY,
)

##
# Register Gymnasium Environments
##

gym.register(
    id="Isaac-Colibri-G1-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": DigitalTwinColibriG1EnvCfg,
        # Reuse G1's proven PPO configuration for training
        "rsl_rl_cfg_entry_point": "isaaclab_tasks.manager_based.locomotion.velocity.config.g1.agents.rsl_rl_ppo_cfg:G1FlatPPORunnerCfg",
    },
)

gym.register(
    id="Isaac-Colibri-G1-Play-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": DigitalTwinColibriG1EnvCfg_PLAY,
        "rsl_rl_cfg_entry_point": "isaaclab_tasks.manager_based.locomotion.velocity.config.g1.agents.rsl_rl_ppo_cfg:G1FlatPPORunnerCfg",
    },
)

##
# Social Navigation Environment Variants
# Combines RayCaster LiDAR + Moving cylinder obstacles + Collision avoidance rewards
##

gym.register(
    id="Isaac-Colibri-G1-SocialNav-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": DigitalTwinColibriG1SocialNavEnvCfg,
        "rsl_rl_cfg_entry_point": f"{agents.__name__}.rsl_rl_ppo_cfg:ColibriG1SocialNavPPORunnerCfg",
    },
)

gym.register(
    id="Isaac-Colibri-G1-SocialNav-Play-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": DigitalTwinColibriG1SocialNavEnvCfg_PLAY,
        "rsl_rl_cfg_entry_point": f"{agents.__name__}.rsl_rl_ppo_cfg:ColibriG1SocialNavPPORunnerCfg",
    },
)
