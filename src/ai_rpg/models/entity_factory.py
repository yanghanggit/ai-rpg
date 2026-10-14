"""
游戏实体工厂模块。

system prompt 段序原则：内容向的「游戏设定」「角色/场景/神器设定」「基础体型」等在前，
具备规则效果的「全局规则」在后——让 agent 先建立人物与世界观，最后读到必须遵守的规则。
"""

from typing import List

from . import (
    Actor,
    ActorType,
    Artifact,
    CharacterStats,
    Stage,
    StageType,
    World,
)


#######################################################################################################################################
def create_actor(
    name: str,
    actor_type: ActorType,
    profile: str,
    base_body: str,
    character_stats: CharacterStats,
    campaign_setting: str,
    system_rules: str,
) -> Actor:
    """
    创建一个游戏角色(Actor)实例。
    """

    assert name.strip() != "", "DBG 游戏要求必须有角色名称(name)"
    assert profile.strip() != "", "DBG 游戏要求必须有角色设定(profile)"
    assert base_body.strip() != "", "DBG 游戏要求必须有角色设定(base_body)"
    assert (
        campaign_setting.strip() != ""
    ), "DBG 游戏要求必须有游戏设定(campaign_setting)"
    assert system_rules.strip() != "", "DBG 游戏要求必须有系统规则(system_rules)"

    actor = Actor(
        name=name,
        type=actor_type,
        profile=profile,
        base_body=base_body,
        system_message="",
        character_stats=character_stats,
    )

    # 血量加满!!!!
    assert character_stats.max_hp > 0, "Max HP must be greater than 0."
    # assert actor.character_stats.hp == 0, "HP must be 0."
    actor.character_stats.hp = character_stats.max_hp

    # 系统提示词词
    actor.system_message = f"""# {actor.name}

你扮演角色: {actor.name}

## 游戏设定

{campaign_setting}

## 角色设定

{profile}

### 基础体型

{base_body}

## 全局规则

{system_rules}"""

    return actor


#######################################################################################################################################
def create_stage(
    name: str,
    stage_type: StageType,
    profile: str,
    campaign_setting: str,
    system_rules: str,
) -> Stage:
    """
    创建一个游戏场景(Stage)实例。
    """

    assert name.strip() != "", "DBG 游戏要求必须有场景名称(name)"
    assert profile.strip() != "", "DBG 游戏要求必须有场景设定(profile)"
    assert (
        campaign_setting.strip() != ""
    ), "DBG 游戏要求必须有游戏设定(campaign_setting)"
    assert system_rules.strip() != "", "DBG 游戏要求必须有系统规则(system_rules)"

    # 创建场景实例
    stage = Stage(
        name=name,
        type=stage_type,
        profile=profile,
        system_message="",
        actors=[],
    )

    # 系统提示词词
    stage.system_message = f"""# {stage.name}

你扮演场景: {stage.name}

## 游戏设定

{campaign_setting}

## 场景设定

{profile}

## 全局规则

{system_rules}"""

    return stage


#######################################################################################################################################


def create_world(
    name: str, campaign_setting: str, system_rules: str, role_rules: str
) -> World:
    """
    创建一个世界(World)实例。
    """

    assert name.strip() != "", "DBG 游戏要求必须有世界名称(name)"
    assert (
        campaign_setting.strip() != ""
    ), "DBG 游戏要求必须有游戏设定(campaign_setting)"
    assert system_rules.strip() != "", "DBG 游戏要求必须有系统规则(system_rules)"
    assert role_rules.strip() != "", "DBG 游戏要求必须有角色扮演规则(role_rules)"

    # 创建世界实例
    world = World(
        name=name,
        system_message="",
        components={},
    )

    # 系统提示词词
    world.system_message = f"""# {world.name}

你扮演世界: {world.name}

## 游戏设定

{campaign_setting}

{role_rules}

## 全局规则

{system_rules}"""

    return world


#######################################################################################################################################
def create_artifact(
    name: str,
    description: str,
    modifiers: List[str],
    source: str = "",
) -> Artifact:
    """
    创建一个神器(Artifact)实例。

    神器与 Card 同级：只承载人设意象（description）与修正规则（modifiers），
    由携带它的宿主通过 ReliquaryComponent 声明归属；source 标识以谁的名义生效，
    运行时作为场景仲裁者的结算参数被注入提示词。
    """

    assert name.strip() != "", "DBG 游戏要求必须有神器名称(name)"
    assert description.strip() != "", "DBG 游戏要求必须有神器设定(description)"
    assert modifiers, "DBG 游戏要求神器至少有一条修正规则(modifiers)"

    # 创建神器实例
    artifact = Artifact(
        name=name,
        description=description,
        source=source,
        modifiers=list(modifiers),
    )

    return artifact
