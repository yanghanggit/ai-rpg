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
def test_world1(world_root: WorldRoot) -> WorldRoot:

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
        appearance="一把普通的铁剑",
        insight="一把普通的铁剑",
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
        appearance="一把普通的短剑",
        insight="一把普通的短剑",
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

    return world_root


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
