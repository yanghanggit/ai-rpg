"""家园动作辅助函数模块

提供家园场景中玩家动作的激活和设置功能，包括说话动作、场景转换和行动计划。
这些函数负责验证前置条件并设置相应的动作组件，实际执行由游戏管道处理。
"""

from loguru import logger
from ..game.tcg_game import TCGGame
from ..models import (
    SpeakAction,
    TransStageAction,
    HomeComponent,
    AllyComponent,
    PlayerComponent,
    ExpeditionRosterComponent,
    PlanAction,
    GenerateDungeonAction,
)
from typing import List, Tuple


###################################################################################################################################################################
def activate_speak_action(
    tcg_game: TCGGame, target: str, content: str
) -> Tuple[bool, str]:
    """
    激活玩家的说话动作，并触发当前场景所有角色的行动计划。

    Args:
        tcg_game: TCG 游戏实例
        target: 说话目标的角色全名
        content: 说话内容

    Returns:
        tuple[bool, str]: (是否成功, 失败时的错误详情)
    """

    if not tcg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法执行说话动作"
        logger.error(f"激活说话动作失败: {error_detail}")
        return False, error_detail

    if not target:
        error_detail = "目标角色名称不能为空"
        logger.error(f"激活说话动作失败: {error_detail}")
        return False, error_detail

    # 验证目标角色存在
    if tcg_game.get_actor_entity(target) is None:
        error_detail = f"目标角色 {target} 不存在"
        logger.error(f"激活说话动作失败: {error_detail}")
        return False, error_detail

    player_entity = tcg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"

    logger.debug(f"激活说话动作: {player_entity.name} -> {target}: {content}")
    player_entity.replace(SpeakAction, player_entity.name, {target: content})
    activate_stage_plan(tcg_game)
    return True, ""


###################################################################################################################################################################
def activate_switch_stage(tcg_game: TCGGame, stage_name: str) -> Tuple[bool, str]:
    """
    激活玩家的场景转换动作，并触发当前场景所有角色的行动计划。

    Args:
        tcg_game: TCG 游戏实例
        stage_name: 目标场景全名

    Returns:
        tuple[bool, str]: (是否成功, 失败时的错误详情)
    """

    if not tcg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法执行说话动作"
        logger.error(f"激活场景转换失败: {error_detail}")
        return False, error_detail

    if not stage_name:
        error_detail = "目标场景名称不能为空"
        logger.error(f"激活场景转换失败: {error_detail}")
        return False, error_detail

    # 验证目标场景存在且为家园场景
    target_stage_entity = tcg_game.get_stage_entity(stage_name)
    if target_stage_entity is None:
        error_detail = f"目标场景 {stage_name} 不存在"
        logger.error(f"激活场景转换失败: {error_detail}")
        return False, error_detail

    if not target_stage_entity.has(HomeComponent):
        error_detail = f"{stage_name} 不是家园场景"
        logger.error(f"激活场景转换失败: {error_detail}")
        return False, error_detail

    player_entity = tcg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"

    # 验证目标场景与当前场景不同
    current_stage_entity = tcg_game.resolve_stage_entity(player_entity)
    assert current_stage_entity is not None, "玩家当前场景实体不存在！"
    if current_stage_entity.name == stage_name:
        error_detail = f"目标场景 {stage_name} 与当前场景相同"
        logger.error(f"激活场景转换失败: {error_detail}")
        return False, error_detail

    logger.debug(f"激活场景转换: {player_entity.name} -> {stage_name}")
    player_entity.replace(TransStageAction, player_entity.name, stage_name)
    activate_stage_plan(tcg_game)
    return True, ""


###################################################################################################################################################################
def activate_stage_plan(tcg_game: TCGGame) -> Tuple[bool, str]:
    """
    为玩家当前场景内所有盟友 NPC 激活行动计划

    获取玩家所在的家园场景，为场景内所有盟友角色添加 PlanAction 组件，
    使其在下一次游戏推进时执行 AI 决策。

    Args:
        tcg_game: TCG 游戏实例

    Returns:
        tuple[bool, str]: (是否成功, 错误详情)
    """

    if not tcg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法执行说话动作"
        logger.error(f"激活行动计划失败: {error_detail}")
        return False, error_detail

    # 获取玩家实体和当前场景实体，验证场景为家园
    player_entity = tcg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"

    # 获取玩家当前场景实体，验证为家园场景
    stage_entity = tcg_game.resolve_stage_entity(player_entity)
    assert stage_entity is not None, "玩家当前场景实体不存在！"
    if not stage_entity.has(HomeComponent):
        error_detail = "当前场景不是家园，无法激活行动计划"
        logger.error(f"激活行动计划失败: {error_detail}")
        return False, error_detail

    # 获取当前场景中的所有角色实体，验证至少有一个角色存在
    actors_in_stage = tcg_game.get_actors_in_stage(player_entity)
    assert len(actors_in_stage) > 0, f"当前场景没有角色，无法激活行动计划！"

    #
    for actor_entity in actors_in_stage:

        assert actor_entity.has(
            AllyComponent
        ), f"角色 {actor_entity.name} 不是盟友，无法激活行动计划！"

        logger.debug(f"为角色 {actor_entity.name} 添加 PlanAction")
        actor_entity.replace(PlanAction, actor_entity.name)

    return True, f"成功为 {len(actors_in_stage)} 个角色添加 PlanAction"


