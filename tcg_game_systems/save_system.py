from entitas import ExecuteProcessor  # type: ignore
from typing import List, final, override, Dict, Set
from game.tcg_game import TCGGame
from loguru import logger


@final
class SaveSystem(ExecuteProcessor):

    ############################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ############################################################################################################
    @override
    def execute(self) -> None:

        # 核心调用
        self._game.save()

        # 保存时，打印当前场景中的所有角色
        self._mapping()

    ############################################################################################################
    def _mapping(self) -> None:

        entities_mapping = self._game.retrieve_stage_actor_mapping()
        if len(entities_mapping) == 0:
            return

        names_mapping: Dict[str, List[str]] = {}

        for stage_entity, actor_entities in entities_mapping.items():
            actor_names = {actor_entity._name for actor_entity in actor_entities}
            stage_name = stage_entity._name
            names_mapping[stage_name] = list(actor_names)

        logger.warning(f"names_mapping = {names_mapping}")

    ############################################################################################################
