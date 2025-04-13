from loguru import logger
from models_v_0_0_1 import (
    Actor,
    Stage,
    WorldSystem,
    ActorPrototype,
    StagePrototype,
    RPGCharacterProfile,
    generate_character_profile_string,
)
from typing import List, Final

#######################################################################################################################################
COMBAT_RULES_DESCRIPTION: Final[
    str
] = """### 如 A 攻击 B
先判断命中，由你根据上下文来推理与决定。
若未命中，则伤害为0。若命中，则
物理伤害 = max(1, (A物理攻击 * alpha) - B物理防御)，alpha由你来决定。
魔法伤害 = max(1, (A魔法攻击 * beta) - B魔法防御)，beta表达元素克制与适应性。
B生命 = B生命 - 伤害，如果B生命 <= 0，则B死亡。
### 如果 A 治疗 B。
治疗量 = A魔法攻击 * beta，beta此时由你来决定。
B生命 = B生命 + 治疗量，如果B生命 > B最大生命值，则B生命 = B最大生命值。
### 伤害与治疗最终结果均向上取整。"""

#######################################################################################################################################
GLOBAL_GAME_RULES: Final[
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


# Max HP = 50 + (10 × STR)
# Physical Attack = 5  + (2  × STR)
# Physical Defense = 5  + (1  × STR)
# Magic Attack = 5  + (2  × WIS)
# Magic Defense = 5  + (1  × WIS)
#######################################################################################################################################
ATTRIBUTE_RULES_DESCRIPTION: Final[
    str
] = f"""- 最大生命值(MAX HP)，由力量决定。
- 力量（Strength/STR）：影响最大生命值、物理攻击、物理防御。
- 智慧（Wisdom/WIS）：影响魔法攻击、魔法防御。
- 敏捷（Dexterity/DEX）：影响行动速度。
- 物理攻击(Physical Attack)，由力量决定。
- 物理防御(Physical Defense)，由力量决定。
- 魔法攻击(Magic Attack)，由智慧决定。
- 魔法防御(Magic Defense)，由智慧决定。"""


#######################################################################################################################################

EPOCH_SCRIPT: Final[
    str
] = """在这片名为「艾尔法尼亚」的大陆上，剑与魔法共存已历经数百年。
人类、精灵与兽人各自建立了繁荣的王国，但也不断受到魔物与黑暗势力的威胁。
传说曾有圣剑封印了魔王的力量，然而邪恶的气息再度卷土重来。
古老的遗迹、神秘的宝藏与未知的险境等待新的冒险者踏上旅途，而人们正期盼着新的勇者出现，守护这片动荡却充满希望的土地。"""


#######################################################################################################################################
def _comple_actor_system_prompt(
    epoch_script: str, actor_profile: str, appearance: str
) -> str:

    return f"""## 当前游戏背景
{epoch_script}
## 全局规则
{GLOBAL_GAME_RULES}
## 你的角色设定
{actor_profile}
## 你的外观特征
{appearance}"""


#######################################################################################################################################
def _comple_stage_system_prompt(epoch_script: str, stage_profile: str) -> str:

    return f"""你将是角色活动的地点也是战斗系统。
## 游戏背景
{epoch_script}
## 全局规则
{GLOBAL_GAME_RULES}
## 场景设定
{stage_profile}"""


#######################################################################################################################################
def _comple_world_system_system_prompt(
    epoch_script: str, world_system_profile: str
) -> str:

    return f"""## 游戏背景
{epoch_script}
## 全局规则
{GLOBAL_GAME_RULES}
## 你的系统设定
{world_system_profile}"""


#######################################################################################################################################
def create_actor(
    name: str,
    prototype_name: str,
    kick_off_message: str,
    rpg_character_profile: RPGCharacterProfile,
    type: str,
    epoch_script: str,
    actor_profile: str,
    appearance: str,
) -> Actor:

    prototype = ActorPrototype(
        name=prototype_name,
        type=type,
        profile=actor_profile,
        appearance=appearance,
    )

    ret = Actor(
        name=name,
        prototype=prototype,
        system_message="",
        kick_off_message=kick_off_message,
        rpg_character_profile=rpg_character_profile,
    )

    # 血量加满!!!!
    assert rpg_character_profile.max_hp > 0, "Max HP must be greater than 0."
    assert ret.rpg_character_profile.hp == 0, "HP must be 0."
    ret.rpg_character_profile.hp = rpg_character_profile.max_hp

    # 初次编译system_message!!!!
    ret.system_message = f"""# {ret.name}
你扮演这个游戏世界中的一个角色: {ret.name}
{_comple_actor_system_prompt(
    epoch_script=epoch_script,
    actor_profile=actor_profile,
    appearance=appearance,
)}"""

    logger.debug(
        f"Actor {ret.name}, rpg_character_profile:\n{generate_character_profile_string(ret.rpg_character_profile)}"
    )

    return ret


#######################################################################################################################################
def create_stage(
    name: str,
    prototype_name: str,
    kick_off_message: str,
    epoch_script: str,
    type: str,
    stage_profile: str,
    actors: List[Actor],
) -> Stage:

    prototype = StagePrototype(
        name=prototype_name,
        type=type,
        profile=stage_profile,
    )

    ret = Stage(
        name=name,
        prototype=prototype,
        system_message="",
        kick_off_message=kick_off_message,
        actors=[],
    )

    # 初次编译system_message!!!!
    ret.system_message = f"""# {ret.name}
你扮演这个游戏世界中的一个场景: {ret.name}
{_comple_stage_system_prompt(
    epoch_script=epoch_script,
    stage_profile=stage_profile,
)}"""

    return ret


#######################################################################################################################################
def copy_stage(
    name: str,
    prototype: StagePrototype,
    kick_off_message: str,
    epoch_script: str,
    actors: List[Actor],
) -> Stage:

    return create_stage(
        name=name,
        prototype_name=prototype.name,
        kick_off_message=kick_off_message,
        epoch_script=epoch_script,
        type=prototype.type,
        stage_profile=prototype.profile,
        actors=actors,
    )


#######################################################################################################################################
def create_world_system(
    name: str,
    kick_off_message: str,
    epoch_script: str,
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
    epoch_script=epoch_script,
    world_system_profile=world_system_profile,
)}"""

    return ret


#######################################################################################################################################
