"""
地下城关卡转换和推进模块

管理地下城的完整生命周期，包括进入、推进和退出流程。
协调关卡索引管理、场景传送、战斗初始化和状态清理等核心流程。
"""

import random
from typing import List, Set
from loguru import logger
from ..game.tcg_game import TCGGame
from ..models import (
    Dungeon,
    DungeonComponent,
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
def _select_expedition_members(tcg_game: TCGGame, dungeon: Dungeon) -> Set[Entity]:
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
    other_allies: List[Entity] = []

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

    for expedition_ally in expedition_members:
        expedition_ally.replace(
            ExpeditionMemberComponent,
            expedition_ally.name,
            dungeon.name,
        )
        logger.debug(
            f"将 {expedition_ally.name} 加入远征队，目标地下城：{dungeon.name}"
        )

    return expedition_members


###################################################################################################################################################################
def _enter_dungeon_stage(
    tcg_game: TCGGame, dungeon: Dungeon, expedition_entities: Set[Entity]
) -> bool:
    """
    进入地下城关卡并初始化战斗环境

    协调关卡进入流程：验证前置条件、生成叙事消息、执行场景传送、设置战斗环境。

    Args:
        tcg_game: TCG游戏实例
        dungeon: 地下城实例
        expedition_entities: 远征队成员实体集合

    Returns:
        bool: 是否成功进入关卡
    """
    # 验证远征队非空
    if len(expedition_entities) == 0:
        logger.error("没有远征队成员不能进入地下城!")
        return False

    # 1. 验证前置条件 - 获取当前关卡数据
    stage_model = dungeon.get_current_stage()
    assert stage_model is not None, f"{dungeon.name} 地下城关卡数据异常！"

    # 2. 获取关卡实体
    stage_entity = tcg_game.get_stage_entity(stage_model.name)
    assert stage_entity is not None, f"{stage_model.name} 没有对应的stage实体！"

    assert stage_entity.has(
        DungeonComponent
    ), f"{stage_model.name} 没有DungeonComponent组件！"

    # 3. 生成并发送传送提示消息
    trans_message = _generate_dungeon_entry_message(
        dungeon.name,
        stage_entity.name,
        dungeon.current_room_index == 0,
        dungeon.description,
    )

    for expedition_member in expedition_entities:
        # 添加上下文！
        # 根据是否为首次进入，设置不同的生命周期标记
        if dungeon.current_room_index == 0:
            # 首次进入：仅地下城名称
            tcg_game.add_human_message(
                expedition_member, trans_message, dungeon_lifecycle_entry=dungeon.name
            )

        else:

            # 关卡推进：地下城名称:关卡名称
            tcg_game.add_human_message(
                expedition_member,
                trans_message,
                dungeon_lifecycle_stage_advance=f"{dungeon.name}:{stage_entity.name}",
            )

        if expedition_member.has(DeathComponent):

            logger.info(f"移除死亡组件: {expedition_member.name}")
            expedition_member.remove(DeathComponent)

            # 恢复生命值1
            assert expedition_member.has(CombatStatsComponent)
            combat_stats = expedition_member.get(CombatStatsComponent)
            combat_stats.stats.hp = 1
            logger.info(
                f"恢复生命值: {expedition_member.name} 生命值 = {combat_stats.stats.hp}/{combat_stats.stats.max_hp}"
            )

    # 4. 执行场景传送
    tcg_game.stage_transition(expedition_entities, stage_entity)

    # 6. 初始化战斗状态
    dungeon.start_combat(Combat(name=stage_entity.name))

    # 7. 清除手牌组件
    tcg_game.clear_hands()
    return True


###################################################################################################################################################################
def setup_dungeon(tcg_game: TCGGame, dungeon: Dungeon) -> tuple[bool, str]:
    """创建地下城的全部游戏实体（敌人和场景）并初始化索引。（幂等）

    若实体已创建（dungeon.setup_entities == True），直接返回成功，不重复操作。
    仅在 dungeon.current_room_index == -1（尚未进入）或 0（已 setup 未进入）时允许调用。
    地下城进行中（current_room_index > 0）视为真正的错误。

    Args:
        tcg_game: TCG游戏实例
        dungeon: 地下城实例

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """
    if len(dungeon.rooms) == 0:
        error_msg = f"setup_dungeon 失败: {dungeon.name} 没有关卡数据"
        logger.error(error_msg)
        return False, error_msg

    # 索引 >= 0 表示地下城已进入，不允许重新 setup
    if dungeon.current_room_index >= 0:
        error_msg = (
            f"setup_dungeon 失败: {dungeon.name} 地下城已进入 "
            f"(current_room_index={dungeon.current_room_index})"
        )
        logger.error(error_msg)
        return False, error_msg

    assert (
        not tcg_game.is_player_in_dungeon_stage
    ), "setup_dungeon 失败: 玩家已在地下城场景中！"

    # 幂等：实体已创建则跳过
    if dungeon.setup_entities:
        logger.debug(f"setup_dungeon: {dungeon.name} 实体已创建，跳过")
        return True, f"地下城实体已存在，跳过创建: {dungeon.name}"

    # 创建地下城实体（内部将 setup_entities 置 True），索引保持 -1
    tcg_game.setup_dungeon_entities(dungeon)

    logger.info(f"setup_dungeon 完成: {dungeon.name}")
    return True, f"地下城实体创建完成: {dungeon.name}"


###################################################################################################################################################################
def enter_dungeon_first_stage(tcg_game: TCGGame, dungeon: Dungeon) -> tuple[bool, str]:
    """组建远征队并传送至地下城第一关，启动首个战斗序列。

    必须在 setup_dungeon 成功后调用（依赖 dungeon.setup_entities == True）。
    负责选择远征队成员（玩家 + 最多1个随机盟友）、执行场景传送、初始化战斗状态。

    Args:
        tcg_game: TCG游戏实例
        dungeon: 地下城实例（须已完成 setup_dungeon）

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """
    if not dungeon.setup_entities:
        error_msg = f"enter_dungeon_first_stage 失败: {dungeon.name} 实体尚未创建，请先调用 setup_dungeon"
        logger.error(error_msg)
        return False, error_msg

    if dungeon.current_room_index != -1:
        error_msg = (
            f"enter_dungeon_first_stage 失败: {dungeon.name} "
            f"current_room_index={dungeon.current_room_index}，期望值为 -1（已 setup 未进入）"
        )
        logger.error(error_msg)
        return False, error_msg

    # 确保全局不存在远征队成员（无人正在参与远征）
    expedition_members = tcg_game.get_group(
        Matcher(all_of=[ExpeditionMemberComponent])
    ).entities
    assert len(expedition_members) == 0, (
        f"enter_dungeon_first_stage: 进入前必须无远征队成员，"
        f"当前存在 {len(expedition_members)} 个"
    )

    # 推进索引（-1 → 0），_enter_dungeon_stage 依赖此值判断首次进入消息
    dungeon.current_room_index = 0

    # 选择远征队成员（玩家 + 最多1个随机盟友）
    expedition_member_entities = _select_expedition_members(tcg_game, dungeon)

    # 传送并初始化战斗
    if not _enter_dungeon_stage(tcg_game, dungeon, expedition_member_entities):
        error_msg = f"enter_dungeon_first_stage 失败: 无法进入第一关 {dungeon.name}"
        logger.error(error_msg)
        return False, error_msg

    logger.info(f"enter_dungeon_first_stage 完成: {dungeon.name}")
    return True, f"成功进入地下城: {dungeon.name}"


###################################################################################################################################################################
def advance_to_next_stage(tcg_game: TCGGame, dungeon: Dungeon) -> None:
    """
    推进到地下城的下一个关卡

    将地下城索引推进到下一关，然后让所有远征队成员进入该关卡。

    Args:
        tcg_game: TCG游戏实例
        dungeon: 地下城实例
    """

    if not tcg_game.current_dungeon.is_post_combat:
        logger.error("当前不处于战斗后状态，无法推进地下城关卡")
        return

    if tcg_game.current_dungeon.is_lost:
        logger.info("英雄失败，应该返回营地！！！！")
        return

    if not tcg_game.current_dungeon.is_won:
        assert False, "不可能出现的情况！"

    # 1. 推进地下城索引到下一关
    next_stage = dungeon.advance_to_next_stage()
    if next_stage is None:
        logger.error("地下城前进失败，没有更多关卡")
        # assert False, "地下城前进失败，没有更多关卡"  # 不可能发生！
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
def exit_dungeon_and_return_home(tcg_game: TCGGame, dungeon: Dungeon) -> None:
    """
    退出地下城并将角色传送回家园

    将远征队成员传送回家园、清理地下城数据、重置战斗状态并解散远征队。
    玩家传送到专属场景，盟友传送到普通家园场景。

    本函数用于所有地下城结束场景：战斗胜利、战斗失败、主动撤退等。
    函数是中性的，不区分成功或失败，只负责清理和返回流程。

    Args:
        tcg_game: TCG游戏实例
        dungeon: 地下城实例
    """
    cs = tcg_game.current_dungeon
    logger.debug(
        f"[return_home] 入参 dungeon={dungeon.name!r}, "
        f"world.dungeon={tcg_game._world.dungeon.name!r}, "
        f"is_ongoing={cs.is_ongoing}, is_post_combat={cs.is_post_combat}, "
        f"is_won={cs.is_won}, is_lost={cs.is_lost}"
    )

    # 严格要求：只能在战斗后状态退出（无论胜负）
    if not cs.is_post_combat:
        logger.error(
            f"当前不处于战斗后状态，无法退出地下城！"
            f"必须先完成战斗进入 post_combat 状态。"
        )
        return

    # 1. 验证并获取远征队成员
    expedition_entities = tcg_game.get_group(
        Matcher(all_of=[ExpeditionMemberComponent])
    ).entities.copy()
    logger.debug(
        f"[return_home] 远征队成员({len(expedition_entities)}): "
        f"{[e.name for e in expedition_entities]}"
    )
    assert len(expedition_entities) > 0, "没有找到远征队成员"

    # 2-3. 获取并分类家园场景实体
    player_only_stages: Set[Entity] = tcg_game.get_group(
        Matcher(all_of=[HomeComponent, PlayerOnlyStageComponent])
    ).entities.copy()
    logger.debug(
        f"[return_home] 玩家专属家园场景({len(player_only_stages)}): "
        f"{[e.name for e in player_only_stages]}"
    )
    assert len(player_only_stages) == 1, "必须存在且仅存在一个玩家专属家园场景！"

    regular_home_stages: Set[Entity] = tcg_game.get_group(
        Matcher(all_of=[HomeComponent], none_of=[PlayerOnlyStageComponent])
    ).entities.copy()
    logger.debug(
        f"[return_home] 普通家园场景({len(regular_home_stages)}): "
        f"{[e.name for e in regular_home_stages]}"
    )

    # 4. 生成并发送返回提示消息，传送远征队成员回家
    player_only_stage = next(iter(player_only_stages))
    regular_home_stage = (
        next(iter(regular_home_stages)) if regular_home_stages else None
    )

    for expedition_entity in expedition_entities:
        is_player = expedition_entity.has(PlayerComponent)
        dest_stage = player_only_stage if is_player else regular_home_stage
        current_stage_entity = tcg_game.resolve_stage_entity(expedition_entity)
        current_stage_name = (
            current_stage_entity.name if current_stage_entity else "None"
        )
        logger.debug(
            f"[return_home] 传送 {expedition_entity.name} | is_player={is_player} | "
            f"当前场景={current_stage_name!r} → 目标场景={dest_stage.name if dest_stage else 'None'!r}"
        )
        if dest_stage is None:
            logger.warning(
                f"盟友 {expedition_entity.name} 无普通家园场景可返回，跳过传送"
            )
            continue

        tcg_game.add_human_message(
            expedition_entity,
            _generate_return_home_message(dungeon.name, dest_stage.name),
            dungeon_lifecycle_completion=dungeon.name,
        )
        tcg_game.stage_transition({expedition_entity}, dest_stage)

        after_stage_entity = tcg_game.resolve_stage_entity(expedition_entity)
        after_stage_name = after_stage_entity.name if after_stage_entity else "None"
        logger.debug(
            f"[return_home] 传送后 {expedition_entity.name} 当前场景={after_stage_name!r}"
        )

    # 5. 清理地下城数据
    logger.debug(
        f"[return_home] 开始 teardown_dungeon_entities: dungeon={dungeon.name!r}"
    )
    tcg_game.teardown_dungeon_entities(dungeon)
    tcg_game._world.dungeon = Dungeon(name="", rooms=[], description="")
    logger.debug("[return_home] teardown_dungeon_entities 完成，dungeon 已重置")

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

        # 解散远征队，移除ExpeditionMemberComponent组件
        assert expedition_entity.has(ExpeditionMemberComponent)
        expedition_entity.remove(ExpeditionMemberComponent)
        logger.info(f"从远征队移除: {expedition_entity.name}")

    # 7. 最终场景确认
    for expedition_entity in expedition_entities:
        final_stage = tcg_game.resolve_stage_entity(expedition_entity)
        logger.debug(
            f"[return_home] 最终确认 {expedition_entity.name} 场景={final_stage.name if final_stage else 'None'!r}"
        )

    # 7. 清除手牌组件
    tcg_game.clear_hands()

    # 8. 将运行时实体状态同步回序列化字段（stage_transition 只更新内存，必须显式 flush）
    tcg_game.flush_entities()


###################################################################################################################################################################
