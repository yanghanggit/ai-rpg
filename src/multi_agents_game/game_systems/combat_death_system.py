from typing import final, override

from loguru import logger

from ..entitas import ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from ..models import (
    DeathComponent,
    RPGCharacterProfileComponent,
)


@final
class CombatDeathSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ########################################################################################################################################################################
    @override
    def execute(self) -> None:

        # 处理hp为0的情况
        entities = self._game.get_group(
            Matcher(all_of=[RPGCharacterProfileComponent], none_of=[DeathComponent])
        ).entities.copy()
        for entity in entities:
            rpg_character_profile_component = entity.get(RPGCharacterProfileComponent)
            if rpg_character_profile_component.rpg_character_profile.hp <= 0:
                logger.warning(f"{rpg_character_profile_component.name} is dead")
                self._game.append_human_message(entity, "# 你已被击败！")
                entity.replace(DeathComponent, rpg_character_profile_component.name)

    ########################################################################################################################################################################
