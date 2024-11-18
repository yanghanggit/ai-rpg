from enum import unique, StrEnum
from entitas import ExecuteProcessor, Matcher  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from my_components.components import ActorComponent, StageComponent
from typing import final, override, Dict
from rpg_game.rpg_game import RPGGame
import gameplay_systems.prompt_utils as prompt_utils


class CompressChatHistoryConstantPrompt(StrEnum):
    COMPRESS_ACTOR_PLAN_PROMPT = "请做出你的计划，决定你将要做什么"
    COMPRESS_STAGE_PLAN_PROMPT = "请做出你的计划，决定你将要做什么"


############################################################################################################


@final
class CompressChatHistorySystem(ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:
        # 这个很有危险
        self._process_chat_history_compression()

    ############################################################################################################
    def _process_chat_history_compression(self) -> None:
        chat_history_replacement_map: Dict[str, str] = {
            prompt_utils.PromptTag.ACTOR_PLAN_PROMPT_TAG: CompressChatHistoryConstantPrompt.COMPRESS_ACTOR_PLAN_PROMPT,
            prompt_utils.PromptTag.STAGE_PLAN_PROMPT_TAG: CompressChatHistoryConstantPrompt.COMPRESS_STAGE_PLAN_PROMPT,
        }

        entities = self._context.get_group(
            Matcher(any_of=[ActorComponent, StageComponent])
        ).entities

        for entity in entities:
            self._context.agent_system.replace_messages(
                self._context.safe_get_entity_name(entity), chat_history_replacement_map
            )


############################################################################################################
