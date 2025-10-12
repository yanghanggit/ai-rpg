from typing import final
from loguru import logger
from overrides import override
from ..entitas import ExecuteProcessor, InitializeProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    ModeratorComponent,
    WerewolfComponent,
    SeerComponent,
    WitchComponent,
    VillagerComponent,
    SDCharacterSheetName,
)


###############################################################################################################################################
@final
class SocialDeductionKickOffSystem(ExecuteProcessor, InitializeProcessor):

    ###############################################################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###############################################################################################################################################
    @override
    async def initialize(self) -> None:

        # 分配角色
        self._assign_role_to_all_actors()

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:
        pass

    ###############################################################################################################################################
    def _assign_role_to_all_actors(self) -> None:
        all_actors = self._game._world.boot.actors

        for actor in all_actors:

            actor_entity = self._game.get_entity_by_name(actor.name)
            assert actor_entity is not None, f"Actor Entity 不存在: {actor.name}"

            match actor.character_sheet.name:
                case SDCharacterSheetName.MODERATOR:
                    actor_entity.replace(ModeratorComponent, actor.name)
                    logger.info(f"分配角色: {actor.name} -> Moderator")

                case SDCharacterSheetName.WEREWOLF:
                    actor_entity.replace(WerewolfComponent, actor.name)
                    logger.info(f"分配角色: {actor.name} -> Werewolf")

                case SDCharacterSheetName.SEER:
                    actor_entity.replace(SeerComponent, actor.name)
                    logger.info(f"分配角色: {actor.name} -> Seer")

                case SDCharacterSheetName.WITCH:
                    actor_entity.replace(WitchComponent, actor.name)
                    logger.info(f"分配角色: {actor.name} -> Witch")

                case SDCharacterSheetName.VILLAGER:
                    actor_entity.replace(VillagerComponent, actor.name)
                    logger.info(f"分配角色: {actor.name} -> Villager")

                case _:
                    assert False, f"未知的狼人杀角色: {actor.character_sheet.name}"

    ###############################################################################################################################################