###################################################################################################################################################################
def add_expedition_member(tcg_game: TCGGame, member_name: str) -> Tuple[bool, str]:
    """
    将盟友加入远征队名单。

    Args:
        tcg_game: TCG 游戏实例
        member_name: 要加入名单的盟友角色名称

    Returns:
        tuple[bool, str]: (是否成功, 失败时的错误详情)
    """
    if not tcg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法修改远征队名单"
        logger.error(f"添加远征队成员失败: {error_detail}")
        return False, error_detail

    member_entity = tcg_game.get_actor_entity(member_name)
    if member_entity is None:
        error_detail = f"角色 {member_name} 不存在"
        logger.error(f"添加远征队成员失败: {error_detail}")
        return False, error_detail

    if not member_entity.has(AllyComponent):
        error_detail = f"角色 {member_name} 不是盟友，无法加入远征队"
        logger.error(f"添加远征队成员失败: {error_detail}")
        return False, error_detail

    if member_entity.has(PlayerComponent):
        error_detail = "不能将玩家自身加入远征队名单"
        logger.error(f"添加远征队成员失败: {error_detail}")
        return False, error_detail

    player_entity = tcg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"
    assert player_entity.has(
        ExpeditionRosterComponent
    ), "玩家实体缺少 ExpeditionRosterComponent"

    roster = player_entity.get(ExpeditionRosterComponent)
    if member_name in roster.members:
        error_detail = f"{member_name} 已在远征队名单中"
        logger.warning(f"添加远征队成员失败: {error_detail}")
        return False, error_detail

    player_entity.replace(
        ExpeditionRosterComponent,
        player_entity.name,
        list(roster.members) + [member_name],
    )
    logger.debug(f"将 {member_name} 加入远征队名单")
    return True, ""


###################################################################################################################################################################
def remove_expedition_member(tcg_game: TCGGame, member_name: str) -> Tuple[bool, str]:
    """
    将盟友从远征队名单中移除。

    Args:
        tcg_game: TCG 游戏实例
        member_name: 要移除的盟友角色名称

    Returns:
        tuple[bool, str]: (是否成功, 失败时的错误详情)
    """
    if not tcg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法修改远征队名单"
        logger.error(f"移除远征队成员失败: {error_detail}")
        return False, error_detail

    player_entity = tcg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"
    assert player_entity.has(
        ExpeditionRosterComponent
    ), "玩家实体缺少 ExpeditionRosterComponent"

    roster = player_entity.get(ExpeditionRosterComponent)
    if member_name not in roster.members:
        error_detail = f"{member_name} 不在远征队名单中"
        logger.warning(f"移除远征队成员失败: {error_detail}")
        return False, error_detail

    player_entity.replace(
        ExpeditionRosterComponent,
        player_entity.name,
        [m for m in roster.members if m != member_name],
    )
    logger.debug(f"将 {member_name} 从远征队名单移除")
    return True, ""


###################################################################################################################################################################
def get_expedition_roster(tcg_game: TCGGame) -> List[str]:
    """
    查阅当前远征队名单（不含玩家自身）。

    Args:
        tcg_game: TCG 游戏实例

    Returns:
        远征队同伴名称列表；玩家实体或组件不存在时返回空列表
    """
    player_entity = tcg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"
    if player_entity is None:
        return []

    assert player_entity.has(
        ExpeditionRosterComponent
    ), "玩家实体缺少 ExpeditionRosterComponent"
    if not player_entity.has(ExpeditionRosterComponent):
        return []

    return list(player_entity.get(ExpeditionRosterComponent).members)


###################################################################################################################################################################
def activate_generate_dungeon(tcg_game: TCGGame) -> Tuple[bool, str]:
    """
    在家园状态下激活地下城创建动作。

    添加 GenerateDungeonAction 到玩家实体，触发 GenerateDungeonActionSystem 在
    dungeon_generate_pipeline 的下一次推进时执行地下城文本数据创建（Steps 1-4）。
    成功后自动添加 IllustrateDungeonAction 触发图片生成。动作组件由 ActionCleanupSystem 自动清除。

    Args:
        tcg_game: TCG 游戏实例

    Returns:
        Tuple[bool, str]: (是否成功, 失败时的错误详情)
    """
    if not tcg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法创建地下城"
        logger.error(f"激活地下城创建失败: {error_detail}")
        return False, error_detail

    player_entity = tcg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"

    if player_entity.has(GenerateDungeonAction):
        error_detail = "地下城创建动作已存在，请勿重复激活"
        logger.warning(f"激活地下城创建失败: {error_detail}")
        return False, error_detail

    logger.debug(f"激活地下城创建: {player_entity.name}")
    player_entity.replace(GenerateDungeonAction, player_entity.name)
    return True, ""


###################################################################################################################################################################
