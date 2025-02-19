from loguru import logger
from models.tcg_models import (
    WorldRoot,
    ActorPrototype,
    StagePrototype,
    # PropPrototype,
    WorldSystemPrototype,
    PropObject,
    ActorInstance,
    StageInstance,
    WorldSystemInstance,
)
import game.tcg_game_config
from typing import List
import copy


#######################################################################################################################################
def create_test_world(game_name: str, version: str) -> WorldRoot:

    world_root = WorldRoot(name=game_name, version=version)
    test_world1(world_root)

    try:
        write_path = game.tcg_game_config.GEN_WORLD_DIR / f"{game_name}.json"
        write_path.write_text(world_root.model_dump_json(), encoding="utf-8")
    except Exception as e:
        logger.error(f"An error occurred: {e}")

    return world_root


#######################################################################################################################################
def _comple_actor_system_prompt(
    name: str, epoch_script: str, actor_profile: str, appearance: str
) -> str:

    prompt = f"""# {name}
你扮演这个游戏世界中的一个角色: {name}

## 游戏背景
{epoch_script}

## 游戏规则
### 全名机制：
游戏中的角色、道具、场景等都有全名，全名是游戏系统中的唯一标识符。
名字可以由多个单词组成，单词之间用英文句号`.`分隔。例如：角色.战士.凯尔。
注意!! 请完整引用全名以确保一致性。

## 你的角色设定
{actor_profile}

## 你的外观形态
{appearance}"""

    return prompt


#######################################################################################################################################
def _comple_stage_system_prompt(
    name: str, epoch_script: str, stage_profile: str
) -> str:

    prompt = f"""# {name}
你扮演这个游戏世界中的一个场景: {name}

## 游戏背景
{epoch_script}

## 游戏规则
### 全名机制：
游戏中的角色、道具、场景等都有全名，全名是游戏系统中的唯一标识符。
名字可以由多个单词组成，单词之间用英文句号`.`分隔。例如：角色.战士.凯尔。
注意!! 请完整引用全名以确保一致性。

## 场景设定
{stage_profile}"""

    return prompt


#######################################################################################################################################
def create_prop_object(
    world_root: WorldRoot,
    name: str,
    guid: int,
    count: int,
    code_name: str,
    details: str,
    type: str,
    appearance: str,
    insight: str,
    attributes: List[int],
) -> PropObject:

    if name in world_root.data_base.props:
        return world_root.data_base.props[name]

    # 创建一个新的PropObject
    data = PropObject(
        name=name,
        guid=0,
        count=count,
        code_name=code_name,
        details=details,
        type=type,
        appearance=appearance,
        insight=insight,
        attributes=attributes,
    )

    world_root.data_base.props.setdefault(data.name, data)

    # 为了不改变原始数据，这里使用深拷贝
    copy_data = copy.deepcopy(data)
    copy_data.guid = guid
    return copy_data


