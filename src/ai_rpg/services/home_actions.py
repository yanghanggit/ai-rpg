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


###################################################################################################################################################################
def activate_speak_action(tcg_game: TCGGame, target: str, content: str) -> bool:
    """
    激活玩家的说话动作，向指定目标角色发起对话

    Args:
        tcg_game: TCG 游戏实例
        target: 目标角色名称
        content: 说话内容

    Returns:
        bool: 是否成功激活说话动作
            - True: 成功设置说话动作
            - False: 目标角色不存在或玩家实体不存在

    Note:
        - 目标角色必须存在于游戏世界中
        - 玩家实体必须存在
        - 成功后会在玩家实体上设置 SpeakAction 组件
        - 说话内容会在后续的游戏管道处理中执行
    """

    target_entity = tcg_game.get_actor_entity(target)
    if target_entity is None:
        logger.error(f"激活说话动作失败: 目标角色 {target} 不存在")
        return False

    player_entity = tcg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"
    if player_entity is None:
        logger.error("激活说话动作失败: 玩家实体不存在")
        return False

    player_entity.replace(SpeakAction, player_entity.name, {target: content})
    return True


###################################################################################################################################################################
def activate_stage_transition(tcg_game: TCGGame, stage_name: str) -> bool:
    """
    激活玩家的场景转换动作，在家园场景间进行切换

    Args:
        tcg_game: TCG 游戏实例
        stage_name: 目标场景名称

    Returns:
        bool: 是否成功激活场景转换动作
            - True: 成功设置场景转换动作
            - False: 场景名称为空、目标场景不存在、不是家园场景或玩家实体不存在

    Note:
        - 目标场景必须存在于游戏世界中
        - 目标场景必须是家园场景（具有 HomeComponent）
        - 玩家实体必须存在
        - 成功后会在玩家实体上设置 TransStageAction 组件
        - 场景转换会在后续的游戏管道处理中执行
    """
    if not stage_name:
        logger.error("激活场景转换失败: 目标场景名称不能为空")
        return False

    target_stage_entity = tcg_game.get_stage_entity(stage_name)
    if target_stage_entity is None:
        logger.error(f"激活场景转换失败: 目标场景 {stage_name} 不存在")
        return False

    if not target_stage_entity.has(HomeComponent):
        logger.error(f"激活场景转换失败: {stage_name} 不是家园场景")
        return False

    player_entity = tcg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"
    if player_entity is None:
        logger.error("激活场景转换失败: 玩家实体不存在")
        return False

    logger.debug(f"激活场景转换: {player_entity.name} -> {stage_name}")
    player_entity.replace(TransStageAction, player_entity.name, stage_name)
    return True


###################################################################################################################################################################
