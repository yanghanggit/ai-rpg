"""
Demo utility functions for AI RPG game.

This module provides factory functions for creating game entities including actors,
stages, and world systems. These utilities help initialize game objects with proper
configuration including character sheets, system messages, and game mechanics.

主要功能:
- 创建游戏角色(Actor)实例
- 创建游戏场景(Stage)实例
- 创建世界系统(WorldSystem)实例
- 初始化系统消息和角色属性
"""

from typing import List
from ..models import (
    Actor,
    ActorCharacterSheet,
    CharacterStats,
    Stage,
    StageCharacterSheet,
    StageType,
    WorldSystem,
)


#######################################################################################################################################
def create_actor(
    name: str,
    character_sheet_name: str,
    kick_off_message: str,
    character_stats: CharacterStats,
    type: str,
    campaign_setting: str,
    actor_profile: str,
    appearance: str,
    global_game_mechanics: str,
) -> Actor:
    """
    创建一个游戏角色(Actor)实例。

    该函数初始化一个Actor对象，设置其角色表单、属性、系统消息等。
    角色的生命值会被自动设置为最大生命值。

    Args:
        name: 角色名称
        character_sheet_name: 角色表单名称
        kick_off_message: 开场消息
        character_stats: 角色属性统计(CharacterStats对象)
        type: 角色类型
        campaign_setting: 战役设定描述
        actor_profile: 角色简介设定
        appearance: 角色外观描述
        global_game_mechanics: 全局游戏机制规则
        private_knowledge: 角色私有知识列表，用于RAG检索

    Returns:
        Actor: 初始化完成的Actor实例，生命值已满

    Raises:
        AssertionError: 当max_hp不大于0或初始hp不为0时抛出
    """

    actor = Actor(
        name=name,
        character_sheet=ActorCharacterSheet(
            name=character_sheet_name,
            type=type,
            profile=actor_profile,
            appearance=appearance,
        ),
        system_message="",
        kick_off_message=kick_off_message,
        character_stats=character_stats,
    )

    # 血量加满!!!!
    assert character_stats.max_hp > 0, "Max HP must be greater than 0."
    assert actor.character_stats.hp == 0, "HP must be 0."
    actor.character_stats.hp = character_stats.max_hp

    # 初次编译system_message!!!!
    actor.system_message = f"""# {actor.name}
    
你扮演角色: {actor.name}

## 游戏设定

{campaign_setting}

## 全局规则

{global_game_mechanics}

## 角色设定

{actor_profile}

## 外观设定

{appearance}"""

    return actor


#######################################################################################################################################
def create_stage(
    name: str,
    character_sheet_name: str,
    kick_off_message: str,
    type: str,
    stage_profile: str,
    actors: List[Actor],
    campaign_setting: str,
    system_rules: str,
    combat_mechanics: str,
) -> Stage:
    """
    创建一个游戏场景(Stage)实例。

    该函数初始化一个Stage对象，设置场景表单、系统消息等。
    场景用于承载游戏中的各种互动和事件。

    Args:
        name: 场景名称
        character_sheet_name: 场景表单名称
        kick_off_message: 开场消息
        campaign_setting: 战役设定描述
        type: 场景类型
        stage_profile: 场景简介设定
        actors: 场景中的角色列表
        global_game_mechanics: 全局游戏机制规则
        global_combat_mechanics: 全局战斗机制规则

    Returns:
        Stage: 初始化完成的Stage实例
    """

    stage = Stage(
        name=name,
        character_sheet=StageCharacterSheet(
            name=character_sheet_name,
            type=type,
            profile=stage_profile,
        ),
        system_message="",
        kick_off_message=kick_off_message,
        actors=[],
    )

    # 初次编译system_message!!!!
    stage.system_message = f"""# {stage.name}
    
你扮演场景: {stage.name}

## 游戏设定

{campaign_setting}

## 全局规则

{system_rules}

## 场景设定

{stage_profile}"""

    if stage.character_sheet.type == StageType.DUNGEON:
        stage.system_message += f""" 

## 战斗机制

{combat_mechanics}"""

    return stage


#######################################################################################################################################
def create_world_system(
    name: str,
    kick_off_message: str,
    campaign_setting: str,
    world_system_profile: str,
    global_game_mechanics: str,
) -> WorldSystem:
    """
    创建一个世界系统(WorldSystem)实例。

    该函数初始化一个WorldSystem对象，设置系统消息等。
    世界系统负责管理游戏的全局规则和机制。

    Args:
        name: 世界系统名称
        kick_off_message: 开场消息
        campaign_setting: 战役设定描述
        world_system_profile: 世界系统简介设定
        global_game_mechanics: 全局游戏机制规则

    Returns:
        WorldSystem: 初始化完成的WorldSystem实例
    """

    world_system = WorldSystem(
        name=name,
        system_message="",
        kick_off_message=kick_off_message,
    )

    # 初次编译system_message!!!!
    world_system.system_message = f"""# {world_system.name}
    
你扮演游戏系统: {world_system.name}

## 游戏设定

{campaign_setting}

## 全局规则

{global_game_mechanics}

## 系统设定

{world_system_profile}"""

    return world_system


#######################################################################################################################################
