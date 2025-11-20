from typing import List
from ..models import (
    Actor,
    ActorCharacterSheet,
    CharacterStats,
    Stage,
    StageCharacterSheet,
    WorldSystem,
    Inventory,
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

    character_sheet = ActorCharacterSheet(
        name=character_sheet_name,
        type=type,
        profile=actor_profile,
        appearance=appearance,
    )

    actor = Actor(
        name=name,
        character_sheet=character_sheet,
        system_message="",
        kick_off_message=kick_off_message,
        character_stats=character_stats,
        inventory=Inventory(items=[]),
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
    campaign_setting: str,
    type: str,
    stage_profile: str,
    actors: List[Actor],
    global_game_mechanics: str,
) -> Stage:

    character_sheet = StageCharacterSheet(
        name=character_sheet_name,
        type=type,
        profile=stage_profile,
    )

    ret = Stage(
        name=name,
        character_sheet=character_sheet,
        system_message="",
        kick_off_message=kick_off_message,
        actors=[],
    )

    # 初次编译system_message!!!!
    ret.system_message = f"""# {ret.name}
你扮演这个游戏世界中的一个场景: {ret.name}
你将是角色活动的地点也是战斗系统。

## 游戏背景

{campaign_setting}

## 全局规则

{global_game_mechanics}

## 场景设定

{stage_profile}"""

    return ret


#######################################################################################################################################
def create_world_system(
    name: str,
    kick_off_message: str,
    campaign_setting: str,
    world_system_profile: str,
    global_game_mechanics: str,
) -> WorldSystem:

    ret = WorldSystem(
        name=name,
        system_message="",
        kick_off_message=kick_off_message,
    )

    # 初次编译system_message!!!!
    ret.system_message = f"""# {ret.name}
你扮演这个游戏世界中的一个全局系统: {ret.name}
## 游戏背景

{campaign_setting}

## 全局规则

{global_game_mechanics}

## 你的系统设定

{world_system_profile}"""

    return ret


#######################################################################################################################################
