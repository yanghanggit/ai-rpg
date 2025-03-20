from enum import IntEnum, unique
from typing import Final, List, final


###############################################################################################################################################
# 表示战斗的状态
@final
@unique
class CombatState(IntEnum):
    NONE = (0,)
    INIT = (1,)  # 初始化，需要同步一些数据与状态
    RUNNING = (2,)  # 运行中，不断进行战斗推理
    END = 3  # 结束，需要进行结算


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
        self._state: CombatState = CombatState.NONE
        self._rounds: List[Round] = []
        self._result: CombatResult = CombatResult.NONE

    ###############################################################################################################################################
    @property
    def current_state(self) -> CombatState:
        return self._state

    ###############################################################################################################################################
    @property
    def result(self) -> CombatResult:
        return self._result

    ###############################################################################################################################################
    def start_combat(self) -> None:
        assert self._state == CombatState.INIT
        self._state = CombatState.RUNNING

    ###############################################################################################################################################
    def end_combat(self, result: CombatResult) -> None:
        assert self._state == CombatState.RUNNING
        self._state = CombatState.END
        self._result = result

    ###############################################################################################################################################
    def start_new_round(self) -> Round:
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


# 全局变量：空的战斗
EMPTY_COMBAT: Final[Combat] = Combat("EMPTY_COMBAT")


###############################################################################################################################################
# 表示战斗系统
class CombatSystem:

    def __init__(self) -> None:
        self._combats: List[Combat] = []

    ########################################################################################################################
    def start_new_combat(self, name: str) -> None:
        combat = Combat(name)
        combat._state = CombatState.INIT
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
