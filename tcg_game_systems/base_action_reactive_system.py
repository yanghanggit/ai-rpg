from enum import Enum
from entitas import ReactiveProcessor, CleanupProcessor, Entity  # type: ignore
from game.tcg_game_context import TCGGameContext
from typing import cast, Optional, Set, List, override
from game.tcg_game import TCGGame
from components.actions import GoToAction
from components.components import StageGraphComponent


class ConversationError(Enum):
    VALID = 0
    INVALID_TARGET = 1
    NO_STAGE = 2
    NOT_SAME_STAGE = 3


####################################################################################################################################
class BaseActionReactiveSystem(ReactiveProcessor, CleanupProcessor):

    def __init__(self, context: TCGGameContext) -> None:
        super().__init__(context)
        self._context: TCGGameContext = context
        self._game: TCGGame = cast(TCGGame, context._game)
        assert self._game is not None
        self._react_entities_copy: List[Entity] = []

    ####################################################################################################################################
    @override
    def cleanup(self) -> None:
        self._react_entities_copy.clear()

    ####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        assert len(self._react_entities_copy) == 0
        self._react_entities_copy = entities.copy()

    ####################################################################################################################################
    # 检查是否可以对话
    def validate_conversation(
        self, stage_or_actor: Entity, target_name: str
    ) -> ConversationError:

        actor_entity: Optional[Entity] = self._context.get_actor_entity(target_name)
        if actor_entity is None:
            return ConversationError.INVALID_TARGET

        current_stage_entity = self._context.safe_get_stage_entity(stage_or_actor)
        if current_stage_entity is None:
            return ConversationError.NO_STAGE

        target_stage_entity = self._context.safe_get_stage_entity(actor_entity)
        if target_stage_entity != current_stage_entity:
            return ConversationError.NOT_SAME_STAGE

        return ConversationError.VALID

    ####################################################################################################################################
    def _get_go_to_target_stage_name(self, entity: Entity) -> str:
        go_to_action = entity.get(GoToAction)
        if len(go_to_action.values) == 0:
            return ""
        return str(go_to_action.values[0])

    ####################################################################################################################################
    def _get_go_to_target_stage_entity(self, entity: Entity) -> Optional[Entity]:
        target_stage_name = self._get_go_to_target_stage_name(entity)
        if target_stage_name == "":
            return None
        return self._context.get_stage_entity(target_stage_name)

    ####################################################################################################################################
    def _retrieve_next_stage_entities(self, entity: Entity) -> Set[Entity]:

        current_stage_entity = self._context.safe_get_stage_entity(entity)
        if current_stage_entity is None:
            return set()

        stage_graph_comp = current_stage_entity.get(StageGraphComponent)
        if stage_graph_comp is None:
            return set()

        ret: Set[Entity] = set()

        for stage_name in stage_graph_comp.stage_graph:
            stage_entity = self._context.get_stage_entity(stage_name)
            if stage_entity is not None:
                ret.add(stage_entity)

        return ret


####################################################################################################################################
