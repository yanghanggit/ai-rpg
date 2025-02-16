from enum import Enum
from entitas import ReactiveProcessor, Entity  # type: ignore
from game.tcg_game_context import TCGGameContext
from typing import cast, Optional
from game.tcg_game import TCGGame


class ConversationError(Enum):
    VALID = 0
    INVALID_TARGET = 1
    NO_STAGE = 2
    NOT_SAME_STAGE = 3


####################################################################################################################################
class BaseActionReactiveSystem(ReactiveProcessor):

    def __init__(self, context: TCGGameContext) -> None:
        super().__init__(context)
        self._context: TCGGameContext = context
        self._game: TCGGame = cast(TCGGame, context._game)
        assert self._game is not None

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
