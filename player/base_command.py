from entitas import Entity  # type: ignore
from rpg_game.base_game import BaseGame
from player.player_proxy import PlayerProxy
from abc import ABC, abstractmethod
from typing import cast


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerCommand(ABC):

    def __init__(self, name: str, input_val: str) -> None:
        self._name: str = name
        self._input_val: str = input_val

    @abstractmethod
    def execute(self, game: BaseGame, player_proxy: PlayerProxy) -> None:
        pass

    def add_player_planning_message(
        self, entity: Entity, human_message_content: str, game: BaseGame
    ) -> None:
        from rpg_game.rpg_game import RPGGame

        rpg_game = cast(RPGGame, game)
        rpg_game._entitas_context.safe_add_ai_message_to_entity(
            entity, human_message_content
        )

    def split_command(self, input_val: str, split_str: str) -> str:
        if split_str in input_val:
            return input_val.split(split_str)[1].strip()
        return input_val
