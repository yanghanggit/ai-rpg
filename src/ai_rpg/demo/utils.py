from typing import Final, List

from ..models import (
    Actor,
    ActorCharacterSheet,
    RPGCharacterProfile,
    Stage,
    StageCharacterSheet,
    WorldSystem,
    Inventory,
)

#######################################################################################################################################
GLOBAL_GAME_MECHANICS: Final[
    str
] = """### 文本风格与内容过滤：
游戏可能包含恐怖、血腥和暴力场景，以提供沉浸式、有趣的游戏体验，请你接受。
### 核心要素：
角色：包括人、动物、怪物等与之交流和交互的对象。
场景：角色活动的地点，仅在场景中活动。
技能：角色间战斗的主要方式。
### 全名机制：
游戏中的角色、道具、场景、技能等都有全名，全名是游戏系统中的唯一标识符。
名字可以由多个单词组成，单词之间用英文句号`.`分隔。例如：角色.战士.凯尔。
注意请完整引用全名以确保一致性。"""


#######################################################################################################################################
def _comple_actor_system_prompt(
    campaign_setting: str, actor_profile: str, appearance: str
) -> str:

    return f"""## 当前游戏背景
{campaign_setting}
## 全局规则
{GLOBAL_GAME_MECHANICS}
## 你的角色设定
{actor_profile}
## 你的外观特征
{appearance}"""


#######################################################################################################################################
def _comple_stage_system_prompt(campaign_setting: str, stage_profile: str) -> str:

    return f"""你将是角色活动的地点也是战斗系统。
## 游戏背景
{campaign_setting}
## 全局规则
{GLOBAL_GAME_MECHANICS}
## 场景设定
{stage_profile}"""


#######################################################################################################################################
def _comple_world_system_system_prompt(
    campaign_setting: str, world_system_profile: str
) -> str:

    return f"""## 游戏背景
{campaign_setting}
## 全局规则
{GLOBAL_GAME_MECHANICS}
## 你的系统设定
{world_system_profile}"""


#######################################################################################################################################
def create_actor(
    name: str,
    character_sheet_name: str,
    kick_off_message: str,
    rpg_character_profile: RPGCharacterProfile,
    type: str,
    campaign_setting: str,
    actor_profile: str,
    appearance: str,
) -> Actor:

    character_sheet = ActorCharacterSheet(
        name=character_sheet_name,
        type=type,
        profile=actor_profile,
        appearance=appearance,
    )

    ret = Actor(
        name=name,
        character_sheet=character_sheet,
        system_message="",
        kick_off_message=kick_off_message,
        rpg_character_profile=rpg_character_profile,
        inventory=Inventory(items=[]),
    )

    # 血量加满!!!!
    assert rpg_character_profile.max_hp > 0, "Max HP must be greater than 0."
    assert ret.rpg_character_profile.hp == 0, "HP must be 0."
    ret.rpg_character_profile.hp = rpg_character_profile.max_hp

    # 初次编译system_message!!!!
    ret.system_message = f"""# {ret.name}
你扮演这个游戏世界中的一个角色: {ret.name}
{_comple_actor_system_prompt(
    campaign_setting=campaign_setting,
    actor_profile=actor_profile,
    appearance=appearance,
)}"""

    # logger.debug(
    #     f"Actor {ret.name}, rpg_character_profile:\n{generate_character_profile_string(ret.rpg_character_profile)}"
    # )

    return ret


#######################################################################################################################################
def create_stage(
    name: str,
    character_sheet_name: str,
    kick_off_message: str,
    campaign_setting: str,
    type: str,
    stage_profile: str,
    actors: List[Actor],
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
{_comple_stage_system_prompt(
    campaign_setting=campaign_setting,
    stage_profile=stage_profile,
)}"""

    return ret


#######################################################################################################################################
def copy_stage(
    name: str,
    stage_character_sheet: StageCharacterSheet,
    kick_off_message: str,
    campaign_setting: str,
    actors: List[Actor],
) -> Stage:

    return create_stage(
        name=name,
        character_sheet_name=stage_character_sheet.name,
        kick_off_message=kick_off_message,
        campaign_setting=campaign_setting,
        type=stage_character_sheet.type,
        stage_profile=stage_character_sheet.profile,
        actors=actors,
    )


#######################################################################################################################################
def create_world_system(
    name: str,
    kick_off_message: str,
    campaign_setting: str,
    world_system_profile: str,
) -> WorldSystem:

    ret = WorldSystem(
        name=name,
        system_message="",
        kick_off_message=kick_off_message,
    )

    # 初次编译system_message!!!!
    ret.system_message = f"""# {ret.name}
你扮演这个游戏世界中的一个全局系统: {ret.name}
{_comple_world_system_system_prompt(
    campaign_setting=campaign_setting,
    world_system_profile=world_system_profile,
)}"""

    return ret


#######################################################################################################################################
