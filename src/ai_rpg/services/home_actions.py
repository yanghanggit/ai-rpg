"""家园动作辅助函数模块

本模块提供家园场景中玩家动作的激活和设置功能，主要包括：
- 说话动作：向指定目标角色发起对话
- 场景转换动作：在家园场景间进行切换

这些函数负责验证前置条件并在玩家实体上设置相应的动作组件，
实际的动作执行由游戏管道（pipeline）处理。

注意事项：
- 所有函数都返回 bool 值表示是否成功激活动作
- 激活失败时会记录错误日志
- 动作组件会被设置到玩家实体上，等待后续处理
"""

from loguru import logger
from ..game.tcg_game import TCGGame
from ..models import SpeakAction, TransStageAction, HomeComponent
from typing import Tuple


###################################################################################################################################################################
def activate_speak_action(
    tcg_game: TCGGame, target: str, content: str
) -> Tuple[bool, str]:
    """
    激活玩家的说话动作，向指定目标角色发起对话

    Args:
        tcg_game: TCG 游戏实例
        target: 目标角色名称
        content: 说话内容

    Returns:
        tuple[bool, str]: (是否成功, 错误详情)
            - (True, ""): 成功设置说话动作
            - (False, detail): 失败时返回具体错误信息
                - "目标角色名称不能为空"
                - "目标角色 {target} 不存在"
                - "玩家实体不存在"

    Note:
        - 目标角色必须存在于游戏世界中
        - 玩家实体必须存在
        - 成功后会在玩家实体上设置 SpeakAction 组件
        - 说话内容会在后续的游戏管道处理中执行
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
def activate_stage_transition(tcg_game: TCGGame, stage_name: str) -> Tuple[bool, str]:
    """
    激活玩家的场景转换动作，在家园场景间进行切换

    Args:
        tcg_game: TCG 游戏实例
        stage_name: 目标场景名称

    Returns:
        tuple[bool, str]: (是否成功, 错误详情)
            - (True, ""): 成功设置场景转换动作
            - (False, detail): 失败时返回具体错误信息
                - "目标场景名称不能为空"
                - "目标场景 {stage_name} 不存在"
                - "{stage_name} 不是家园场景"
                - "玩家实体不存在"
                - "目标场景 {stage_name} 与当前场景相同"

    Note:
        - 目标场景必须存在于游戏世界中
        - 目标场景必须是家园场景（具有 HomeComponent）
        - 玩家实体必须存在
        - 成功后会在玩家实体上设置 TransStageAction 组件
        - 场景转换会在后续的游戏管道处理中执行
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

    player_stage_entity = tcg_game.safe_get_stage_entity(player_entity)
    assert player_stage_entity is not None, "玩家当前场景实体不存在！"
    if player_stage_entity.name == stage_name:
        error_detail = f"目标场景 {stage_name} 与当前场景相同"
        logger.error(f"激活场景转换失败: {error_detail}")
        return False, error_detail

    logger.debug(f"激活场景转换: {player_entity.name} -> {stage_name}")
    player_entity.replace(TransStageAction, player_entity.name, stage_name)
    return True, ""


###################################################################################################################################################################
def activate_ally_plan_action(tcg_game: TCGGame, allies: list[str]) -> Tuple[bool, str]:
    """
    激活指定角色的行动计划，为角色添加 PlanAction 组件

    该函数为指定的盟友角色添加行动计划标记，使其在下一次游戏推进时执行AI决策。
    只有符合条件的盟友角色才能被添加 PlanAction：
    - 角色必须存在于游戏世界中
    - 角色必须是盟友（具有 AllyComponent）
    - 角色不能是玩家控制的（不能有 PlayerComponent）

    Args:
        tcg_game: TCG 游戏实例
        heroes: 目标角色名称列表

    Returns:
        tuple[bool, str]: (是否成功, 错误详情)
            - (True, ""): 成功为所有符合条件的角色设置 PlanAction
            - (False, detail): 失败时返回具体错误信息
                - "角色名称列表不能为空"
                - "未能为任何角色添加 PlanAction"

    Note:
        - 不存在、不是盟友或是玩家控制的角色会被跳过，并记录警告日志
        - 至少需要为一个角色成功添加 PlanAction 才算成功
        - 成功后会在符合条件的角色实体上设置 PlanAction 组件
        - 行动计划会在后续的 NPC home pipeline 处理中执行
    """
    from ..models import AllyComponent, PlayerComponent, PlanAction

    if not allies or len(allies) == 0:
        error_detail = "角色名称列表不能为空"
        logger.error(f"激活行动计划失败: {error_detail}")
        return False, error_detail

    success_count = 0
    for actor_name in allies:
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
