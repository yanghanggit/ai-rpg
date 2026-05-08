"""战斗回合清理系统：回合结束后重置战场瞬态，确保下一回合以干净状态启动。"""

from typing import Final, List, final, override
from loguru import logger
from ..entitas import ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from ..models import (
    ActorComponent,
    StatusEffect,
    StatusEffectsComponent,
)


def _make_status_effects_tick_message(
    ticked: List[StatusEffect],
    expired: List[StatusEffect],
) -> str:
    """生成回合结束时状态效果更新的 LLM 通知文本。

    Args:
        ticked: 持续时间已递减但尚未过期的效果列表
        expired: 本回合耗尽（已移除）的效果列表

    Returns:
        写入 agent 上下文的 human message 文本
    """
    lines = ["# 回合结束 — 状态效果更新"]
    for e in ticked:
        lines.append(f"- {e.name}（剩余{e.duration}回合）")
    for e in expired:
        lines.append(f"- {e.name} → 已过期，已从状态列表移除")
    return "\n".join(lines)


###############################################################################################################################################
@final
class CombatRoundCleanupSystem(ExecuteProcessor):
    """
    战斗回合清理系统。

    目标：在每个回合标记完成后，清除该回合遗留的瞬态数据，
          使 CombatRoundTransitionSystem 能安全地创建下一回合。

    Pipeline 位置：CombatOutcomeSystem（后）→ 本系统 → CombatRoundTransitionSystem（前）

    前置条件：
    - 当前战斗处于 ONGOING 状态
    - 已存在至少一个回合，且最新回合已完成

    不满足上述条件时静默跳过，对外无副作用。
    """

    ############################################################################################################
    def __init__(self, game: TCGGame) -> None:
        self._game: Final[TCGGame] = game

    ############################################################################################################
    @override
    async def execute(self) -> None:

        if not self._game.current_dungeon.is_ongoing:
            logger.debug("当前战斗状态非 ONGOING，跳过旧回合状态清除")
            return

        current_rounds = self._game.current_dungeon.current_rounds or []
        if len(current_rounds) == 0:
            return

        last_round = self._game.current_dungeon.latest_round
        assert last_round is not None, "latest_round is None"
        if not last_round.is_completed:
            return

        logger.debug("清除旧回合手牌与格挡状态")
        self._game.clear_round_state()
        self.tick_status_effects_duration()

    ############################################################################################################
    def tick_status_effects_duration(self) -> None:
        """推进所有角色的状态效果时钟，移除到期效果，并将变化同步写入角色 agent 上下文。"""
        for entity in self._game.get_group(
            Matcher(StatusEffectsComponent)
        ).entities.copy():
            assert entity.has(
                ActorComponent
            ), f"Entity {entity.name} has StatusEffectsComponent but is not an Actor"
            comp = entity.get(StatusEffectsComponent)

            # 递减持续时间并移除过期效果
            updated = []
            ticked = []
            expired = []
            for effect in comp.status_effects:
                if effect.duration == -1:
                    updated.append(effect)
                    continue
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
                entity, _make_status_effects_tick_message(ticked, expired)
            )

    ################################################################################################################
