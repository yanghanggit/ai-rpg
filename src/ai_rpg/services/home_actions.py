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
    PlanAction,
)
from typing import List, Tuple


###################################################################################################################################################################
def activate_speak_action(
    tcg_game: TCGGame, target: str, content: str
) -> Tuple[bool, str]:
    """
    激活玩家的说话动作

    Args:
        tcg_game: TCG 游戏实例
        target: 目标角色名称
        content: 说话内容

    Returns:
        tuple[bool, str]: (是否成功, 错误详情)
    """
    if not target:
        error_detail = "目标角色名称不能为空"
        logger.error(f"激活说话动作失败: {error_detail}")
        return False, error_detail

    target_entity = tcg_game.get_actor_entity(target)
    if target_entity is None:
        error_detail = f"目标角色 {target} 不存在"
        logger.error(f"激活说话动作失败: {error_detail}")
        return False, error_detail

    player_entity = tcg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"
    if player_entity is None:
        error_detail = "玩家实体不存在"
        logger.error(f"激活说话动作失败: {error_detail}")
        return False, error_detail

    player_entity.replace(SpeakAction, player_entity.name, {target: content})
    return True, ""


###################################################################################################################################################################
def activate_switch_stage(tcg_game: TCGGame, stage_name: str) -> Tuple[bool, str]:
    """
    激活玩家的场景转换动作

    Args:
        tcg_game: TCG 游戏实例
        stage_name: 目标场景名称

    Returns:
        tuple[bool, str]: (是否成功, 错误详情)
    """
    if not stage_name:
        error_detail = "目标场景名称不能为空"
        logger.error(f"激活场景转换失败: {error_detail}")
        return False, error_detail

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
    if player_entity is None:
        error_detail = "玩家实体不存在"
        logger.error(f"激活场景转换失败: {error_detail}")
        return False, error_detail

    player_stage_entity = tcg_game.resolve_stage_entity(player_entity)
    assert player_stage_entity is not None, "玩家当前场景实体不存在！"
    if player_stage_entity.name == stage_name:
        error_detail = f"目标场景 {stage_name} 与当前场景相同"
        logger.error(f"激活场景转换失败: {error_detail}")
        return False, error_detail

    logger.debug(f"激活场景转换: {player_entity.name} -> {stage_name}")
    player_entity.replace(TransStageAction, player_entity.name, stage_name)
    return True, ""


###################################################################################################################################################################
def activate_plan_action(tcg_game: TCGGame, actors: List[str]) -> Tuple[bool, str]:
    """
    为指定角色激活行动计划

    为符合条件的角色添加 PlanAction 组件，使其在下一次游戏推进时执行AI决策。
    角色必须是盟友且非玩家控制。

    Args:
        tcg_game: TCG 游戏实例
        actors: 目标角色名称列表

    Returns:
        tuple[bool, str]: (是否成功, 错误详情)
    """

    if not actors or len(actors) == 0:
        error_detail = "角色名称列表不能为空"
        logger.error(f"激活行动计划失败: {error_detail}")
        return False, error_detail

    success_count = 0
    for actor_name in actors:
        actor_entity = tcg_game.get_actor_entity(actor_name)
        if actor_entity is None:
            logger.warning(f"角色 {actor_name} 不存在，跳过")
            continue

        if not actor_entity.has(AllyComponent):
            logger.warning(f"角色 {actor_name} 不是盟友，不能添加行动计划，跳过")
            continue

        if actor_entity.has(PlayerComponent):
            logger.warning(f"角色 {actor_name} 是玩家控制的，不能添加行动计划，跳过")
            continue

        logger.debug(f"为角色 {actor_name} 添加 PlanAction")
        actor_entity.replace(PlanAction, actor_entity.name)
        success_count += 1

    if success_count == 0:
        error_detail = "未能为任何角色添加 PlanAction"
        logger.error(f"激活行动计划失败: {error_detail}")
        return False, error_detail

    logger.info(f"成功为 {success_count} 个角色添加 PlanAction")
    return True, ""


###################################################################################################################################################################
