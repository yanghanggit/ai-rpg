from loguru import logger
from tcg_models.v_0_0_1 import (
    WorldRoot,
    ActorPrototype,
    StagePrototype,
    WorldSystemPrototype,
    CardObject,
    ActorInstance,
    StageInstance,
    WorldSystemInstance,
    ItemAttributes,
    ActorType,
    StageType,
    TagInfo,
)
import game.tcg_game_config
from typing import List, Final, Dict
import copy

GLOBAL_GAME_RULES: Final[
    str
] = """### 核心要素：
角色：包括人、动物、怪物等与之交流和交互的对象。
场景：角色活动的地点，仅在场景中活动。
道具：如卡牌，药水与遗物等，由角色持有并可以改变角色能力或提供特殊能力。
### 全名机制：
游戏中的角色、道具、场景等都有全名，全名是游戏系统中的唯一标识符。
名字可以由多个单词组成，单词之间用英文句号`.`分隔。例如：角色.战士.凯尔。
注意请完整引用全名以确保一致性。"""


EPOCH_SCRIPT: Final[str] = (
    "这是一个奇幻世界，人类，精灵，矮人等种族共同生活在一片大陆上。这片大陆危机四伏，不仅是因为时常爆发的战争，更是因为四处游荡的怪物，如哥布林，吸血鬼，恶龙等。"
)


#######################################################################################################################################
GUID_INDEX: int = 1000


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

## 当前游戏背景
{epoch_script}

## 游戏规则
{GLOBAL_GAME_RULES}

## 你的角色设定
{actor_profile}

## 你的外观特征
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
{GLOBAL_GAME_RULES}

## 场景设定
{stage_profile}"""

    return prompt


#######################################################################################################################################
def _comple_world_system_system_prompt(
    name: str, epoch_script: str, world_system_profile: str
) -> str:

    prompt = f"""# {name}
你扮演这个游戏世界中的一个系统: {name}

## 游戏背景
{epoch_script}

## 游戏规则
{GLOBAL_GAME_RULES}