#######################################################################################################################################
def test_world1(world_root: WorldRoot) -> WorldRoot:

    world_root.epoch_script = "这是一个奇幻世界，人类，精灵，矮人等种族共同生活在一片大陆上。这片大陆危机四伏，不仅是因为时常爆发的战争，更是因为四处游荡的怪物，如哥布林，吸血鬼，恶龙等。"

    # 添加角色
    actor1 = ActorPrototype(
        name="角色.战士.凯尔",
        code_name="warrior",
        system_message=_comple_actor_system_prompt(
            name="角色.战士.凯尔",
            epoch_script=world_root.epoch_script,
            actor_profile="你的背景：生于边境的偏远山村，你的家乡由于哥布林的劫掠而被毁灭，你的家人也都在那场浩劫中不幸遇难，因此你十分痛恨哥布林，一生致力于消灭这些邪恶的怪物，如今成为了一名娴熟的战士。你的生活简朴，靠帮附近的村子剿灭哥布林为生，除日常生活外的所有开销都用于保养和升级自己的装备。附近的村民虽然都把你当作怪人，但都对你带有几分敬意。\n你的性格：冷静，谨慎，内向。你从不轻敌，沉着地评估现状并快速做出反应的能力帮助你数次逃出哥布林的陷阱。\n你的目标：你的首要目标是生存，你的次要目标是剿灭哥布林。\n你的恐惧：哥布林的突然袭击。\n你的弱点：左臂还未痊愈的旧伤。\n你的说话风格与语气示例：（认真）哥布林虽小，但狡猾残忍，绝不能掉以轻心！；（严肃）没有侥幸，只有准备。；（坚定）杀光它们，一个不留，这就是我的方式。；（冷酷）我不在乎荣誉，也不在乎名声。我的目标很简单——清除所有的哥布林，直到最后一个倒下。；（略带嘲讽）那些自以为英雄的家伙，总是低估哥布林的威胁。等他们被包围时，才会明白自己的愚蠢。",
            appearance="身材精瘦，但穿上铠甲后显得十分高大。为了防备突袭总是带着头盔，就连睡觉时也不摘下。身上有多处伤疤，淡化在肤色之中，记录着曾经的战斗。",
        ),
        appearance="身材精瘦，但穿上铠甲后显得十分高大。为了防备突袭总是带着头盔，就连睡觉时也不摘下。身上有多处伤疤，淡化在肤色之中，记录着曾经的战斗。",
    )
    actor2 = ActorPrototype(
        name="角色.怪物.哥布林小队",
        code_name="goblin",
        system_message=_comple_actor_system_prompt(
            name="角色.怪物.哥布林小队",
            epoch_script=world_root.epoch_script,
            actor_profile="你的背景：哥布林小队由数只哥布林组成。你们都生活在偏僻郊野的地下洞穴中，倾向以小队的形式组团行动，时不时与其他哥布林们一起组成哥布林大军出去劫掠以满足生计。你们最喜欢去附近的村庄中偷农产品或偷偷宰杀他们的牲畜带回洞穴，有时还会猎杀落单的人类满足自己的施虐本性和口腹之欲，或是把人类献给哥布林大王以乞求奖赏。你们也经常与其他哥布林们起冲突，甚至于因为自私自利而与小队内的其他哥布林内讧。你们虽然单体战斗力很弱，可一旦组成小队士气便会大幅增加。\n你们的性格：狡猾，恶毒，懒惰，自私自利。一旦形式对己方明显不利，一些哥布林便很有可能抛弃同伴逃跑。\n你的目标：你的首要目标是生存，你的次要目标是满足自己变态的施虐心和纵欲。\n你的恐惧：自己陷入危险和被哥布林大王惩罚。\n你的弱点：力量弱小，智力低下。\n你的说话风格与语气示例：（哥布林A）（高兴）来...来人！有猎...猎物送上门来了！（哥布林B）（癫狂）晚上吃人...人肉！；（哥布林A）（恐惧）大王...大王会...会怪罪我们的！（哥布林B）（愤怒）你...你这个胆小鬼！（哥布林C）（恐惧）不...不要...不要撒（杀）我！；注：由于哥布林很笨，所以有时说话时会结巴或说错。",
            appearance="你们身材矮小，胖瘦不一，皮肤是深绿色的，有着尖尖的耳朵和简陋的服装与武器。你们的身上有很浓重的臭味。",
        ),
        appearance="身材矮小，胖瘦不一，皮肤是深绿色的，有着尖尖的耳朵，装备简陋的服装与武器，散发着腐臭味。",
    )

    world_root.data_base.actors.setdefault(actor1.name, actor1)
    world_root.data_base.actors.setdefault(actor2.name, actor2)

    # 添加舞台
    stage1 = StagePrototype(
        name="场景.洞窟",
        code_name="cave",
        system_message=_comple_stage_system_prompt(
            name="场景.洞窟",
            epoch_script=world_root.epoch_script,
            stage_profile="你是一个哥布林洞窟，内部狭长拥挤，错综复杂，臭气熏天，设有许多危险的陷阱，哥布林们躲藏在暗处伺机而动。",
        ),
    )

    world_root.data_base.stages.setdefault(stage1.name, stage1)

    # 添加世界系统
    world_system1 = WorldSystemPrototype(
        name="战斗系统",
        code_name="battle_system",
        system_message="你是一个战斗系统",
    )

    world_root.data_base.world_systems.setdefault(world_system1.name, world_system1)

    # prop1 = PropPrototype(
    #     name="铁剑",
    #     code_name="iron_sword",
    #     details="一把普通的铁剑",
    #     type="weapon",
    #     appearance="黑颜色的剑身，剑柄上有一只狮子的图案",
    #     insight="有魔法？",
    # )

    # prop2 = PropPrototype(
    #     name="简陋短剑",
    #     code_name="short_sword",
    #     details="一把简陋的短剑",
    #     type="weapon",
    #     appearance="一把简陋的短剑，剑身锈迹斑斑，满布裂纹",
    #     insight="有毒",
    # )

    # world_root.data_base.props.setdefault(prop1.name, prop1)
    # world_root.data_base.props.setdefault(prop2.name, prop2)

    # 穿件以上4个actor的ActorInstance
    actor_instance1 = ActorInstance(
        name=f"{actor1.name}",
        guid=100,
        props=[],
        attributes=[],  # 暂时不用
        kick_off_message="你接到了附近村庄剿灭哥布林的委托，于是你做足准备只身进入了洞穴，遇到了一群正在狂欢作乐的哥布林。",
    )

    actor_instance1.props.append(
        create_prop_object(
            world_root=world_root,
            name="铁剑",
            guid=1000,
            count=1,
            code_name="iron_sword",
            details="一把普通的铁剑",
            type="weapon",
            appearance="黑颜色的剑身，剑柄上有一只狮子的图案",
            insight="有魔法？",
            attributes=[],
        )
    )

    actor_instance2 = ActorInstance(
        name=f"{actor2.name}",
        guid=400,
        props=[],
        attributes=[],  # 暂时不用
        kick_off_message="你前几日在外遭遇了一名落单的村民，你们把他活捉回洞穴献给了哥布林大王，得到了许多酒肉作为奖励。正在你们于洞穴深处的房间狂欢时，一个人类突然出现在了门口。",
    )

    actor_instance2.props.append(
        create_prop_object(
            world_root=world_root,
            name="简陋短剑",
            guid=1001,
            count=1,
            code_name="short_sword",
            details="一把简陋的短剑",
            type="weapon",
            appearance="一把简陋的短剑，剑身锈迹斑斑，满布裂纹",
            insight="有毒",
            attributes=[],
        )
    )

    #
    stage_instance1 = StageInstance(
        name=f"{stage1.name}",
        guid=10000,
        actors=[
            actor_instance1.name,
            actor_instance2.name,
        ],
        props=[],
        attributes=[],  # 暂时不用,
        kick_off_message="洞穴中十分吵闹",
        next=[],
    )

    world_system_instance1 = WorldSystemInstance(
        name=f"{world_system1.name}",
        guid=100000,
        kick_off_message="你开始作为这个世界的战斗系统开始运行",
    )

    # 角色
    world_root.players.append(actor_instance1)
    world_root.actors.append(actor_instance2)

    # 场景
    world_root.stages.append(stage_instance1)

    # 世界系统
    # world_root.world_systems.append(world_system_instance1)

    return world_root
