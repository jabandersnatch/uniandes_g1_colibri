# Copyright (c) 2022-2025, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Colibri G1 Digital Twin Locomotion Tasks.

Task Variants:
    - Isaac-Colibri-G1-v0: Base goal-directed locomotion
    - Isaac-Colibri-G1-Play-v0: Visualization variant
    - Isaac-Colibri-G1-People-v0: Training with animated people
    - Isaac-Colibri-G1-People-Play-v0: Visualization with people
    - Isaac-Colibri-G1-SocialNav-v0: Social navigation (LiDAR + People + Social rewards)
    - Isaac-Colibri-G1-SocialNav-Play-v0: Social navigation visualization
"""

import gymnasium as gym

from . import agents
from .digital_twin_colibri_g1_env_cfg import (
    DigitalTwinColibriG1EnvCfg,
    DigitalTwinColibriG1EnvCfg_PLAY,
)
from .people_env_cfg import (
    DigitalTwinColibriG1PeopleEnvCfg,
    DigitalTwinColibriG1PeopleEnvCfg_PLAY,
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
# People Environment Variants
# These variants include animated human characters as dynamic obstacles
##

gym.register(
    id="Isaac-Colibri-G1-People-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": DigitalTwinColibriG1PeopleEnvCfg,
        "rsl_rl_cfg_entry_point": f"{agents.__name__}.rsl_rl_ppo_cfg:ColibriG1PPORunnerCfg",
    },
)

gym.register(
    id="Isaac-Colibri-G1-People-Play-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": DigitalTwinColibriG1PeopleEnvCfg_PLAY,
        "rsl_rl_cfg_entry_point": f"{agents.__name__}.rsl_rl_ppo_cfg:ColibriG1PPORunnerCfg",
    },
)

##
# Social Navigation Environment Variants
# Combines LiDAR perception + Animated people + Social navigation rewards
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
