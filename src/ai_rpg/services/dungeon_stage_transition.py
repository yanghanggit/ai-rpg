"""
地下城关卡转换和推进模块

该模块负责管理地下城的完整生命周期，包括进入、推进和退出流程：
- 首次进入地下城（initialize_dungeon_first_entry）
- 进入指定关卡（enter_dungeon_stage）
- 推进到下一关卡（advance_to_next_stage）
- 完成冒险并返回家园（complete_dungeon_and_return_home）

这些函数协调了关卡索引管理、场景传送、战斗初始化、状态清理等核心流程。
"""

from typing import Dict, Set
from loguru import logger
from ..game.tcg_game import TCGGame
from ..models import (
    Dungeon,
    DungeonComponent,
    KickOffComponent,
    Combat,
    AllyComponent,
)
from ..entitas import Matcher, Entity
from ..demo.stage_ally_manor import create_stage_monitoring_house


###################################################################################################################################################################
def _generate_dungeon_entry_message(
    dungeon_stage_name: str, is_first_stage: bool
) -> str:
    """生成地下城进入提示消息

    Args:
        dungeon_stage_name: 地下城关卡名称
        is_first_stage: 是否为首个关卡（索引为0）

    Returns:
        格式化的进入提示消息
    """
    if is_first_stage:
        return f"""# 提示！准备进入地下城: {dungeon_stage_name}"""
    else:
        return f"""# 提示！准备进入下一个地下城: {dungeon_stage_name}"""


###################################################################################################################################################################
def _format_stage_actors_info(actors_appearances_mapping: Dict[str, str]) -> str:
    """格式化场景内角色信息为文本

    Args:
        actors_appearances_mapping: 角色名称到外观描述的映射字典

    Returns:
        格式化后的角色信息文本，如果没有角色则返回"无"
    """
    actors_appearances_info = []
    for actor_name, appearance in actors_appearances_mapping.items():
        actors_appearances_info.append(f"{actor_name}: {appearance}")

    if len(actors_appearances_info) == 0:
        return "无"

    return "\n\n".join(actors_appearances_info)


###################################################################################################################################################################
def _enhance_kickoff_with_actors(
    original_content: str, actors_appearances_mapping: Dict[str, str]
) -> str:
    """增强KickOff消息，添加场景内角色信息

    Args:
        original_content: 原始KickOff消息内容
        actors_appearances_mapping: 角色名称到外观描述的映射字典

    Returns:
        增强后的KickOff消息内容
    """
    actors_info = _format_stage_actors_info(actors_appearances_mapping)

    return f"""{original_content}
    
**场景内角色**  

{actors_info}"""


###################################################################################################################################################################
def enter_dungeon_stage(
    tcg_game: TCGGame, dungeon: Dungeon, ally_entities: Set[Entity]
) -> bool:
    """
    进入地下城关卡并初始化战斗环境

    协调整个关卡进入流程：验证前置条件、生成叙事消息、执行场景传送、
    设置战斗环境和启动战斗序列。

    Args:
        tcg_game: TCG游戏实例
        dungeon: 地下城实例
        ally_entities: 参与进入的盟友实体集合

    Returns:
        bool: 是否成功进入关卡并完成初始化

    Note:
        - 用于首次进入(index=0)和后续关卡推进(index>0)
        - 调用者: initialize_dungeon_first_entry, advance_to_next_stage
    """
    # 验证盟友队伍非空
    if len(ally_entities) == 0:
        logger.error("没有盟友不能进入地下城!")
        return False

    # 1. 验证前置条件 - 获取当前关卡数据
    current_dungeon_stage = dungeon.get_current_stage()
    assert current_dungeon_stage is not None, f"{dungeon.name} 地下城关卡数据异常！"

    # 2. 获取关卡实体
    dungeon_stage_entity = tcg_game.get_stage_entity(current_dungeon_stage.name)
    assert (
        dungeon_stage_entity is not None
    ), f"{current_dungeon_stage.name} 没有对应的stage实体！"
    assert dungeon_stage_entity.has(
        DungeonComponent
    ), f"{current_dungeon_stage.name} 没有DungeonComponent组件！"

    logger.debug(
        f"{dungeon.name} = [{dungeon.current_stage_index}]关为：{dungeon_stage_entity.name}，可以进入"
    )

    # 3. 生成并发送传送提示消息
    trans_message = _generate_dungeon_entry_message(
        dungeon_stage_entity.name, dungeon.current_stage_index == 0
    )

    for ally_entity in ally_entities:
        # 添加上下文！
        tcg_game.add_human_message(ally_entity, trans_message)

    # 4. 执行场景传送
    tcg_game.stage_transition(ally_entities, dungeon_stage_entity)

    # 5. 设置KickOff消息并添加场景角色信息
    stage_kickoff_comp = dungeon_stage_entity.get(KickOffComponent)
    assert (
        stage_kickoff_comp is not None
    ), f"{dungeon_stage_entity.name} 没有KickOffMessageComponent组件！"

    # 获取场景内角色的外貌信息并增强KickOff消息
    actors_appearances_mapping: Dict[str, str] = tcg_game.get_stage_actor_appearances(
        dungeon_stage_entity
    )

    enhanced_kickoff_content = _enhance_kickoff_with_actors(
        stage_kickoff_comp.content, actors_appearances_mapping
    )

    dungeon_stage_entity.replace(
        KickOffComponent,
        stage_kickoff_comp.name,
        enhanced_kickoff_content,
    )

    # 6. 初始化战斗状态
    dungeon.combat_sequence.start_combat(Combat(name=dungeon_stage_entity.name))

    # 7. 清除手牌组件
    tcg_game.clear_hands()
    return True


