"""
游戏实体工厂模块。
"""

from typing import List, Optional

from . import (
    Actor,
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
    keywords: List[str] = [],
) -> Actor:
    """
    创建一个游戏角色(Actor)实例。
    """

    actor = Actor(
        name=name,
        character_sheet=character_sheet,
        system_message="",
        character_stats=character_stats,
        keywords=keywords,
    )

    # 血量加满!!!!
    assert character_stats.max_hp > 0, "Max HP must be greater than 0."
    assert actor.character_stats.hp == 0, "HP must be 0."
    actor.character_stats.hp = character_stats.max_hp

    # 初次编译system_message!!!!
    actor.system_message = build_actor_system_message(
        actor_name=actor.name,
        campaign_setting=campaign_setting,
        system_rules=system_rules,
        character_profile=character_sheet.profile,
        base_body=character_sheet.base_body,
    )

    assert (
        len(actor.keywords) > 0
    ), f"DBG 游戏要求每个角色至少有一个关键词约束: {actor.name}"
    return actor


#######################################################################################################################################
def build_actor_system_message(
    actor_name: str,
    campaign_setting: str,
    system_rules: str,
    character_profile: str,
    base_body: str,
) -> str:
    """
    组装角色 system_message。
    """
    return f"""# {actor_name}
    
你扮演角色: {actor_name}

## 游戏设定

{campaign_setting}

## 全局规则

{system_rules}

## 角色设定

{character_profile}

## 基础体型

{base_body}"""


#######################################################################################################################################
def create_stage(
    name: str,
    stage_profile: StageProfile,
    campaign_setting: str,
    system_rules: str,
) -> Stage:
    """
    创建一个游戏场景(Stage)实例。
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
    role_rules: Optional[str] = None,
) -> WorldSystem:
    """
    创建一个世界系统(WorldSystem)实例。
    """

    world_system = WorldSystem(
        name=name,
        system_message="",
        components=[],
    )

    role_rules_section = f"\n\n{role_rules}" if role_rules is not None else ""

    # 初次编译system_message!!!!
    world_system.system_message = f"""# {world_system.name}

你扮演世界系统: {world_system.name}

## 游戏设定

{campaign_setting}

## 全局规则

{system_rules}{role_rules_section}"""

    return world_system
