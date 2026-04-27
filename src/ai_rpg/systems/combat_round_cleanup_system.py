"""
战斗回合清理系统

职责：
- 清除上一回合的手牌、格挡状态
- 递减状态效果持续时间，移除已过期效果

设计特点：
- 使用 ExecuteProcessor，每次 pipeline 执行时主动检查
- 位于 CombatOutcomeSystem 之后、CombatRoundTransitionSystem 之前
- 内部有状态守护：仅在回合已完成时触发
"""

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
    战斗回合清理系统

    在每次 pipeline 执行时清理已完成回合的残留状态：
    清除旧回合手牌与格挡 → 递减/移除状态效果。
    位于 CombatRoundTransitionSystem 之前，确保新回合创建时环境已干净。

    内部状态守护（不满足则静默跳过）：
    - 战斗状态非 ONGOING / COMPLETE / POST_COMBAT → 跳过
    - 尚无任何回合 → 跳过
    - 最新回合未完成 → 跳过
    """

    ############################################################################################################
    def __init__(self, game: TCGGame) -> None:
        self._game: Final[TCGGame] = game

    ############################################################################################################
    @override
    async def execute(self) -> None:
        # # 状态守护：非有效战斗阶段 / 无回合 / 最新回合未完成 → 静默跳过
        # valid_state = (
        #     self._game.current_dungeon.is_ongoing
        #     or self._game.current_dungeon.is_combat_completed
        #     or self._game.current_dungeon.is_post_combat
        # )
        # if not valid_state:
        #     logger.debug(
        #         "当前战斗状态非 ONGOING/COMPLETE/POST_COMBAT，跳过旧回合状态清除"
        #     )
        #     return

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
        """回合结束时递减所有角色的状态效果持续时间，移除已过期的效果。

        - duration == -1：永久效果，跳过递减
        - duration > 0：-=1；降至 0 时从列表中移除

        对每个有变化的 actor 实体写入 human message，保持 agent 对话上下文连续性。
        """
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
