"""
游戏实体工厂模块。

本模块提供工厂函数用于创建和初始化游戏实体，包括角色、场景和世界系统。
工厂函数负责实体的完整构建，包括系统消息生成、状态初始化和配置组装。

主要功能:
- 创建游戏角色(Actor)实例，自动生成 system_message 和初始化属性
- 创建游戏场景(Stage)实例，根据场景类型配置战斗机制
- 创建世界系统(WorldSystem)实例，设置全局叙事和规则管理
"""

from ..models import (
    Actor,
    CharacterSheet,
    CharacterStats,
    Stage,
    StageProfile,
    StageType,
    WorldSystem,
)
from loguru import logger


#######################################################################################################################################
def create_actor(
    name: str,
    character_sheet: CharacterSheet,
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
        character_sheet: 角色表单(CharacterSheet对象)
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
    stage_profile: StageProfile,
    campaign_setting: str,
    system_rules: str,
    combat_mechanics: str,
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

{stage_profile.profile}"""

    # 仅地下城场景添加战斗机制说明
    if stage.stage_profile.type == StageType.DUNGEON:
        stage.system_message += f""" 

## 战斗机制

{combat_mechanics}"""

    return stage


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
        kick_off_message="",
        component="",
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
