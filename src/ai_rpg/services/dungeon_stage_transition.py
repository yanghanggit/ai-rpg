"""
地下城关卡转换和推进模块

管理地下城的完整生命周期，包括进入、推进和退出流程。
协调关卡索引管理、场景传送、战斗初始化和状态清理等核心流程。
"""

import random
from typing import Dict, Set
from loguru import logger
from ..game.tcg_game import TCGGame
from ..models import (
    Dungeon,
    DungeonComponent,
    KickOffComponent,
    Combat,
    AllyComponent,
    ExpeditionMemberComponent,
    PlayerComponent,
    PlayerOnlyStageComponent,
    HomeComponent,
    DeathComponent,
    CombatStatsComponent,
)
from ..entitas import Matcher, Entity


###################################################################################################################################################################
def _generate_dungeon_entry_message(
    dungeon_name: str,
    dungeon_stage_name: str,
    is_first_stage: bool,
    dungeon_description: str,
) -> str:
    """生成地下城进入提示消息

    Args:
        dungeon_name: 地下城名称
        dungeon_stage_name: 地下城关卡名称
        is_first_stage: 是否为首个关卡
        dungeon_description: 地下城任务说明

    Returns:
        str: 格式化的进入提示消息
    """
    if is_first_stage:
        return f"""# 提示！进入地下城：{dungeon_name}，开始关卡场景：{dungeon_stage_name}

## 任务说明

{dungeon_description}"""

    else:
        return f"""# 提示！地下城：{dungeon_name}，进入下一关卡场景：{dungeon_stage_name}"""


###################################################################################################################################################################
def _generate_return_home_message(
    dungeon_name: str, destination_stage_name: str
) -> str:
    """生成返回家园的提示消息

    Args:
        dungeon_name: 地下城名称
        destination_stage_name: 目标场景名称

    Returns:
        str: 格式化的返回提示消息
    """
    return f"""# 提示！地下城：{dungeon_name} 结束，返回家园场景：{destination_stage_name}"""


###################################################################################################################################################################
def _format_stage_actors_info(actors_appearances_mapping: Dict[str, str]) -> str:
    """格式化场景内角色信息为文本

    Args:
        actors_appearances_mapping: 角色名称到外观描述的映射

    Returns:
        str: 格式化后的角色信息文本
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
        original_content: 原KickOff消息内容
        actors_appearances_mapping: 角色名称到外观描述的映射

    Returns:
        str: 增强后的KickOff消息内容
    """
    actors_info = _format_stage_actors_info(actors_appearances_mapping)

    return f"""{original_content}
    
**场景内角色**  

{actors_info}"""


###################################################################################################################################################################
def _select_expedition_members(tcg_game: TCGGame) -> Set[Entity]:
    """选择参与地下城远征的队伍成员

    从所有盟友中选择远征队成员，规则：
    1. 必须包含玩家角色（PlayerComponent）
    2. 从剩余盟友中随机选择1个同伴
    3. 远征队最少1人（玩家），最多2人（玩家+1个同伴）

    Args:
        tcg_game: TCG游戏实例

    Returns:
        远征队成员实体集合，包含玩家和最多1个随机选择的盟友
    """
    # 获取所有盟友
    all_allies = tcg_game.get_group(Matcher(all_of=[AllyComponent])).entities.copy()

    # 1. 找到玩家实体（必须）并分离其他盟友
    player_entity = None
    other_allies = []

    for ally in all_allies:
        if ally.has(PlayerComponent):
            player_entity = ally
        else:
            other_allies.append(ally)

    assert player_entity is not None, "必须存在一个玩家实体"

    # 2. 从其他盟友中随机选择1个
    expedition_members = {player_entity}
    logger.info(f"玩家 {player_entity.name} 将参与远征")

    if len(other_allies) > 0:
        selected_ally = random.choice(other_allies)
        expedition_members.add(selected_ally)
        logger.info(f"随机选择 {selected_ally.name} 加入远征队")
    else:
        logger.warning("没有其他盟友可以加入远征队，玩家将独自冒险")

    return expedition_members


