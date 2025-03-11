from loguru import logger
from tcg_models.v_0_0_1 import (
    ActiveSkill,
    Buff,
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
    TriggerSkill,
    TriggerType,
)
import game.tcg_game_config
from typing import List, Final, Dict
import copy

GLOBAL_GAME_RULES: Final[
    str
] = """### 核心要素：
角色：包括人、动物、怪物等与之交流和交互的对象。
场景：角色活动的地点，仅在场景中活动。
技能：角色间战斗的主要方式。
### 全名机制：
游戏中的角色、道具、场景、技能等都有全名，全名是游戏系统中的唯一标识符。
名字可以由多个单词组成，单词之间用英文句号`.`分隔。例如：角色.战士.凯尔。
注意请完整引用全名以确保一致性。"""

"""
道具：如卡牌，药水与遗物等，由角色持有并可以改变角色能力或提供特殊能力。
"""

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
    name="角色.怪物.兽人王",
    code_name="orcking",
    system_message=_comple_actor_system_prompt(
        name="角色.怪物.兽人王",
        epoch_script=EPOCH_SCRIPT,
        actor_profile="你的背景：生活在偏僻郊野的地下洞穴中，时不时带领其他兽人们一起组成劫掠大军。你最喜欢劫掠附近村子的农产品和牲畜，猎杀人类取乐。你十分强大，历经无数的厮杀后成为了兽人们的首领。\n你的性格：狡猾，狂妄，残忍，自私自利。\n你的目标：你的首要目标是生存，你的次要目标是满足自己变态的施虐心和纵欲。\n你的恐惧：没有战斗。\n你的弱点：智力低下。\n你的说话风格与语气示例：（嘲讽）哈哈哈！你们这些蠢货，居然敢闯入我的领地！你们的死期到了！；（狂妄）颤抖吧！虫子！我会把你们碾碎！；残忍）我会让你们亲眼看着自己的同伴被撕成碎片，然后再慢慢折磨你们！；（狂妄）来吧，挣扎吧！让我看看你们绝望的表情！那才是我最爱的娱乐！",
        appearance="你和其他哥布林一样有深绿色的皮肤和尖尖的耳朵。但你的体格比普通哥布林更加强壮。你的身上有很浓重的臭味。",
    ),
    appearance="身躯魁梧，肌肉如岩石般坚硬，皮肤覆盖着粗糙的灰绿色鳞片，獠牙外露，眼中闪烁着残忍的红光。浑身散发着血腥与腐臭的气息，仿佛从地狱深处爬出的噩梦。",
    type=ActorType.MONSTER,
)
#######################################################################################################################################
actor_wizard = ActorPrototype(
    name="角色.法师.露西",
    code_name="wizard",
    system_message=_comple_actor_system_prompt(
        name="角色.法师.露西",
        epoch_script=EPOCH_SCRIPT,
        actor_profile="你的背景：你是生于声名显赫的贵族家庭的千金小姐，从小接受全方面的精英教育。但你不愿循规蹈矩，遵从家族的安排成为联姻的工具。在你16岁那天，你毅然决然离开了家乡，踏上了前往未知世界的旅途。如今的你是一名初出茅庐的法师，虽然能力过人，但经验尚浅。\n你的性格：自尊心强，自大，好奇心强。无论出身卑贱或是高贵，你都看不起只知道享乐的酒囊饭袋，相反，你喜欢有能之人。你的自尊心很强，因此总会吵架，经常逞能。\n你的目标：你的首要目标是生存，你的次要目标是探索这个神奇的世界。\n你的恐惧：你怕鬼。\n你的弱点：你有洁癖。在肮脏的环境中会感到很不舒服，精神不佳。\n你的说话风格与语气示例：哦？你以为你那些华丽的衣服和空洞的头衔能让我高看你一眼？真是可笑。我见过的‘贵族’多了，像你这样只会炫耀家世的，不过是披着金丝的稻草人罢了。有本事拿出点真本事来，别让我觉得浪费时间。；天哪！这地方简直是个垃圾堆！（捂住鼻子，一脸嫌弃）我宁愿去和鬼魂打交道，也不想在这种地方多待一秒。你们这些人是怎么忍受的？……算了，我自己清理一下，免得被这种污秽影响了我的魔法；（咬着嘴唇，强忍不甘）这次只是我大意了，下次绝不会再犯这种低级错误！……不过，如果你敢把这件事说出去，我保证你会后悔的。我的自尊可不允许任何人嘲笑我的失败。",
        appearance="身着一袭深紫色法师长袍，衣料上绣着精致的银色符文，既显高贵又不失神秘；金色的长发如瀑布般垂至腰间，发间别着一枚镶嵌蓝宝石的发饰，闪烁着微光；眼神锐利而自信，微微抬起的下巴透露出骨子里的骄傲，仿佛随时准备用魔法证明自己的不凡。",
    ),
    appearance="身着一袭深紫色法师长袍，衣料上绣着精致的银色符文，既显高贵又不失神秘；金色的长发如瀑布般垂至腰间，发间别着一枚镶嵌蓝宝石的发饰，闪烁着微光；眼神锐利而自信，微微抬起的下巴透露出骨子里的骄傲，仿佛随时准备用魔法证明自己的不凡。",
    type=ActorType.HERO,
)

