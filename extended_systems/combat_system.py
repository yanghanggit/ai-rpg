from enum import IntEnum, unique
from typing import Final, List, final


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
        self._turns: List[str] = []

    @property
    def turns(self) -> List[str]:
        return self._turns

    # 写一个 turns 的setter
    @turns.setter
    def turns(self, value: List[str]) -> None:
        self._turns = value


# 全局变量：空的回合
EMPTY_ROUND: Final[Round] = Round()


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
    def current_phase(self) -> CombatPhase:
        return self._phase

    ###############################################################################################################################################
    @property
    def result(self) -> CombatResult:
        return self._result

    ###############################################################################################################################################
    def begin_combat(self) -> None:
        assert self._phase == CombatPhase.PREPARATION
        self._phase = CombatPhase.ONGOING
        assert self._result == CombatResult.NONE

    ###############################################################################################################################################
    def end_combat(self, result: CombatResult) -> None:

        # 设置战斗结束阶段！
        assert self._phase == CombatPhase.ONGOING
        assert self.is_on_going, "战斗已经结束"
        self._phase = CombatPhase.COMPLETE

        # 设置战斗结果！
        assert result == CombatResult.HERO_WIN or result == CombatResult.HERO_LOSE
        assert self._result == CombatResult.NONE
        self._result = result

    ###############################################################################################################################################
    def post_combat_wait(self) -> None:
        assert self._phase == CombatPhase.COMPLETE
        self._phase = CombatPhase.POST_WAIT
        assert (
            self._result == CombatResult.HERO_WIN
            or self._result == CombatResult.HERO_LOSE
        )

    ###############################################################################################################################################
    def begin_new_round(self) -> Round:
        round = Round()
        self._rounds.append(round)
        return round

    ###############################################################################################################################################
    @property
    def rounds(self) -> List[Round]:
        return self._rounds

    ###############################################################################################################################################
    @property
    def latest_round(self) -> Round:
        assert len(self._rounds) > 0
        if len(self._rounds) == 0:
            return EMPTY_ROUND

        return self._rounds[-1]

    ###############################################################################################################################################
    @property
    def is_on_going(self) -> bool:
        return self._phase == CombatPhase.ONGOING

    ###############################################################################################################################################
    @property
    def is_complete(self) -> bool:
        return self._phase == CombatPhase.COMPLETE

    ###############################################################################################################################################
    @property
    def is_preparation(self) -> bool:
        return self._phase == CombatPhase.PREPARATION

    ###############################################################################################################################################
    @property
    def is_post_wait(self) -> bool:
        return self._phase == CombatPhase.POST_WAIT

    ###############################################################################################################################################


# 全局变量：空的战斗
EMPTY_COMBAT: Final[Combat] = Combat("EMPTY_COMBAT")


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
    def start_new_combat(self, name: str) -> None:
        combat = Combat(name)
        combat._phase = CombatPhase.PREPARATION
        self._combats.append(combat)

    ########################################################################################################################
    def has_combat(self, name: str) -> bool:
        for combat in self._combats:
            if combat._name == name:
                return True
        return False

    ########################################################################################################################
    @property
    def latest_combat(self) -> Combat:
        assert len(self._combats) > 0
        if len(self._combats) == 0:
            return EMPTY_COMBAT

        return self._combats[-1]

    ########################################################################################################################
