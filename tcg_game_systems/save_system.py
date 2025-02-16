from entitas import ExecuteProcessor  # type: ignore
from typing import final, override, cast, Dict, Set
from game.tcg_game_context import TCGGameContext
from game.tcg_game import TCGGame
from loguru import logger


@final
class SaveSystem(ExecuteProcessor):

    ############################################################################################################
    def __init__(self, context: TCGGameContext) -> None:
        self._context: TCGGameContext = context
        self._game: TCGGame = cast(TCGGame, context._game)
        assert self._game is not None

    ############################################################################################################
    @override
    def execute(self) -> None:

        # 核心调用
        self._game.save()

        # 保存时，打印当前场景中的所有角色
        self._mapping()

    ############################################################################################################
    def _mapping(self) -> None:
        
        entities_mapping = self._game.context.retrieve_stage_actor_mapping()
        if len(entities_mapping) == 0:
            return

        names_mapping: Dict[str, Set[str]] = {}

        for stage_entity, actor_entities in entities_mapping.items():
            actor_names = {actor_entity._name for actor_entity in actor_entities}
            stage_name = stage_entity._name
            names_mapping[stage_name] = actor_names

        logger.debug(f"names_mapping = {names_mapping}")

    ############################################################################################################