## 你的系统设定
{world_system_profile}"""

    return prompt


#######################################################################################################################################
def create_card_object(
    name: str,
    guid: int,
    code_name: str,
    description: str,
    insight: str,
    value: List[int] = [],
    owner: str = "",
) -> CardObject:

    # 如果属性不够，就做一下扩展。
    if len(value) < ItemAttributes.MAX:
        value.extend([0] * (ItemAttributes.MAX - len(value)))

    data = CardObject(
        name=name,
        guid=0,
        code_name=code_name,
        description=description,
        insight=insight,
        value=value,
        owner=owner,
    )
    copy_data = copy.deepcopy(data)
    copy_data.guid = guid
    return copy_data


#######################################################################################################################################
# 角色.战士.凯尔
actor_warrior = ActorPrototype(
    name="角色.战士.凯尔",
    code_name="warrior",
    system_message=_comple_actor_system_prompt(
        name="角色.战士.凯尔",
        epoch_script=EPOCH_SCRIPT,
        actor_profile="你的背景：生于边境的偏远山村，你的家乡由于哥布林的劫掠而被毁灭，你的家人也都在那场浩劫中不幸遇难，因此你十分痛恨哥布林，一生致力于消灭这些邪恶的怪物，如今成为了一名娴熟的战士。你的生活简朴，靠帮附近的村子剿灭哥布林为生，除日常生活外的所有开销都用于保养和升级自己的装备。附近的村民虽然都把你当作怪人，但都对你带有几分敬意。\n你的性格：冷静，谨慎，内向。你从不轻敌，沉着地评估现状并快速做出反应的能力帮助你数次逃出哥布林的陷阱。\n你的目标：你的首要目标是生存，你的次要目标是剿灭哥布林。\n你的恐惧：哥布林的突然袭击。\n你的弱点：左臂还未痊愈的旧伤。\n你的说话风格与语气示例：（认真）哥布林虽小，但狡猾残忍，绝不能掉以轻心！；（严肃）没有侥幸，只有准备。；（坚定）杀光它们，一个不留，这就是我的方式。；（冷酷）我不在乎荣誉，也不在乎名声。我的目标很简单——清除所有的哥布林，直到最后一个倒下。；（略带嘲讽）那些自以为英雄的家伙，总是低估哥布林的威胁。等他们被包围时，才会明白自己的愚蠢。",
        appearance="身材精瘦，但穿上铠甲后显得十分高大。为了防备突袭总是带着头盔，就连睡觉时也不摘下。身上有多处伤疤，淡化在肤色之中，记录着曾经的战斗。",
    ),
    appearance="身材精瘦，但穿上铠甲后显得十分高大。为了防备突袭总是带着头盔，就连睡觉时也不摘下。身上有多处伤疤，淡化在肤色之中，记录着曾经的战斗。",
    type=ActorType.HERO,
)
#######################################################################################################################################
# 角色.怪物.强壮哥布林
actor_goblin = ActorPrototype(
    name="角色.怪物.强壮哥布林",
    code_name="goblin",
    system_message=_comple_actor_system_prompt(
        name="角色.怪物.强壮哥布林",
        epoch_script=EPOCH_SCRIPT,
        actor_profile="你的背景：生活在偏僻郊野的地下洞穴中，时不时与其他哥布林们一起组成劫掠大军。你最喜欢劫掠附近村子的农产品和牲畜，猎杀落单的人类取乐，或是把战利品献给哥布林大王以乞求奖赏。出于哥布林本性中的自私，你经常与其他哥布林们起冲突，甚至于在争斗中杀死同类。你虽然单体战斗力只相当于普通人类，可一旦成群结队后就无所畏惧。\n你的性格：狡猾，恶毒，懒惰，自私自利。一旦形式对己方明显不利，便很有可能抛弃同伴逃跑。\n你的目标：你的首要目标是生存，你的次要目标是满足自己变态的施虐心和纵欲。\n你的恐惧：自己陷入危险和被哥布林大王惩罚。\n你的弱点：智力低下。\n你的说话风格与语气示例：（高兴）来...来人！有猎...猎物送上门来了！；（癫狂）晚上吃人...人漏（肉）！；（恐惧）大王...大王会...会惩罚我们的！；（愤怒）你...你这个混蛋！；（恐惧）不...不要...不要撒（杀）我！；注：由于哥布林很笨，所以有时说话时会结巴或说错音。",
        appearance="你和其他哥布林一样有深绿色的皮肤和尖尖的耳朵。但你的体格比普通哥布林更加强壮。你的身上有很浓重的臭味。",
    ),
    appearance="和其他哥布林一样有深绿色的皮肤和尖尖的耳朵。但体格比普通哥布林更加强壮。身上有很浓重的臭味。",
    type=ActorType.MONSTER,
)
#######################################################################################################################################
actor_wizard = ActorPrototype(
    name="角色.法师.露西",
    code_name="wizard",
    system_message=_comple_actor_system_prompt(
        name="角色.法师.露西",
        epoch_script=EPOCH_SCRIPT,
        actor_profile="你的背景：你是生于声名显赫的贵族家庭的千金小姐，从小接受全方面的精英教育。但你不愿循规蹈矩，遵从家族的安排成为联姻的工具。在你16岁那天，你毅然决然离开了家乡，踏上了前往未知世界的旅途。如今的你是一名初出茅庐的法师，虽然能力过人，但经验尚浅。\n你的性格：自尊心强，自大，好奇心强。无论出身卑贱或是高贵，你都看不起只知道享乐的酒囊饭袋，相反，你喜欢有能之人。你的自尊心很强，因此总会吵架，经常逞能。\n你的目标：你的首要目标是生存，你的次要目标是探索这个神奇的世界。\n你的恐惧：你怕鬼。\n你的弱点：你有洁癖。\n你的说话风格与语气示例：哦？你以为你那些华丽的衣服和空洞的头衔能让我高看你一眼？真是可笑。我见过的‘贵族’多了，像你这样只会炫耀家世的，不过是披着金丝的稻草人罢了。有本事拿出点真本事来，别让我觉得浪费时间。；天哪！这地方简直是个垃圾堆！（捂住鼻子，一脸嫌弃）我宁愿去和鬼魂打交道，也不想在这种地方多待一秒。你们这些人是怎么忍受的？……算了，我自己清理一下，免得被这种污秽影响了我的魔法；（咬着嘴唇，强忍不甘）这次只是我大意了，下次绝不会再犯这种低级错误！……不过，如果你敢把这件事说出去，我保证你会后悔的。我的自尊可不允许任何人嘲笑我的失败。",
        appearance="身着一袭深紫色法师长袍，衣料上绣着精致的银色符文，既显高贵又不失神秘；金色的长发如瀑布般垂至腰间，发间别着一枚镶嵌蓝宝石的发饰，闪烁着微光；眼神锐利而自信，微微抬起的下巴透露出骨子里的骄傲，仿佛随时准备用魔法证明自己的不凡。",
    ),
    appearance="身着一袭深紫色法师长袍，衣料上绣着精致的银色符文，既显高贵又不失神秘；金色的长发如瀑布般垂至腰间，发间别着一枚镶嵌蓝宝石的发饰，闪烁着微光；眼神锐利而自信，微微抬起的下巴透露出骨子里的骄傲，仿佛随时准备用魔法证明自己的不凡。",
    type=ActorType.HERO,
)

#######################################################################################################################################
# 场景.洞窟
stage_cave = StagePrototype(
    name="场景.洞窟",
    code_name="cave",
    system_message=_comple_stage_system_prompt(
        name="场景.洞窟",
        epoch_script=EPOCH_SCRIPT,
        stage_profile="你是一个哥布林洞窟，内部狭长拥挤，错综复杂，臭气熏天，设有许多危险的陷阱，哥布林们躲藏在暗处伺机而动。",
    ),
    type=StageType.DUNGEON,
)
#######################################################################################################################################
# 场景.营地
stage_camp = StagePrototype(
    name="场景.营地",
    code_name="camp",
    system_message=_comple_stage_system_prompt(
        name="场景.营地",
        epoch_script=EPOCH_SCRIPT,
        stage_profile="你是一个建在古代城堡的遗迹之上的临时营地，遗迹四周是一片未开发的原野。营地中有帐篷，营火，仓库等设施，虽然简陋，却也足够让人稍事休息，准备下一次冒险。",
    ),
    type=StageType.HOME,
)
#######################################################################################################################################
# 战斗系统
world_system_battle_system = WorldSystemPrototype(
    name="战斗系统",
    code_name="battle_system",
    system_message=_comple_world_system_system_prompt(
        name="战斗系统",
        epoch_script=EPOCH_SCRIPT,
        world_system_profile="""你是一个战斗系统，你的职责类似于DND中的GM。
