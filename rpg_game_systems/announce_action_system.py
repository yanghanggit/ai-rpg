from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from typing import final, override
from components.actions import AnnounceAction
from game.rpg_game_context import RPGGameContext
from game.rpg_game import RPGGame
from rpg_models.event_models import AnnounceEvent


####################################################################################################
def _generate_announce_prompt(speaker_name: str, stage_name: str, content: str) -> str:
    return f"# 发生事件: {speaker_name} 对 {stage_name} 里的所有角色说: {content}"


####################################################################################################
####################################################################################################
####################################################################################################


@final
class AnnounceActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game

    ####################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(AnnounceAction): GroupEvent.ADDED}

    ####################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(AnnounceAction)

    ####################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_announce_action(entity)

    ####################################################################################################
    def _process_announce_action(self, entity: Entity) -> None:
        stage_entity = self._context.safe_get_stage_entity(entity)
        if stage_entity is None:
            return

        announce_action = entity.get(AnnounceAction)
        stage_name = self._context.safe_get_entity_name(stage_entity)
        content = " ".join(announce_action.values)
        self._context.broadcast_event(
            stage_entity,
            AnnounceEvent(
                message=_generate_announce_prompt(
                    announce_action.name,
                    stage_name,
                    content,
                ),
                announcer_name=announce_action.name,
                stage_name=stage_name,
                content=content,
            ),
        )

    ####################################################################################################