###################################################################################################################################################################
def _enter_dungeon_stage(
    tcg_game: TCGGame, dungeon: Dungeon, ally_entities: Set[Entity]
) -> bool:
    """
    进入地下城关卡并初始化战斗环境

    协调关卡进入流程：验证前置条件、生成叙事消息、执行场景传送、设置战斗环境。

    Args:
        tcg_game: TCG游戏实例
        dungeon: 地下城实例
        ally_entities: 盟友实体集合

    Returns:
        bool: 是否成功进入关卡
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

    # logger.debug(
    #     f"{dungeon.name} = [{dungeon.current_stage_index}]关为：{dungeon_stage_entity.name}，可以进入"
    # )

    # 3. 生成并发送传送提示消息
    trans_message = _generate_dungeon_entry_message(
        dungeon.name,
        dungeon_stage_entity.name,
        dungeon.current_stage_index == 0,
        dungeon.description,
    )

    for ally_entity in ally_entities:
        # 添加上下文！
        # 根据是否为首次进入，设置不同的生命周期标记
        if dungeon.current_stage_index == 0:
            # 首次进入：仅地下城名称
            tcg_game.add_human_message(
                ally_entity, trans_message, dungeon_lifecycle_entry=dungeon.name
            )

        else:

            # 关卡推进：地下城名称:关卡名称
            tcg_game.add_human_message(
                ally_entity,
                trans_message,
                dungeon_lifecycle_stage_advance=f"{dungeon.name}:{dungeon_stage_entity.name}",
            )

    # 4. 执行场景传送
    tcg_game.stage_transition(ally_entities, dungeon_stage_entity)

    # 5. 设置KickOff消息并添加场景角色信息
    stage_kickoff_comp = dungeon_stage_entity.get(KickOffComponent)
    assert (
        stage_kickoff_comp is not None
    ), f"{dungeon_stage_entity.name} 没有KickOffMessageComponent组件！"

    # 获取场景内角色的外貌信息并增强KickOff消息
    actors_appearances_mapping: Dict[str, str] = (
        tcg_game.get_actor_appearances_on_stage(dungeon_stage_entity)
    )

    enhanced_kickoff_content = _enhance_kickoff_with_actors(
        stage_kickoff_comp.prompt, actors_appearances_mapping
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
    初始化地下城首次进入

    仅在首次进入时调用，设置地下城状态并进入第一个关卡。
    会将所有盟友添加到远征队（ExpeditionMemberComponent）。

    Args:
        tcg_game: TCG游戏实例
        dungeon: 地下城实例

    Returns:
        bool: 是否成功初始化并进入第一个关卡
    """
    # 验证是否为首次进入（索引必须为-1）
    if dungeon.current_stage_index >= 0:
        logger.error(
            f"initialize_dungeon_first_entry: 索引异常 = {dungeon.current_stage_index}, "
            f"期望值为 -1（首次进入标记）"
        )
        return False

    # 确保全局不存在远征队成员（无人正在参与远征）
    expedition_members = tcg_game.get_group(
        Matcher(all_of=[ExpeditionMemberComponent])
    ).entities
    assert len(expedition_members) == 0, (
        f"初始化地下城前必须确保无远征队成员，"
        f"当前存在 {len(expedition_members)} 个远征队成员"
    )

    # 初始化地下城状态
    dungeon.current_stage_index = 0
    tcg_game.setup_dungeon_entities(dungeon)

    # 选择远征队成员（玩家 + 最多1个随机盟友）
    ally_entities = _select_expedition_members(tcg_game)

    # 将选中的成员添加到远征队
    for ally_entity in ally_entities:
        ally_entity.replace(
            ExpeditionMemberComponent,
            ally_entity.name,
            dungeon.name,
        )
        logger.debug(f"将 {ally_entity.name} 加入远征队，目标地下城：{dungeon.name}")

    # 推进到第一关
    return _enter_dungeon_stage(tcg_game, dungeon, ally_entities)


###################################################################################################################################################################
def advance_to_next_stage(tcg_game: TCGGame, dungeon: Dungeon) -> None:
    """
    推进到地下城的下一个关卡

    将地下城索引推进到下一关，然后让所有远征队成员进入该关卡。

    Args:
        tcg_game: TCG游戏实例
        dungeon: 地下城实例
    """
    # 1. 推进地下城索引到下一关
    if not dungeon.advance_to_next_stage():
        logger.error("地下城前进失败，没有更多关卡")
        assert False, "地下城前进失败，没有更多关卡"  # 不可能发生！
        return

    # 2. 获取所有远征队成员
    expedition_entities = tcg_game.get_group(
        Matcher(all_of=[ExpeditionMemberComponent])
    ).entities.copy()
    assert len(expedition_entities) > 0, "没有找到远征队成员"

    # 3. 进入下一关卡
    enter = _enter_dungeon_stage(tcg_game, dungeon, expedition_entities)
    assert enter, "进入下一关卡失败！"


