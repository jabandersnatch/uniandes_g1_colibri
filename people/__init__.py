# Copyright (c) 2024, Universidad de los Andes
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""People management module for Colibri G1 digital twin."""

from .people_scene_manager import PeopleSceneManager
from .people_spawner import PeopleSpawner
from .ira_people_manager import IRACharacterManager
from .navmesh_utils import NavMeshUtility

__all__ = [
    "PeopleSceneManager",
    "PeopleSpawner",
    "IRACharacterManager",
    "NavMeshUtility",
]
