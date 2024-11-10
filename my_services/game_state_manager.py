from enum import Enum
from typing import Dict, Set


class GameState(Enum):
    UNLOGGED = 0
    LOGGED_IN = 1
    GAME_CREATED = 3
    GAME_JOINED = 4
    PLAYING = 5
    REQUESTING_EXIT = 6


class GameStateController:

    def __init__(self, game_stage: GameState) -> None:

        self._state: GameState = game_stage

        self._transition_protocol: Dict[GameState, Set[GameState]] = {
            GameState.UNLOGGED: {GameState.LOGGED_IN},
            GameState.LOGGED_IN: {GameState.GAME_CREATED},
            GameState.GAME_CREATED: {GameState.GAME_JOINED},
            GameState.GAME_JOINED: {GameState.PLAYING},
            GameState.PLAYING: {GameState.REQUESTING_EXIT},
            GameState.REQUESTING_EXIT: {GameState.UNLOGGED},
        }

    @property
    def state(self) -> GameState:
        return self._state

    def can_transition(self, dst: GameState) -> bool:
        return dst in self._transition_protocol.get(self._state, set())

    def transition(self, dst: GameState) -> None:
        if self.can_transition(dst):
            self._state = dst
        else:
            raise ValueError(f"Can't transition from {self._state} to {dst}")