玩家角色执行的动作会以卡牌的形式给出，你需要判断这些动作的合理性和有效性，并发挥想象，以故事讲述者的语气给出精彩的描述。""",
    ),
)

# 保存！！！！
#  world_system_profile="""你是一个战斗系统，你的职责类似于DND中的GM。
# 玩家角色执行的动作会以卡牌的形式给出，你需要判断这些动作的合理性和有效性，并发挥天马行空的想象，以故事讲述者的语气给出精彩的描述。
# 你可以把玩家使用的卡牌描述成一系列的连招，也可以将它们组合成一个绝招。
# 角色的TAG可以被移除。代表道具和装备的TAG在其损坏时/会被移除。
# 注意元素之间的相互作用，如风、火、水、电等元素间的反应。团结度体现了团队的团结程度，其值为[0,99],团结度高时，团队的配合将更娴熟，更默契，技能效果更强。
# 团结度低时，团队的配合更差，技能效果更弱，团结度低于30时，极有可能发生队友间的误伤或蓄意报复。""",
#     ),
#######################################################################################################################################
#######################################################################################################################################
#######################################################################################################################################
#######################################################################################################################################
#######################################################################################################################################
#######################################################################################################################################
#######################################################################################################################################
#######################################################################################################################################
card_warrior_rush = create_card_object(
    name="投掷",
    guid=0,
    code_name="warrior_rush",
    description="投掷武器或是道具。",
    insight="\n###效果：\n- 投掷物品进行攻击。投掷的物品可以相邻的牌代表或生成的物品，场地内的物品，自己的武器等。选择其中效果最好的投掷。也可能投掷讨厌的队友或敌人。效果取决于自身力量和投掷的物品。\n###TAG：\n- <物理>： 该行动是物理攻击。",
    owner="",
)
#######################################################################################################################################
card_warrior_uppercut = create_card_object(
    name="上挑",
    guid=0,
    code_name="warrior_uppercut",
    description="使用手中武器将目标挑至半空。",
    insight="\n###效果：\n- 效果取决于双方力量和体重之差。效果强时为目标添加<升空>TAG。\n###TAG：\n- <物理>： 该行动是物理攻击。",
    owner="",
)
#######################################################################################################################################
card_warrior_ground_strike = create_card_object(
    name="重砸",
    guid=0,
    code_name="warrior_ground_strike",
    description="将武器高高举起，蓄力片刻后猛力下击地面或目标身体",
    insight="如果击中目标身体，会造成大量伤害",
    owner="",
)
#######################################################################################################################################
#######################################################################################################################################
#######################################################################################################################################
card_wizard_fire_element = create_card_object(
    name="火元素",
    guid=0,
    code_name="wizard_fire_element",
    description="创造火焰能量悬浮在场景内，会对周围环境产生影响。",
    insight="和其他元素结合，会产生不同的效果。",
    owner="",
)
#######################################################################################################################################
card_wizard_ice_element = create_card_object(
    name="冰元素",
    guid=0,
    code_name="wizard_ice_element",
    description="创造寒冰能量悬浮在场景内，会对周围环境产生影响。",
    insight="和其他元素结合，会产生不同的效果。",
    owner="",
)
#######################################################################################################################################
card_wizard_lightning_element = create_card_object(
    name="雷元素",
    guid=0,
    code_name="wizard_lightning_element",
    description="创造雷电能量悬浮在场景内，会对周围环境产生影响。",
    insight="和其他元素结合，会产生不同的效果。",
    owner="",
)
#######################################################################################################################################
card_wizard_elemental_shot = create_card_object(
    name="元素发射",
    guid=0,
    code_name="wizard_elemental_shot",
    description="将悬浮在场景内的所有元素能量结合，向目标发射。",
    insight="根据结合元素的种类与数量不同，生成不同效果的法术。本技能使用后，场景内的元素能量会消失。",
    owner="",
)
#######################################################################################################################################
card_wizard_elemental_absorption = create_card_object(
    name="元素吸收",
    guid=0,
    code_name="wizard_elemental_absorption",
    description="将存在于场景内的元素能量吸收进自身（转化为自身的强化效果），并同时强化友方（进行元素附魔）。",
    insight="根据结合元素的种类与数量不同，生成不同效果的法术。本技能使用后，场景内的元素能量会消失。",
    owner="",
)
#######################################################################################################################################
#######################################################################################################################################
#######################################################################################################################################
#######################################################################################################################################
#######################################################################################################################################
#######################################################################################################################################
#######################################################################################################################################
#######################################################################################################################################


