from ..entitas import Entity, Matcher, GroupEvent
from typing import final, override
from ..tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem
from ..models import AnnounceAction, HomeComponent, HeroComponent, AnnounceEvent


####################################################################################################################################
def _generate_prompt(
    announcer_name: str, announcement_message: str, event_stage: str
) -> str:
    return f"""# 发生事件: {announcer_name} 宣布: {announcement_message}
## {announcer_name} 所在场景: {event_stage}"""


####################################################################################################################################


@final
class AnnounceActionSystem(BaseActionReactiveSystem):

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
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._prosses_announce_action(entity)

    ####################################################################################################################################
    def _prosses_announce_action(self, entity: Entity) -> None:

        assert entity.has(HeroComponent)
        if not entity.has(HeroComponent):
            # 不是hero，不处理
            return

        home_stage_entity = self._game.safe_get_stage_entity(entity)
        assert home_stage_entity is not None
        if home_stage_entity is None:
            return

        assert home_stage_entity.has(HomeComponent)
        if not home_stage_entity.has(HomeComponent):
            # 不是home场景，不处理
            return

        announce_action = entity.get(AnnounceAction)
        assert announce_action is not None
        assert announce_action.data != ""
        if announce_action.data == "":
            return

        # 获取所有需要进行角色规划的角色
        home_stage_entities = self._game.get_group(
            Matcher(
                all_of=[
                    HomeComponent,
                ],
            )
        ).entities

        for home_stage_entity in home_stage_entities:
            self._game.broadcast_event(
                home_stage_entity,
                AnnounceEvent(
                    message=_generate_prompt(
                        entity.get(HeroComponent).name,
                        announce_action.data,
                        home_stage_entity.get(HomeComponent).name,
                    ),
                    announcement_speaker=entity.get(HeroComponent).name,
                    event_stage=home_stage_entity.get(HomeComponent).name,
                    announcement_message=announce_action.data,
                ),
            )

    ####################################################################################################################################
