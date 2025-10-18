from typing import final, override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor

# from ..game_systems.base_action_reactive_system import BaseActionReactiveSystem
from ..models import DiscussionAction, DiscussionEvent
from ..game.tcg_game import RPGGame


####################################################################################################################################
def _generate_prompt(
    discussion_actor_name: str, discussion_message: str, event_stage: str
) -> str:
    return f"""# 发生事件: {discussion_actor_name} 发言

## 所在场景: {event_stage}

## 发言内容:

{discussion_message} """


####################################################################################################################################


@final
class DiscussionActionSystem(ReactiveProcessor):

    def __init__(self, game_context: RPGGame) -> None:
        super().__init__(game_context)
        self._game: RPGGame = game_context

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(DiscussionAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(DiscussionAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._prosses_action(entity)

    ####################################################################################################################################
    def _prosses_action(self, entity: Entity) -> None:

        current_stage_entity = self._game.safe_get_stage_entity(entity)
        assert current_stage_entity is not None, "实体必须处于某个场景中"

        discussion_action = entity.get(DiscussionAction)
        assert discussion_action is not None

        # logger.debug(
        #     f"讨论行动: {entity.name} 在场景 {current_stage_entity.name} 说: {discussion_action.message}"
        # )
        self._game.broadcast_to_stage(
            current_stage_entity,
            DiscussionEvent(
                message=_generate_prompt(
                    entity.name,
                    discussion_action.message,
                    current_stage_entity.name,
                ),
                actor=entity.name,
                stage=current_stage_entity.name,
                content=discussion_action.message,
            ),
        )

    ####################################################################################################################################
