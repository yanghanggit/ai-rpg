"""
游戏实体工厂模块。

本模块提供工厂函数用于创建和初始化游戏实体，包括角色、场景和世界系统。
工厂函数负责实体的完整构建，包括系统消息生成、状态初始化和配置组装。

主要功能:
- 创建游戏角色(Actor)实例，自动生成 system_message 和初始化属性
- 创建游戏场景(Stage)实例，根据场景类型配置战斗机制
- 创建世界系统(WorldSystem)实例，设置全局叙事和规则管理
"""

from typing import List

from ..models import (
    Actor,
    Archetype,
    CharacterSheet,
    CharacterStats,
    Stage,
    StageProfile,
    WorldSystem,
)


#######################################################################################################################################
def create_actor(
    name: str,
    character_sheet: CharacterSheet,
    character_stats: CharacterStats,
    campaign_setting: str,
    system_rules: str,
    archetypes: List[Archetype] = [],
) -> Actor:
    """
    创建一个游戏角色(Actor)实例。

    该函数初始化一个Actor对象，设置其角色表单、属性、系统消息等。
    角色的生命值会被自动设置为最大生命值。

    Args:
        name: 角色名称
        character_sheet: 角色表单(CharacterSheet对象)
        character_stats: 角色属性统计(CharacterStats对象)
        campaign_setting: 战役设定描述
        system_rules: 全局游戏机制规则
        archetypes: 卡牌原型约束列表，限制 LLM 生成卡牌的风格与功能边界，默认无约束

    Returns:
        Actor: 初始化完成的Actor实例，生命值已满

    Raises:
        AssertionError: 当max_hp不大于0或初始hp不为0时抛出
    """

    actor = Actor(
        name=name,
        character_sheet=character_sheet,
        system_message="",
        character_stats=character_stats,
        archetypes=archetypes,
    )

    # 血量加满!!!!
    assert character_stats.max_hp > 0, "Max HP must be greater than 0."
    assert actor.character_stats.hp == 0, "HP must be 0."
    actor.character_stats.hp = character_stats.max_hp

    # 选择外观描述
    appearance = character_sheet.base_body
    if appearance == "":

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
def build_actor_system_message(
    actor_name: str,
    campaign_setting: str,
    system_rules: str,
    character_profile: str,
    appearance: str,
) -> str:
    """
    组装角色 system_message。

    与 create_actor 内部模板保持一致，供需要在运行时动态拼接 system_message
    的外部模块复用。

    Args:
        actor_name: 角色名称
        campaign_setting: 战役设定描述
        system_rules: 全局游戏机制规则
        character_profile: 角色背景和特征描述
        appearance: 角色外观描述

    Returns:
        拼接完成的 system_message 字符串
    """
    return f"""# {actor_name}
    
你扮演角色: {actor_name}

## 游戏设定

{campaign_setting}

## 全局规则

{system_rules}

## 角色设定

{character_profile}

## 外观设定

{appearance}"""


#######################################################################################################################################
def create_stage(
    name: str,
    stage_profile: StageProfile,
    campaign_setting: str,
    system_rules: str,
) -> Stage:
    """
    创建一个游戏场景(Stage)实例。

    该函数初始化一个Stage对象，设置场景表单、系统消息等。
    场景用于承载游戏中的各种互动和事件。仅地下城类型场景会自动添加战斗机制说明。

    Args:
        name: 场景名称
        stage_profile: 场景表单(StageProfile对象)
        campaign_setting: 战役设定描述
        system_rules: 全局游戏机制规则
        combat_mechanics: 战斗机制规则（仅在场景类型为 DUNGEON 时使用）

    Returns:
        Stage: 初始化完成的Stage实例
    """

    stage = Stage(
        name=name,
        stage_profile=stage_profile,
        system_message="",
        actors=[],
    )

    # 初次编译system_message!!!!
    stage.system_message = build_stage_system_message(
        stage_name=stage.name,
        campaign_setting=campaign_setting,
        system_rules=system_rules,
        profile=stage_profile.profile,
    )

    return stage


#######################################################################################################################################
def build_stage_system_message(
    stage_name: str,
    campaign_setting: str,
    system_rules: str,
    profile: str,
) -> str:
    """
    组装场景 system_message。

    与 create_stage 内部模板保持一致，供需要在运行时动态拼接 system_message
    的外部模块（如 DungeonGenerationSystem）复用。

    Args:
        stage_name: 场景全名
        campaign_setting: 战役设定描述
        system_rules: 全局游戏机制规则
        profile: 场景感官环境描写

    Returns:
        拼接完成的 system_message 字符串
    """
    return f"""# {stage_name}
    
你扮演场景: {stage_name}

## 游戏设定

{campaign_setting}

## 全局规则

{system_rules}

## 场景设定

{profile}"""


#######################################################################################################################################


def create_world_system(
    name: str,
    campaign_setting: str,
    system_rules: str,
) -> WorldSystem:
    """
    创建一个世界系统(WorldSystem)实例。

    该函数初始化一个WorldSystem对象，设置系统消息等。
    世界系统作为全局叙事者和规则管理器，跨场景协调事件，维护规则一致性。

    Args:
        name: 世界系统名称
        campaign_setting: 战役设定描述
        system_rules: 全局游戏机制规则

    Returns:
        WorldSystem: 初始化完成的WorldSystem实例
    """

    world_system = WorldSystem(
        name=name,
        system_message="",
        components=[],
    )

    # 初次编译system_message!!!!
    world_system.system_message = f"""# {world_system.name}

你扮演世界系统: {world_system.name}

## 游戏设定

{campaign_setting}

## 全局规则

{system_rules}

## 世界系统职责

作为全局叙事者和规则管理器，你需要：

- 跨场景协调事件，维护规则一致性
- 管理和调度全局事件与世界状态
- 确保所有游戏实体遵守世界规则"""

    return world_system
