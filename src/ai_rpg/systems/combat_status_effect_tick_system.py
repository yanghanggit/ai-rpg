"""战斗状态效果 tick 系统：推进所有角色的状态效果持续时间，移除到期效果。"""

from typing import Final, List, final, override
from loguru import logger
from ..entitas import ExecuteProcessor, Matcher
from ..game.dbg_game import DBGGame
from ..utils import prompt_builder
from ..models import (
    DeathComponent,
    HumanMessage,
    StatusEffect,
    StatusEffectsComponent,
)


@prompt_builder
def _build_status_effects_tick_message(
    ticked: List[StatusEffect],
    expired: List[StatusEffect],
) -> str:
    """生成回合结束时状态效果更新的 LLM 通知文本。"""
    lines = ["# 回合结束 — 状态效果更新"]
    for e in ticked:
        lines.append(f"- {e.name}（剩余{e.duration}回合）")
    for e in expired:
        lines.append(f"- {e.name} → 已过期，已从状态列表移除")
    return "\n".join(lines)


###############################################################################################################################################
@final
class CombatStatusEffectTickSystem(ExecuteProcessor):
    """
    战斗状态效果 tick 系统：推进所有角色的状态效果时钟，移除到期效果，
    并将变化同步写入角色 agent 上下文。
    """

    ############################################################################################################
    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ############################################################################################################
    @override
    async def execute(self) -> None:

        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("当前战斗状态非 ONGOING，跳过状态效果 tick")
            return

        current_rounds = self._game.current_dungeon_combat_room.combat.rounds or []
        if len(current_rounds) == 0:
            return

        last_round = self._game.current_dungeon_combat_room.combat.latest_round
        assert last_round is not None, "latest_round is None"
        if not last_round.is_completed:
            return

        # 遍历所有具有状态效果组件且未死亡的实体，推进状态效果时钟并移除到期效果
        for entity in self._game.get_group(
            Matcher(all_of=[StatusEffectsComponent], none_of=[DeathComponent])
        ).entities.copy():

            comp = entity.get(StatusEffectsComponent)

            # 递减持续时间并移除过期效果
            updated = []
            ticked = []
            expired = []

            # 遍历每个状态效果，递减其持续时间并根据是否到期分类为已更新、已触发或已过期
            for effect in comp.status_effects:

                # 如果状态效果的持续时间为 -1，表示该效果是永久性的，不进行递减，直接加入已更新列表
                if effect.duration == -1:
                    updated.append(effect)
                    continue

                # 递减状态效果的持续时间，并根据是否到期分类为已更新、已触发或已过期
                effect.duration -= 1
                if effect.duration > 0:
                    updated.append(effect)
                    ticked.append(effect)
                else:
                    expired.append(effect)
                    logger.debug(
                        f"[{entity.name}] 状态效果「{effect.name}」持续时间耗尽，已移除"
                    )

            # 更新组件状态效果列表
            comp.status_effects = updated

            # 没有任何变化则跳过写入上下文
            if not ticked and not expired:
                continue

            # 将更新结果写入角色上下文，保持对话连续性
            self._game.add_human_message(
                entity,
                HumanMessage(
                    content=_build_status_effects_tick_message(ticked, expired)
                ),
            )

    ################################################################################################################
