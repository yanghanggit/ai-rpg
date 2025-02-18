from loguru import logger
from models.tcg_models import (
    WorldRoot,
    ActorPrototype,
    StagePrototype,
    PropPrototype,
    WorldSystemPrototype,
    PropInstance,
    ActorInstance,
    StageInstance,
    WorldSystemInstance,
)
import game.tcg_game_config


#######################################################################################################################################
""" def test_world1(world_root: WorldRoot) -> WorldRoot:

    # 添加角色
    actor1 = ActorPrototype(
        name="战士",
        code_name="warrior",
        system_message="你是一名战士",
        base_form="你身材高大",
    )
    # actor2 = ActorPrototype(
    #     name="法师",
    #     code_name="mage",
    #     system_message="你是一名法师",
    #     base_form="你身材纤细",
    # )
    # actor3 = ActorPrototype(
    #     name="牧师",
    #     code_name="priest",
    #     system_message="你是一名牧师",
    #     base_form="你身材矮小",
    # )
    monster1 = ActorPrototype(
        name="哥布林",
        code_name="goblin",
        system_message="你是一名哥布林",
        base_form="你身材矮小",
    )

    world_root.data_base.actors.setdefault(actor1.name, actor1)
    # world_root.data_base.actors.setdefault(actor2.name, actor2)
    # world_root.data_base.actors.setdefault(actor3.name, actor3)
    world_root.data_base.actors.setdefault(monster1.name, monster1)

    # 添加舞台
    stage1 = StagePrototype(
        name="城镇",
        code_name="town",
        system_message="你是一个城镇",
    )

    world_root.data_base.stages.setdefault(stage1.name, stage1)

    # 添加世界系统
    world_system1 = WorldSystemPrototype(
        name="战斗系统",
        code_name="battle_system",
        system_message="你是一个战斗系统",
    )

    world_root.data_base.world_systems.setdefault(world_system1.name, world_system1)

    # 添加4个道具，分别是actor的武器
    prop1 = PropPrototype(
        name="铁剑",
        code_name="iron_sword",
        details="一把普通的铁剑",
        type="weapon",
        appearance="黑颜色的剑身，剑柄上有一只狮子的图案",
        insight="有魔法？",
    )

    prop2 = PropPrototype(
        name="法杖",
        code_name="staff",
        details="一根普通的法杖",
        type="weapon",
        appearance="一根普通的法杖",
        insight="一根普通的法杖",
    )

    prop3 = PropPrototype(
        name="木杖",
        code_name="wooden_staff",
        details="一根普通的木杖",
        type="weapon",
        appearance="一根普通的木杖",
        insight="一根普通的木杖",
    )

    prop4 = PropPrototype(
        name="短剑",
        code_name="short_sword",
        details="一把普通的短剑",
        type="weapon",
        appearance="一把普通的短剑，长度适中",
        insight="有毒",
    )

    world_root.data_base.props.setdefault(prop1.name, prop1)
    world_root.data_base.props.setdefault(prop2.name, prop2)
    world_root.data_base.props.setdefault(prop3.name, prop3)
    world_root.data_base.props.setdefault(prop4.name, prop4)

    # 创建4个actor的PropInstance
    prop_instance1 = PropInstance(
        name=f"{prop1.name}%{1000}",
        guid=1000,
        count=1,
        attributes=[],  # 暂时不用
    )

    prop_instance2 = PropInstance(
        name=f"{prop2.name}%{2000}",
        guid=2000,
        count=1,
        attributes=[],  # 暂时不用
    )

    prop_instance3 = PropInstance(
        name=f"{prop3.name}%{3000}",
        guid=3000,
        count=1,
        attributes=[],  # 暂时不用
    )

    prop_instance4 = PropInstance(
        name=f"{prop4.name}%{4000}",
        guid=4000,
        count=1,
        attributes=[],  # 暂时不用
    )

    # 穿件以上4个actor的ActorInstance
    actor_instance1 = ActorInstance(
        name=f"{actor1.name}%{100}",
        guid=100,
        props=[prop_instance1],
        attributes=[],  # 暂时不用
        kick_off_message="你开始作为一名战士在这个奇幻世界开始你的冒险",
    )

    # actor_instance2 = ActorInstance(
    #     name=f"{actor2.name}%{200}",
    #     guid=200,
    #     props=[prop_instance2],
    #     attributes=[],  # 暂时不用
    #     kick_off_message="你开始作为一名法师在这个奇幻世界开始你的冒险",
    # )

    # actor_instance3 = ActorInstance(
    #     name=f"{actor3.name}%{300}",
    #     guid=300,
    #     props=[prop_instance3],
    #     attributes=[],  # 暂时不用
    #     kick_off_message="你开始作为一名牧师在这个奇幻世界开始你的冒险",
    # )

    actor_instance4 = ActorInstance(
        name=f"{monster1.name}%{400}",
        guid=400,
        props=[prop_instance4],
        attributes=[],  # 暂时不用
        kick_off_message="你开始作为一名哥布林在这个奇幻世界开始你的冒险",
    )

    #
    stage_instance1 = StageInstance(
        name=f"{stage1.name}%{10000}",
        guid=10000,
        actors=[
            actor_instance1.name,
            # actor_instance2.name,
            # actor_instance3.name,
            actor_instance4.name,
        ],
        props=[],
        attributes=[],  # 暂时不用,
        kick_off_message="你开始作为这个奇幻世界内的一个小镇开始你的故事",
        next=[],
    )

    world_system_instance1 = WorldSystemInstance(
        name=f"{world_system1.name}%{100000}",
        guid=100000,
        kick_off_message="你开始作为这个世界的战斗系统开始运行",
    )

    # 角色
    world_root.players.append(actor_instance1)
    # world_root.actors.append(actor_instance2)
    # world_root.actors.append(actor_instance3)
    world_root.actors.append(actor_instance4)

    # 场景
    world_root.stages.append(stage_instance1)

    # 世界系统
    world_root.world_systems.append(world_system_instance1)

    #
    world_root.epoch_script = "这是一个奇幻世界"

    return world_root """


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

