from enum import IntEnum, unique
from typing import Final, List, final

from loguru import logger


###############################################################################################################################################
# 表示战斗的状态 Phase
@final
@unique
class CombatPhase(IntEnum):
    NONE = (0,)
    PREPARATION = (1,)  # 初始化，需要同步一些数据与状态
    ONGOING = (2,)  # 运行中，不断进行战斗推理
    COMPLETE = 3  # 结束，需要进行结算
    POST_WAIT = 4  # 战斗等待进入新一轮战斗或者回家


###############################################################################################################################################
# 表示战斗的状态
@final
@unique
class CombatResult(IntEnum):
    NONE = (0,)
    HERO_WIN = (1,)  # 胜利
    HERO_LOSE = (2,)  # 失败


###############################################################################################################################################


# 表示一个回合
class Round:

    def __init__(self) -> None:
        pass


###############################################################################################################################################
# 表示一个战斗
class Combat:

    def __init__(self, name: str) -> None:
        self._name: Final[str] = name
        self._phase: CombatPhase = CombatPhase.NONE
        self._rounds: List[Round] = []
        self._result: CombatResult = CombatResult.NONE

    ###############################################################################################################################################
    @property
    def last_round(self) -> Round:
        assert len(self._rounds) > 0
        if len(self._rounds) == 0:
            return Round()

        return self._rounds[-1]

    ###############################################################################################################################################


###############################################################################################################################################
# 表示战斗系统
@final
class CombatSystem:

    def __init__(self) -> None:
        self._combats: List[Combat] = []

    ########################################################################################################################
    @property
    def combats(self) -> List[Combat]:
        return self._combats

    ########################################################################################################################
    @property
    def last_combat(self) -> Combat:
        assert len(self._combats) > 0
        if len(self._combats) == 0:
            return Combat("")

        return self._combats[-1]

    ###############################################################################################################################################
    @property
    def is_on_going_phase(self) -> bool:
        return self.last_combat._phase == CombatPhase.ONGOING

    ###############################################################################################################################################
    @property
    def is_complete_phase(self) -> bool:
        return self.last_combat._phase == CombatPhase.COMPLETE

    ###############################################################################################################################################
    @property
    def is_preparation_phase(self) -> bool:
        return self.last_combat._phase == CombatPhase.PREPARATION

    ###############################################################################################################################################
    @property
    def is_post_wait_phase(self) -> bool:
        return self.last_combat._phase == CombatPhase.POST_WAIT

    ###############################################################################################################################################
    @property
    def rounds(self) -> List[Round]:
        return self.last_combat._rounds

    ###############################################################################################################################################
    @property
    def combat_result(self) -> CombatResult:
        return self.last_combat._result

    ###############################################################################################################################################
    # 启动一个战斗！！！ 注意状态转移
    def combat_engagement(self, combat: Combat) -> None:
        assert combat._phase == CombatPhase.NONE
        combat._phase = CombatPhase.PREPARATION
        self._combats.append(combat)

    ###############################################################################################################################################
    def combat_go(self) -> None:
        assert self.last_combat._phase == CombatPhase.PREPARATION
        assert self.last_combat._result == CombatResult.NONE
        self.last_combat._phase = CombatPhase.ONGOING

    ###############################################################################################################################################
    def combat_complete(self, result: CombatResult) -> None:
        # 设置战斗结束阶段！
        assert self.last_combat._phase == CombatPhase.ONGOING
        assert result == CombatResult.HERO_WIN or result == CombatResult.HERO_LOSE
        assert self.last_combat._result == CombatResult.NONE

        # "战斗已经结束"
        self.last_combat._phase = CombatPhase.COMPLETE
        # 设置战斗结果！
        self.last_combat._result = result

    ###############################################################################################################################################
    def combat_post_wait(self) -> None:
        assert (
            self.last_combat._result == CombatResult.HERO_WIN
            or self.last_combat._result == CombatResult.HERO_LOSE
        )
        assert self.last_combat._phase == CombatPhase.COMPLETE

        # 设置战斗等待阶段！
        self.last_combat._phase = CombatPhase.POST_WAIT

    ###############################################################################################################################################
    def new_round(self) -> Round:
        round = Round()
        self.last_combat._rounds.append(round)
        logger.info(f"新的回合开始 = {len(self.last_combat._rounds)}")
        return round

    ###############################################################################################################################################
