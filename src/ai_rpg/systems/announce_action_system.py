from typing import Set, final, override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor

# from ..game_systems.base_action_reactive_system import BaseActionReactiveSystem
from ..models import AnnounceAction, AnnounceEvent, HomeComponent, DungeonComponent
from ..game.tcg_game import TCGGame


####################################################################################################################################
def _generate_prompt(
    announcer_name: str, announcement_message: str, event_stage: str
) -> str:
    return f"""# 发生事件: {announcer_name} 宣布: {announcement_message}

## {announcer_name} 所在场景: {event_stage}"""


####################################################################################################################################


@final
class AnnounceActionSystem(ReactiveProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: TCGGame = game_context

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(AnnounceAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(AnnounceAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._prosses_action(entity)

    ####################################################################################################################################
    def _prosses_action(self, entity: Entity) -> None:

        current_stage_entity = self._game.safe_get_stage_entity(entity)
        assert current_stage_entity is not None
        announce_action = entity.get(AnnounceAction)
        assert announce_action is not None

        stage_entities: Set[Entity] = set()

        # 根据当前场景类型，选择相应的广播范围
        if current_stage_entity.has(HomeComponent):

            stage_entities = self._game.get_group(
                Matcher(
                    all_of=[
                        HomeComponent,
                    ],
                )
            ).entities.copy()

        elif current_stage_entity.has(DungeonComponent):

            stage_entities = self._game.get_group(
                Matcher(
                    all_of=[
                        DungeonComponent,
                    ],
                )
            ).entities.copy()
        else:
            assert False, "未知的场景类型，无法广播公告。"

        # 广播事件
        for stage_entity in stage_entities:

            self._game.broadcast_to_stage(
                stage_entity,
                AnnounceEvent(
                    message=_generate_prompt(
                        entity.name,
                        announce_action.message,
                        stage_entity.name,
                    ),
                    actor=entity.name,
                    stage=stage_entity.name,
                    content=announce_action.message,
                ),
            )

    ####################################################################################################################################