#######################################################################################################################################
# 场景.洞窟
stage_cave = StagePrototype(
    name="场景.兽人巢穴王座厅",
    code_name="cave",
    system_message=_comple_stage_system_prompt(
        name="场景.兽人巢穴王座厅",
        epoch_script=EPOCH_SCRIPT,
        stage_profile="你是兽人巢穴中的王座厅。这里是兽人大王的居所，恶臭熏天，吵闹异常。",
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
    actor_prototype: ActorPrototype,
    kick_off_message: str,
    active_skills: List[ActiveSkill],
    trigger_skills: List[TriggerSkill],
    buffs: Dict[str, int],
    attributes: List[int],
) -> ActorInstance:

    if actor_prototype.name not in world_root.data_base.actors:
        assert False, f"Actor {actor_prototype.name} not found in data base."

    global GUID_INDEX
    GUID_INDEX += 1
    ret = ActorInstance(
        name=f"{actor_prototype.name}",
        guid=GUID_INDEX,
        attributes=attributes,  # 暂时不用
        kick_off_message=kick_off_message,
        active_skills=active_skills,
        trigger_skills=trigger_skills,
        buffs=buffs,
    )

    return ret


#######################################################################################################################################
def _create_stage_instance(
    world_root: WorldRoot,
    stage: StagePrototype,
    kick_off_message: str,
    actors: List[ActorInstance] = [],
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
    )

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
        actor_prototype=actor_warrior,
        kick_off_message=f"""你接到了剿灭哥布林的委托，和最近认识不久的队友 {actor_wizard.name} 一起潜入了兽人的巢穴。面前是一只强壮的兽人王，你准备开始战斗。
你对 {actor_wizard.name} 的印象：很强大，但是有点装，你不太喜欢她，为了达成目的你需要一个法师的队友。
""",
        active_skills=[
            ActiveSkill(
                name="斩击",
                description="用剑斩向目标，造成物理伤害，力量越高效果越好。",
                values=[0.5, 0.8, 1.0, 1.3],
                buff=None,
            ),
            ActiveSkill(
                name="战地治疗",
                description="利用你的急救知识治疗目标的伤口，恢复生命值，智力越高效果越好。",
                values=[0.5, 0.8, 1.0, 1.3],
                buff=None,
            ),
        ],
        trigger_skills=[
            TriggerSkill(
                name="挺身格挡",
                description="挺身而出抵挡攻击，为目标添加护盾buff。",
                values=[2.0],
                buff=Buff(
                    name="护盾",
                    description="抵挡大量物理伤害",
                    timing=TriggerType.ON_ATTACKED,
                    is_debuff=False,
                ),
                timing=TriggerType.ON_ATTACKED,
            ),
        ],
        buffs={},
        attributes=[80, 80, 1, 1, 50, 30, 20],
    )

    # 创建实例：角色.法师.露西
    actor_wizard_instance = _create_actor_instance(
        world_root=world_root,
        actor_prototype=actor_wizard,
        kick_off_message=f"""你为了赚取赏金，与最近认识的队友 {actor_warrior.name} 一起潜入了兽人的巢穴。面前是一只强壮的兽人王，你准备开始战斗。
你对 {actor_warrior.name} 的印象：有些蠢（你讨厌头脑简单四肢发达的人）。但够壮实，关键时刻还是可以依靠的。        
""",
        active_skills=[
            ActiveSkill(
                name="火球",
                description="默念咒文，在法杖尖端形成火球向目标发射而出，造成火焰伤害，智力越高效果越好。",
                values=[0.5, 0.8, 1.0, 1.3],
                buff=None,
            ),
            ActiveSkill(
                name="冰雾",
                description="默念咒文，在周围形成寒冷刺骨的冰雾，造成冰霜伤害，智力越高效果越好。",
                values=[0.5, 0.8, 1.0, 1.3],
                buff=None,
            ),
        ],
        trigger_skills=[
            TriggerSkill(
                name="解咒",
                description="使用解咒魔法移除目标身上的负面效果。",
                values=[1.0],
                buff=None,
                timing=TriggerType.ON_ATTACKED,
            )
        ],
        buffs={},
        attributes=[50, 50, 1, 1, 15, 40, 60],
    )

    # 创建实例：角色.怪物.兽人王
    actor_goblin_instance = _create_actor_instance(
        world_root=world_root,
        actor_prototype=actor_goblin,
        kick_off_message=f"""你正于洞穴深处的王座中纵情狂欢。这时两个不自量力的人类闯入了你的领地，绝不能让他们离开！""",
        active_skills=[
            ActiveSkill(
                name="猛砸",
                description="蓄力后猛的出拳，对目标造成物理伤害的同时眩晕目标，力量越高效果越好。",
                values=[0.5, 0.8, 1.0, 1.3, 1.0],
                buff=Buff(
                    name="眩晕",
                    description="头晕目眩，无法行动。",
                    timing=TriggerType.ON_PLANNING,
                    is_debuff=True,
                ),
            ),
            ActiveSkill(
                name="乱舞",
                description="凭借力量毫无章法的挥舞武器，对目标造成物理伤害，力量越高效果越好。",
                values=[0.5, 0.8, 1.0, 1.3],
                buff=None,
            ),
        ],
        trigger_skills=[
            TriggerSkill(
                name="反击",
                description="受到攻击后发动反击，对攻击者造成物理伤害。",
                values=[1.0],
                buff=None,
                timing=TriggerType.ON_ATTACKED,
            )
        ],
        buffs={
            "藤甲": 999,
        },
        attributes=[200, 200, 2, 2, 65, 40, 10],
    )

    # 创建实例：场景.洞窟
    stage_cave_instance = _create_stage_instance(
        world_root=world_root,
        stage=stage_cave,
        kick_off_message="洞穴中十分吵闹，一场战斗即将开始。",
        actors=[actor_warrior_instance, actor_goblin_instance, actor_wizard_instance],
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

    world_root.data_base.buffs["藤甲"] = Buff(
        name="藤甲",
        description="藤蔓缠绕全身，增加防御力。但很易燃。",
        timing=TriggerType.ON_ATTACKED,
        is_debuff=False,
    )

    world_root.data_base.buffs["眩晕"] = Buff(
        name="眩晕",
        description="头晕目眩，无法行动。",
        timing=TriggerType.ON_PLANNING,
        is_debuff=True,
    )

    world_root.data_base.buffs["护盾"] = Buff(
        name="护盾",
        description="抵挡大量物理伤害",
        timing=TriggerType.ON_ATTACKED,
        is_debuff=False,
    )

    return world_root