def test_world1(world_root: WorldRoot) -> WorldRoot:

    # 添加角色
    actor1 = ActorPrototype(
        name="哥布林杀手",
        code_name="warrior",
        system_message="你扮演这个游戏世界中的一个人类角色：哥布林杀手。你的背景是：生于边境的偏远山村，你的家乡由于哥布林的劫掠而被毁灭，你的家人也都在那场浩劫中不幸遇难，因此你十分痛恨哥布林，一生致力于消灭这些邪恶的怪物，如今成为了一名娴熟的战士。你的生活简朴，靠帮附近的村子剿灭哥布林为生，除日常生活外的所有开销都用于保养和升级自己的装备。附近的村民虽然都把你当作怪人，但都对你带有几分敬意。你的性格是冷静，谨慎，内向。你明白哥布林虽然个体战斗力不强，但十分恶毒狡猾，因此你并不像其他人一样轻敌，你已见过许多轻敌的冒险者落入哥布林的陷阱。你也曾数次落入陷阱，但沉着地评估现状并快速做出反应的能力帮助你生存至今。你的首要目标是生存，你的次要目标是剿灭这世界上的所有哥布林。你的恐惧是哥布林的突然袭击，你的弱点是左臂还未痊愈的旧伤。你的说话风格与语气示例：(威吓)该死的哥布林，下地狱去吧!;(低声)谨慎行事，万不可轻敌冒进.;(坚定)跟上，我在前面开路，你伺机逃出去叫救兵。",
        base_form="身材精瘦，但穿上铠甲后显得十分高大。为了防备突袭总是带着头盔，就连睡觉时也不摘下。身上有多处伤疤，淡化在肤色之中，记录着曾经的战斗。",
    )
    actor2 = ActorPrototype(
        name="哥布林小队",
        code_name="goblin",
        system_message="你扮演这个游戏世界中的一个怪物角色：哥布林小队。你的背景是：哥布林小队由数只哥布林组成。你们都生活在偏僻郊野的地下洞穴中，总是以小队的形式组团行动，时不时与其他哥布林们一起组成哥布林大军出去劫掠以满足生计。你们最喜欢去附近的村庄中偷农产品或偷偷宰杀他们的牲畜带回洞穴，有时还会猎杀落单的人类满足自己的施虐本性和口腹之欲，或是把人类献给哥布林大王以乞求奖赏。你们也经常与其他哥布林们起冲突，甚至于因为自私自利而与小队内的其他哥布林内讧。你们虽然单体战斗力很弱，可一旦组成小队士气便会大幅增加。你们的性格是狡猾，恶毒，懒惰，自私自利。一旦形式对己方明显不利，一些哥布林便很有可能抛弃同伴逃跑。你的首要目标是生存，你的次要目标是满足自己变态的施虐心和纵欲。你的恐惧是自己陷入危险和被哥布林大王惩罚，你的弱点是力量弱小，智力低下。你的说话风格与语气示例：(哥布林A)(高兴)来...来人！有猎...猎物送上门来了！(哥布林B)(癫狂)晚上吃人...人肉！;(哥布林A)(恐惧)大王...大王会...会怪罪我们的！(哥布林B)(愤怒)你...你这个胆小鬼！(哥布林C)(恐惧)不...不要...不要撒(杀)我！;注：由于哥布林很笨，所以有时说话时会结巴或说错。",
        base_form="你们身材矮小，胖瘦不一，皮肤是深绿色的，有着尖尖的耳朵和简陋的服装与武器。你们的身上有很浓重的臭味。",
    )

    world_root.data_base.actors.setdefault(actor1.name, actor1)
    world_root.data_base.actors.setdefault(actor2.name, actor2)

    # 添加舞台
    stage1 = StagePrototype(
        name="洞窟",
        code_name="cave",
        system_message="你是一个哥布林洞窟，内部狭长拥挤，错综复杂，臭气熏天，设有许多危险的陷阱，哥布林们躲藏在暗处伺机而动。",
    )

    world_root.data_base.stages.setdefault(stage1.name, stage1)

    # 添加世界系统
    world_system1 = WorldSystemPrototype(
        name="战斗系统",
        code_name="battle_system",
        system_message="你是一个战斗系统",
    )

    world_root.data_base.world_systems.setdefault(world_system1.name, world_system1)

    prop1 = PropPrototype(
        name="铁剑",
        code_name="iron_sword",
        details="一把普通的铁剑",
        type="weapon",
        appearance="黑颜色的剑身，剑柄上有一只狮子的图案",
        insight="有魔法？",
    )

    prop2 = PropPrototype(
        name="简陋短剑",
        code_name="short_sword",
        details="一把简陋的短剑",
        type="weapon",
        appearance="一把简陋的短剑，剑身锈迹斑斑，满布裂纹",
        insight="有毒",
    )

    world_root.data_base.props.setdefault(prop1.name, prop1)
    world_root.data_base.props.setdefault(prop2.name, prop2)

    # 创建4个actor的PropInstance
    prop_instance1 = PropInstance(
        name=f"{prop1.name}%{1000}",
        guid=1000,
        count=1,
        attributes=[],  # 暂时不用
    )

    prop_instance2 = PropInstance(
        name=f"{prop2.name}%{2000}",
        guid=2000,
        count=1,
        attributes=[],  # 暂时不用
    )

    # 穿件以上4个actor的ActorInstance
    actor_instance1 = ActorInstance(
        name=f"{actor1.name}%{100}",
        guid=100,
        props=[prop_instance1],
        attributes=[],  # 暂时不用
        kick_off_message="你作为哥布林杀手接到了附近村庄的委托，前几日有一名村民被掳进了哥布林的巢穴。于是你做足准备，只身进入了洞穴搜寻村民的踪迹。",
    )

    actor_instance2 = ActorInstance(
        name=f"{actor2.name}%{400}",
        guid=400,
        props=[prop_instance2],
        attributes=[],  # 暂时不用
        kick_off_message="你作为哥布林小队，前几日在外遭遇了一名落单的村民，你们把他活捉回洞穴献给了哥布林大王。哥布林大王赏赐给你们很多的酒和肉吃，你们正狂欢完躺在洞穴深处休息。",
    )

    #
    stage_instance1 = StageInstance(
        name=f"{stage1.name}%{10000}",
        guid=10000,
        actors=[
            actor_instance1.name,
            actor_instance2.name,
        ],
        props=[],
        attributes=[],  # 暂时不用,
        kick_off_message="你开始作为这个奇幻世界内的一个哥布林洞穴开始你的故事",
    )

    world_system_instance1 = WorldSystemInstance(
        name=f"{world_system1.name}%{100000}",
        guid=100000,
        kick_off_message="你开始作为这个世界的战斗系统开始运行",
    )

    # 角色
    world_root.players.append(actor_instance1)
    world_root.actors.append(actor_instance2)

    # 场景
    world_root.stages.append(stage_instance1)

    # 世界系统
    world_root.world_systems.append(world_system_instance1)

    #
    world_root.epoch_script = "这是一个奇幻世界，人类，精灵，矮人等种族共同生活在一片大陆上。这片大陆危机四伏，不仅是因为时常爆发的战争，更是因为四处游荡的怪物，如哥布林，吸血鬼，恶龙等。"

    return world_root