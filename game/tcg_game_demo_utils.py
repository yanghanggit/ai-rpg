from models.v_0_0_1 import (
    Boot,
    ActorPrototype,
    StagePrototype,
    WorldSystemPrototype,
    ActorInstance,
    StageInstance,
    WorldSystemInstance,
    BaseAttributes,
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
GUID_INDEX: int = 1000


#######################################################################################################################################
def _comple_actor_system_prompt(
    name: str, epoch_script: str, actor_profile: str, appearance: str
) -> str:

    return f"""# {name}
你扮演这个游戏世界中的一个角色: {name}
## 当前游戏背景
{epoch_script}
## 全局规则
{GLOBAL_GAME_RULES}
## 你的角色设定
{actor_profile}
## 你的外观特征
{appearance}"""


#######################################################################################################################################
def _comple_stage_system_prompt(
    name: str, epoch_script: str, stage_profile: str
) -> str:

    return f"""# {name}
你扮演这个游戏世界中的一个场景: {name}
你将是角色活动的地点也是战斗系统。
## 游戏背景
{epoch_script}
## 全局规则
{GLOBAL_GAME_RULES}
## 场景设定
{stage_profile}"""


#######################################################################################################################################
def _comple_world_system_system_prompt(
    name: str, epoch_script: str, world_system_profile: str
) -> str:

    return f"""# {name}
你扮演这个游戏世界中的一个系统: {name}
## 游戏背景
{epoch_script}
## 全局规则
{GLOBAL_GAME_RULES}
## 你的系统设定
{world_system_profile}"""


#######################################################################################################################################
def _initialize_data_base(
    world_boot: Boot,
    epoch_script: str,
    actors: List[ActorPrototype],
    stages: List[StagePrototype],
    world_systems: List[WorldSystemPrototype],
) -> None:

    world_boot.epoch_script = epoch_script

    for actor in actors:
        world_boot.data_base.actors.setdefault(actor.name, actor)

    for stage in stages:
        world_boot.data_base.stages.setdefault(stage.name, stage)

    for world_system in world_systems:
        world_boot.data_base.world_systems.setdefault(world_system.name, world_system)


#######################################################################################################################################
def _create_actor_instance(
    name: str,
    actor_prototype: ActorPrototype,
    kick_off_message: str,
    attributes: BaseAttributes,
) -> ActorInstance:

    global GUID_INDEX
    GUID_INDEX += 1
    ret = ActorInstance(
        name=name,
        prototype=actor_prototype.name,
        guid=GUID_INDEX,
        kick_off_message=kick_off_message,
        base_attributes=attributes,
    )

    # 血量加满。
    assert attributes.max_hp > 0, "Max HP must be greater than 0."
    assert ret.base_attributes.hp == 0, "HP must be 0."
    ret.base_attributes.hp = attributes.max_hp

    return ret


#######################################################################################################################################
def _create_stage_instance(
    name: str,
    stage: StagePrototype,
    kick_off_message: str,
    actors: List[ActorInstance] = [],
) -> StageInstance:

    global GUID_INDEX
    GUID_INDEX += 1
    ret = StageInstance(
        name=name,
        prototype=stage.name,
        guid=GUID_INDEX,
        actors=[],
        kick_off_message=kick_off_message,
    )

    ret.actors = [actor.name for actor in actors]
    return ret


#######################################################################################################################################
def _create_world_system_instance(
    name: str,
    world_system: WorldSystemPrototype,
    kick_off_message: str,
) -> WorldSystemInstance:

    global GUID_INDEX
    GUID_INDEX += 1
    return WorldSystemInstance(
        name=name,
        prototype=world_system.name,
        guid=GUID_INDEX,
        kick_off_message=kick_off_message,
    )


#######################################################################################################################################
def _link_instance(
    world_boot: Boot,
    players: List[ActorInstance],
    actors: List[ActorInstance],
    stages: List[StageInstance],
    world_systems: List[WorldSystemInstance],
) -> None:

    world_boot.players.extend(players)
    world_boot.actors.extend(actors)
    world_boot.stages.extend(stages)
    world_boot.world_systems.extend(world_systems)

    for player in players:
        assert (
            player.prototype in world_boot.data_base.actors
        ), f"Actor {player.prototype} not found in data base."
    for actor in actors:
        assert (
            actor.prototype in world_boot.data_base.actors
        ), f"Actor {actor.prototype} not found in data base."
    for stage in stages:
        assert (
            stage.prototype in world_boot.data_base.stages
        ), f"Stage {stage.prototype} not found in data base."
    for world_system in world_systems:
        assert (
            world_system.prototype in world_boot.data_base.world_systems
        ), f"World System {world_system.prototype} not found in data base."

    # 检查players 与 actors是否有重复
    for player in players:
        for actor in actors:
            if player.name == actor.name:
                assert False, f"Actor {player.name} found in both players and actors."

    # 检查是否有不在players与actors中的actor
    append_actors = players + actors
    check_names = [actor.name for actor in append_actors]
    for stage in stages:
        for test_actor in stage.actors:
            if test_actor not in check_names:
                assert False, f"Actor {test_actor} not found in append_actors."


#######################################################################################################################################
