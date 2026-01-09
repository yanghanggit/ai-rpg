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

from ..models import (
    Actor,
    ActorCharacterSheet,
    CharacterStats,
    Stage,
    StageCharacterSheet,
    StageType,
)
from loguru import logger


#######################################################################################################################################
def create_actor(
    name: str,
    character_sheet: ActorCharacterSheet,
    character_stats: CharacterStats,
    campaign_setting: str,
    system_rules: str,
) -> Actor:
    """
    创建一个游戏角色(Actor)实例。

    该函数初始化一个Actor对象，设置其角色表单、属性、系统消息等。
    角色的生命值会被自动设置为最大生命值。

    Args:
        name: 角色名称
        character_sheet: 角色表单(ActorCharacterSheet对象)
        kick_off_message: 开场消息
        character_stats: 角色属性统计(CharacterStats对象)
        campaign_setting: 战役设定描述
        system_rules: 全局游戏机制规则

    Returns:
        Actor: 初始化完成的Actor实例，生命值已满

    Raises:
        AssertionError: 当max_hp不大于0或初始hp不为0时抛出
    """

    actor = Actor(
        name=name,
        character_sheet=character_sheet,
        system_message="",
        kick_off_message="",
        character_stats=character_stats,
    )

    # 血量加满!!!!
    assert character_stats.max_hp > 0, "Max HP must be greater than 0."
    assert actor.character_stats.hp == 0, "HP must be 0."
    actor.character_stats.hp = character_stats.max_hp

    # 选择外观描述
    appearance = character_sheet.base_body
    if appearance == "":
        logger.warning(
            f"Actor {name} has empty base_body in character_sheet, using appearance instead."
        )
        appearance = character_sheet.appearance

    # 初次编译system_message!!!!
    actor.system_message = f"""# {actor.name}
    
你扮演角色: {actor.name}

## 游戏设定

{campaign_setting}

## 全局规则

{system_rules}

## 角色设定

{character_sheet.profile}

## 外观设定

{appearance}"""

    return actor


#######################################################################################################################################
def create_stage(
    name: str,
    character_sheet: StageCharacterSheet,
    # kick_off_message: str,
    # actors: List[Actor],
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
        character_sheet: 场景表单(StageCharacterSheet对象)
        kick_off_message: 开场消息
        actors: 场景中的角色列表
        campaign_setting: 战役设定描述
        system_rules: 全局游戏机制规则
        combat_mechanics: 全局战斗机制规则

    Returns:
        Stage: 初始化完成的Stage实例
    """

    stage = Stage(
        name=name,
        character_sheet=character_sheet,
        system_message="",
        kick_off_message="",
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

{character_sheet.profile}"""

    if stage.character_sheet.type == StageType.DUNGEON:
        stage.system_message += f""" 

## 战斗机制

{combat_mechanics}"""

    return stage


#######################################################################################################################################
