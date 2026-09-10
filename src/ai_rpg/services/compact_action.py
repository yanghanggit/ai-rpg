"""上下文压缩动作辅助函数模块。

与场景状态无关：调用方传入目标实体名，本模块按名字解析实体并挂载
CompactContextAction，实际压缩由 CompactContextActionSystem 在
compact pipeline 中执行。
"""

from typing import Tuple

from loguru import logger

from ..game.dbg_game import DBGGame
from ..models import CompactContextAction


###################################################################################################################################################################
def activate_compact_context(dbg_game: DBGGame, target_name: str) -> Tuple[bool, str]:
    """
    为指定名称的实体激活手动上下文压缩动作。

    按名字直接取实体，不做场景/NPC 等额外校验（复杂度交给发起端）。
    """

    # 目标名称不能为空
    if not target_name or target_name.strip() == "":
        error_detail = "目标实体名称不能为空"
        logger.error(f"激活上下文压缩失败: {error_detail}")
        return False, error_detail

    target_name = target_name.strip()

    # 按名字解析目标实体（角色/怪物/场景/世界均可）
    target_entity = dbg_game.get_entity_by_name(target_name)
    if target_entity is None:
        error_detail = f"目标实体 {target_name} 不存在"
        logger.error(f"激活上下文压缩失败: {error_detail}")
        return False, error_detail

    # 防止重复挂载（replace 在已存在时只会触发 replaced 事件，无法被 ADDED 监听捕获）
    if target_entity.has(CompactContextAction):
        error_detail = f"目标实体 {target_name} 的压缩动作已存在，请勿重复激活"
        logger.warning(f"激活上下文压缩失败: {error_detail}")
        return False, error_detail

    # 挂载压缩动作，由 CompactContextActionSystem 响应
    logger.debug(f"激活上下文压缩: {target_entity.name}")
    target_entity.replace(CompactContextAction, target_entity.name)

    return True, ""