###################################################################################################################################################################
def initialize_dungeon_first_entry(tcg_game: TCGGame, dungeon: Dungeon) -> bool:
    """
    初始化地下城首次进入，仅在首次进入时调用（current_stage_index < 0）

    Args:
        tcg_game: TCG游戏实例
        dungeon: 要初始化的地下城实例

    Returns:
        bool: 是否成功初始化并进入第一个关卡

    Note:
        此函数仅处理首次进入场景，后续关卡推进使用 advance_to_next_stage
    """
    # 验证是否为首次进入（索引必须为-1）
    if dungeon.current_stage_index >= 0:
        logger.error(
            f"initialize_dungeon_first_entry: 索引异常 = {dungeon.current_stage_index}, "
            f"期望值为 -1（首次进入标记）"
        )
        return False

    # 初始化地下城状态
    dungeon.current_stage_index = 0
    tcg_game.create_dungeon_entities(dungeon)

    # 获取所有盟友实体并推进到第一关
    ally_entities = tcg_game.get_group(Matcher(all_of=[AllyComponent])).entities.copy()
    return enter_dungeon_stage(tcg_game, dungeon, ally_entities)


###################################################################################################################################################################
def advance_to_next_stage(tcg_game: TCGGame, dungeon: Dungeon) -> None:
    """
    推进到地下城的下一个关卡

    该函数协调地下城关卡推进流程：先将地下城索引推进到下一关，
    然后让所有盟友实体进入该关卡并初始化战斗环境。

    Args:
        tcg_game: TCG游戏实例
        dungeon: 要推进的地下城实例

    Returns:
        bool: 是否成功推进到下一关卡
            - True: 成功推进并进入下一关
            - False: 推进失败（没有更多关卡）

    Note:
        - 用于战斗胜利后继续推进到下一关卡
        - 调用者: _handle_advance_next_dungeon
        - 调用链: advance_to_next_stage → enter_dungeon_stage
    """
    # 1. 推进地下城索引到下一关
    if not dungeon.advance_to_next_stage():
        logger.error("地下城前进失败，没有更多关卡")
        assert False, "地下城前进失败，没有更多关卡"  # 不可能发生！
        return

    # 2. 获取所有盟友实体
    ally_entities = tcg_game.get_group(Matcher(all_of=[AllyComponent])).entities.copy()

    # 3. 进入下一关卡
    enter = enter_dungeon_stage(tcg_game, dungeon, ally_entities)
    assert enter, "进入下一关卡失败！"


###################################################################################################################################################################
def complete_dungeon_and_return_home(tcg_game: TCGGame) -> None:
    """
    完成地下城冒险并返回家园

    该函数协调地下城结束流程：传送盟友回家、清理地下城数据、
    恢复盟友战斗状态。用于地下城冒险结束后的收尾工作。

    主要操作：
    1. 验证并获取盟友和家园实体
    2. 生成返回提示消息
    3. 执行场景传送到家园
    4. 清理地下城实体和数据
    5. 恢复盟友状态（移除死亡、满血、清空效果）

    Args:
        tcg_game: TCG游戏实例

    Note:
        - 用于战斗结束后返回家园
        - 调用者: dungeon_trans_home API
        - 会完全重置地下城状态和盟友战斗状态
    """
    # 导入必要的模型
    from ..models import HomeComponent, DeathComponent, CombatStatsComponent

    # 1. 验证并获取盟友实体
    ally_entities = tcg_game.get_group(Matcher(all_of=[AllyComponent])).entities
    assert len(ally_entities) > 0, "没有找到盟友实体"

    # 2. 验证并获取家园场景实体
    home_stage_entities = tcg_game.get_group(
        Matcher(all_of=[HomeComponent])
    ).entities.copy()
    assert len(home_stage_entities) > 0, "没有找到家园场景实体"

    # TODO 移除监视之屋（玩家专属场景）
    monitoring_house_name = create_stage_monitoring_house().name
    stages_to_remove = set()
    for stage_entity in home_stage_entities:
        if stage_entity.name == monitoring_house_name:
            stages_to_remove.add(stage_entity)
    home_stage_entities -= stages_to_remove

    assert len(home_stage_entities) > 0, "没有找到有效的家园场景实体!"
    home_stage = next(iter(home_stage_entities))

    # 3. 生成并发送返回提示消息
    return_prompt = f"""# 提示！冒险结束，将要返回: {home_stage.name}"""
    for ally_entity in ally_entities:
        tcg_game.add_human_message(ally_entity, return_prompt)

    # 4. 执行场景传送到家园
    tcg_game.stage_transition(ally_entities, home_stage)

    # 5. 清理地下城数据
    tcg_game.destroy_dungeon_entities(tcg_game.world.dungeon)
    tcg_game._world.dungeon = Dungeon(name="", stages=[])

    # 6. 恢复所有盟友的战斗状态
    for ally_entity in ally_entities:
        # 移除死亡组件
        if ally_entity.has(DeathComponent):
            logger.info(f"移除死亡组件: {ally_entity.name}")
            ally_entity.remove(DeathComponent)

        # 恢复生命值至满血
        assert ally_entity.has(CombatStatsComponent)
        combat_stats = ally_entity.get(CombatStatsComponent)
        combat_stats.stats.hp = combat_stats.stats.max_hp
        logger.info(
            f"恢复满血: {ally_entity.name} 生命值 = {combat_stats.stats.hp}/{combat_stats.stats.max_hp}"
        )

        # 清空所有状态效果
        combat_stats.status_effects.clear()
        logger.info(f"清空状态效果: {ally_entity.name}")


###################################################################################################################################################################