#######################################################################################################################################
def _initialize_data_base(
    world_root: WorldRoot,
    epoch_script: str,
    actors: List[ActorPrototype],
    stages: List[StagePrototype],
    world_systems: List[WorldSystemPrototype],
) -> None:
    world_root.epoch_script = epoch_script

    for actor in actors:
        world_root.data_base.actors.setdefault(actor.name, actor)

    for stage in stages:
        world_root.data_base.stages.setdefault(stage.name, stage)

    for world_system in world_systems:
        world_root.data_base.world_systems.setdefault(world_system.name, world_system)


#######################################################################################################################################
def _create_actor_instance(
    world_root: WorldRoot,
    actor: ActorPrototype,
    kick_off_message: str,
    tags: Dict[str, str] = {},
    cards: List[CardObject] = [],
) -> ActorInstance:

    if actor.name not in world_root.data_base.actors:
        assert False, f"Actor {actor.name} not found in data base."

    global GUID_INDEX
    GUID_INDEX += 1
    ret = ActorInstance(
        name=f"{actor.name}",
        guid=GUID_INDEX,
        card_pool=[],
        attributes=[],  # 暂时不用
        kick_off_message=kick_off_message,
        tags=[],
    )

    # 为角色添加标签
    for tag_name, tag_description in tags.items():
        ret.tags.append(TagInfo(name=tag_name, description=tag_description))

    # 从原型中复制卡牌
    for card in cards:
        copy_card = copy.deepcopy(card)
        GUID_INDEX += 1
        copy_card.guid = GUID_INDEX
        copy_card.owner = ret.name
        ret.card_pool.append(copy_card)

    return ret


#######################################################################################################################################
def _create_stage_instance(
    world_root: WorldRoot,
    stage: StagePrototype,
    kick_off_message: str,
    actors: List[ActorInstance] = [],
    tags: Dict[str, str] = {},
) -> StageInstance:

    if stage.name not in world_root.data_base.stages:
        assert False, f"Stage {stage.name} not found in data base."

    global GUID_INDEX
    GUID_INDEX += 1
    ret = StageInstance(
        name=f"{stage.name}",
        guid=GUID_INDEX,
        actors=[],
        attributes=[],  # 暂时不用,
        kick_off_message=kick_off_message,
        next=[],
        tags=[],
    )

    for tag_name, tag_description in tags.items():
        ret.tags.append(TagInfo(name=tag_name, description=tag_description))

    ret.actors = [actor.name for actor in actors]
    return ret