###################################################################################################################################################################
def complete_dungeon_and_return_home(tcg_game: TCGGame) -> None:
    """
    完成地下城冒险并将角色传送回家园

    将远征队成员传送回家园、清理地下城数据、重置战斗状态并解散远征队。
    玩家传送到专属场景，盟友传送到普通家园场景。

    Args:
        tcg_game: TCG游戏实例
    """

    # 1. 验证并获取远征队成员
    expedition_entities = tcg_game.get_group(
        Matcher(all_of=[ExpeditionMemberComponent])
    ).entities.copy()
    assert len(expedition_entities) > 0, "没有找到远征队成员"

    # 2. 验证并获取家园场景实体
    home_stage_entities = tcg_game.get_group(
        Matcher(all_of=[HomeComponent])
    ).entities.copy()
    assert len(home_stage_entities) > 0, "没有找到家园场景实体"

    # 3. 分离玩家专属场景和普通家园场景
    player_only_stages: Set[Entity] = set()
    regular_home_stages: Set[Entity] = set()
    for stage in home_stage_entities:
        if stage.has(PlayerOnlyStageComponent):
            player_only_stages.add(stage)
        else:
            regular_home_stages.add(stage)

    # 这个是必须的。
    assert len(player_only_stages) == 1, "必须存在一个PlayerOnlyStage场景"

    # 提醒一下没有普通家园场景的情况
    if len(regular_home_stages) == 0:
        logger.warning("没有普通家园场景，盟友将无法返回家园")

    # 4. 生成并发送返回提示消息
    dungeon_name = tcg_game.world.dungeon.name
    for expedition_entity in expedition_entities:

        if expedition_entity.has(PlayerComponent):

            # 唯一的玩家传送到专有场景
            player_only_stage = next(iter(player_only_stages))

            # 添加返回消息
            tcg_game.add_human_message(
                expedition_entity,
                _generate_return_home_message(dungeon_name, player_only_stage.name),
                dungeon_lifecycle_completion=dungeon_name,
            )

            # 传送玩家到专有场景
            tcg_game.stage_transition({expedition_entity}, player_only_stage)

        else:

            # 盟友传送到普通家园
            if len(regular_home_stages) > 0:

                # 随机选择一个普通家园场景
                random_home_stage = next(iter(regular_home_stages))

                # 添加返回消息并传送
                tcg_game.add_human_message(
                    expedition_entity,
                    _generate_return_home_message(dungeon_name, random_home_stage.name),
                    dungeon_lifecycle_completion=dungeon_name,
                )

                # 传送盟友
                tcg_game.stage_transition({expedition_entity}, random_home_stage)

    # 5. 清理地下城数据
    tcg_game.teardown_dungeon_entities(tcg_game.world.dungeon)
    tcg_game._world.dungeon = Dungeon(name="", stages=[], description="")

    # 6. 恢复所有远征队成员的战斗状态
    for expedition_entity in expedition_entities:
        # 移除死亡组件
        if expedition_entity.has(DeathComponent):
            logger.info(f"移除死亡组件: {expedition_entity.name}")
            expedition_entity.remove(DeathComponent)

        # 恢复生命值至满血
        assert expedition_entity.has(CombatStatsComponent)
        combat_stats = expedition_entity.get(CombatStatsComponent)
        combat_stats.stats.hp = combat_stats.stats.max_hp
        logger.info(
            f"恢复满血: {expedition_entity.name} 生命值 = {combat_stats.stats.hp}/{combat_stats.stats.max_hp}"
        )

        # 清空所有状态效果
        combat_stats.status_effects.clear()
        logger.info(f"清空状态效果: {expedition_entity.name}")

    # 7. 解散远征队（移除 ExpeditionMemberComponent）
    for expedition_entity in expedition_entities:
        expedition_entity.remove(ExpeditionMemberComponent)
        logger.info(f"从远征队移除: {expedition_entity.name}")

    # 8. 清除手牌组件
    tcg_game.clear_hands()


###################################################################################################################################################################
