from enum import IntEnum, unique
from typing import Final, List, final


###############################################################################################################################################
@final
@unique
class CombatState(IntEnum):
    NONE = (0,)
    INIT = (1,)
    RUNNING = (2,)
    END = 3


###############################################################################################################################################
class Combat:

    def __init__(self, name: str) -> None:
        self._name: Final[str] = name
        self._state: CombatState = CombatState.NONE

    ###############################################################################################################################################
    @property
    def current_state(self) -> CombatState:
        return self._state

    ###############################################################################################################################################
    def start_combat(self) -> None:
        assert self._state == CombatState.INIT
        self._state = CombatState.RUNNING

    ###############################################################################################################################################


EMPTY_COMBAT: Final[Combat] = Combat("EMPTY_COMBAT")


###############################################################################################################################################
class CombatSystem:

    def __init__(self) -> None:
        self._combats: List[Combat] = []

    ########################################################################################################################
    def new_combat(self, name: str) -> None:
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
    def current_combat(self) -> Combat:
        assert len(self._combats) > 0
        if len(self._combats) == 0:
            return EMPTY_COMBAT

        return self._combats[-1]

    ########################################################################################################################
