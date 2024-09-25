from entitas import ExecuteProcessor, Matcher, Entity  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from gameplay_systems.components import ActorComponent, StageComponent
from typing import Set, override, Dict
from rpg_game.rpg_game import RPGGame
import gameplay_systems.public_builtin_prompt as public_builtin_prompt


class CompressChatHistorySystem(ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:
        # 这个很有危险
        # self.handle_exclude_chat_history()
        self.handle_compress_chat_history()

    ############################################################################################################
    def handle_exclude_chat_history(self) -> None:

        tags: Set[str] = {
            public_builtin_prompt.ConstantPrompt.ACTOR_PLAN_PROMPT_TAG,
            public_builtin_prompt.ConstantPrompt.STAGE_PLAN_PROMPT_TAG,
        }

        entities: Set[Entity] = self._context.get_group(
            Matcher(any_of=[ActorComponent, StageComponent])
        ).entities

        for entity in entities:

            safe_name = self._context.safe_get_entity_name(entity)
            filters = self._context._langserve_agent_system.filter_messages_by_keywords(
                safe_name, tags
            )
            self._context._langserve_agent_system.filter_chat_history(
                safe_name, filters
            )

    ############################################################################################################
    def handle_compress_chat_history(self) -> None:
        context = self._context
        replace_data: Dict[str, str] = {
            public_builtin_prompt.ConstantPrompt.ACTOR_PLAN_PROMPT_TAG: public_builtin_prompt.ConstantPrompt.COMPRESS_ACTOR_PLAN_PROMPT,
            public_builtin_prompt.ConstantPrompt.STAGE_PLAN_PROMPT_TAG: public_builtin_prompt.ConstantPrompt.COMPRESS_STAGE_PLAN_PROMPT,
        }

        entities = context.get_group(
            Matcher(any_of=[ActorComponent, StageComponent])
        ).entities

        for entity in entities:
            safename = context.safe_get_entity_name(entity)
            if safename == "":
                continue
            context._langserve_agent_system.modify_chat_history(safename, replace_data)


############################################################################################################