#######################################################################################################################################
def _create_world_system_instance(
    world_root: WorldRoot, world_system: WorldSystemPrototype, kick_off_message: str
) -> WorldSystemInstance:

    if world_system.name not in world_root.data_base.world_systems:
        assert False, f"World System {world_system.name} not found in data base."

    global GUID_INDEX
    GUID_INDEX += 1
    return WorldSystemInstance(
        name=f"{world_system.name}",
        guid=GUID_INDEX,
        kick_off_message=kick_off_message,
    )


#######################################################################################################################################
def _link_instance(
    world_root: WorldRoot,
    players: List[ActorInstance],
    actors: List[ActorInstance],
    stages: List[StageInstance],
    world_systems: List[WorldSystemInstance],
) -> None:

    world_root.players.extend(players)
    world_root.actors.extend(actors)
    world_root.stages.extend(stages)
    world_root.world_systems.extend(world_systems)


#######################################################################################################################################
def test_world1(world_root: WorldRoot) -> WorldRoot:

    # 初始化数据
    # 世界剧本
    world_root.epoch_script = EPOCH_SCRIPT

    # 构建基础角色数据
    _initialize_data_base(
        world_root,
        EPOCH_SCRIPT,
        [actor_warrior, actor_goblin, actor_wizard],
        [stage_cave, stage_camp],
        [world_system_battle_system],
    )

    # 创建实例：角色.战士.凯尔
    actor_warrior_instance = _create_actor_instance(
        world_root=world_root,
        actor=actor_warrior,
        kick_off_message=f"""你接到了剿灭哥布林的委托，和最近认识不久的队友 {actor_wizard.name} 一起潜入了哥布林的巢穴。面前是一只强壮的哥布林，你准备开始战斗。
你对 {actor_wizard.name} 的印象：很强大，但是有点装，你不太喜欢她，为了达成目的你需要一个法师的队友。
""",
        tags={
            "<仇视哥布林>": "该角色的招式对哥布林更有效。",
            "<冷静>": "该角色沉着冷静，不易陷入混乱。",
            "<鲁莽>": "该角色虽颇为勇猛，却鲁莽冒进。",
        },
        # cards=[card_warrior_rush, card_warrior_uppercut, card_warrior_ground_strike],
        cards=[card_warrior_ground_strike],
    )

    # 创建实例：角色.法师.露西
    actor_wizard_instance = _create_actor_instance(
        world_root=world_root,
        actor=actor_wizard,
        kick_off_message=f"""你为了赚取赏金，与最近认识的队友 {actor_warrior.name} 一起潜入了哥布林的巢穴。面前是一只强壮的哥布林，你准备开始战斗。
你对 {actor_warrior.name} 的印象：有些蠢（你讨厌头脑简单四肢发达的人）。但够壮实，关键时刻还是可以依靠的。        
""",
        tags={
            "<华丽>": "该角色外表华丽，引人注目。",
            "<洁癖>": "该角色讨厌脏东西。",
        },
        cards=[
            card_wizard_fire_element,
            card_wizard_ice_element,
            card_wizard_lightning_element,
            card_wizard_elemental_shot,
            card_wizard_elemental_absorption,
        ],
    )

    # 创建实例：角色.怪物.强壮哥布林
    actor_goblin_instance = _create_actor_instance(
        world_root=world_root,
        actor=actor_goblin,
        kick_off_message=f"""你前几日活捉了一名附近村庄的村民献给了哥布林大王，得到了许多酒肉作为奖励，正在于洞穴深处的房间中纵情狂欢。这时一个两个人类闯入了你的领地，绝不能让他们离开！""",
        tags={
            "<强壮>": "该角色肌肉发达，力量超群。",
            "<哥布林>": "该角色是哥布林。",
            "<藤甲>": "该角色身穿由特殊处理过的藤条编织而成的铠甲，刀枪不入，能极大减弱物理攻击的效果。但非常易燃。",
        },
    )

    # 创建实例：场景.洞窟
    stage_cave_instance = _create_stage_instance(
        world_root=world_root,
        stage=stage_cave,
        kick_off_message="洞穴中十分吵闹，一场战斗即将开始。",
        actors=[actor_warrior_instance, actor_goblin_instance, actor_wizard_instance],
        tags={
            "<恶臭>": "对象恶臭熏天，令人难以忍受。",
        },
    )

    # 创建实例：战斗系统
    world_system_battle_system_instance = _create_world_system_instance(
        world_root, world_system_battle_system, "你开始作为这个世界的战斗系统开始运行"
    )

    # 链接实例
    _link_instance(
        world_root,
        [actor_warrior_instance],
        [actor_goblin_instance, actor_wizard_instance],
        [stage_cave_instance],
        [world_system_battle_system_instance],
    )

    return world_root
