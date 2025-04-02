from typing import List, final
from loguru import logger
from models.v_0_0_1 import Combat, Round, CombatPhase, CombatResult, Engagement


###############################################################################################################################################
# 表示战斗系统
@final
class EngagementSystem(Engagement):

    ###############################################################################################################################################
    @property
    def last_combat(self) -> Combat:
        assert len(self.combats) > 0
        if len(self.combats) == 0:
            return Combat(name="")

        return self.combats[-1]

    ###############################################################################################################################################
    @property
    def rounds(self) -> List[Round]:
        return self.last_combat.rounds

    ###############################################################################################################################################
    @property
    def last_round(self) -> Round:
        assert len(self.rounds) > 0
        if len(self.rounds) == 0:
            return Round(tag="")

        return self.rounds[-1]

    ###############################################################################################################################################
    def new_round(self) -> Round:
        round = Round(tag=f"round_{len(self.last_combat.rounds) + 1}")
        self.last_combat.rounds.append(round)
        logger.debug(f"新的回合开始 = {len(self.last_combat.rounds)}")
        return round

    ###############################################################################################################################################
    @property
    def is_on_going_phase(self) -> bool:
        return self.last_combat.phase == CombatPhase.ONGOING

    ###############################################################################################################################################
    @property
    def is_complete_phase(self) -> bool:
        return self.last_combat.phase == CombatPhase.COMPLETE

    ###############################################################################################################################################
    @property
    def is_kickoff_phase(self) -> bool:
        return self.last_combat.phase == CombatPhase.KICK_OFF

    ###############################################################################################################################################
    @property
    def is_post_wait_phase(self) -> bool:
        return self.last_combat.phase == CombatPhase.POST_WAIT

    ###############################################################################################################################################
    @property
    def combat_result(self) -> CombatResult:
        return self.last_combat.result

    ###############################################################################################################################################
    # 启动一个战斗！！！ 注意状态转移
    def combat_kickoff(self, combat: Combat) -> None:
        assert combat.phase == CombatPhase.NONE
        combat.phase = CombatPhase.KICK_OFF
        self.combats.append(combat)

    ###############################################################################################################################################
    def combat_ongoing(self) -> None:
        assert self.last_combat.phase == CombatPhase.KICK_OFF
        assert self.last_combat.result == CombatResult.NONE
        self.last_combat.phase = CombatPhase.ONGOING

    ###############################################################################################################################################
    def combat_complete(self, result: CombatResult) -> None:
        # 设置战斗结束阶段！
        assert self.last_combat.phase == CombatPhase.ONGOING
        assert result == CombatResult.HERO_WIN or result == CombatResult.HERO_LOSE
        assert self.last_combat.result == CombatResult.NONE

        # "战斗已经结束"
        self.last_combat.phase = CombatPhase.COMPLETE
        # 设置战斗结果！
        self.last_combat.result = result

    ###############################################################################################################################################
    def combat_post_wait(self) -> None:
        assert (
            self.last_combat.result == CombatResult.HERO_WIN
            or self.last_combat.result == CombatResult.HERO_LOSE
        )
        assert self.last_combat.phase == CombatPhase.COMPLETE

        # 设置战斗等待阶段！
        self.last_combat.phase = CombatPhase.POST_WAIT

    ###############################################################################################################################################
