from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from my_components.action_components import PickUpPropAction, DeadAction
from my_components.components import ActorComponent, StageComponent
from loguru import logger
from typing import final, override
from extended_systems.files_def import PropFile
import extended_systems.file_system_helper
from rpg_game.rpg_game import RPGGame
from my_models.event_models import AgentEvent


###############################################################################################################################################
def _generate_failed_pickup_prompt(actor_name: str, prop_name: str) -> str:
    return f"""# {actor_name} 无法拾取道具 {prop_name}
## 原因分析:
- {prop_name} 不是一个可拾取的道具。
- 该道具可能已被移出场景，或被其他角色拾取。
## 建议:
请{actor_name}重新考虑拾取的目标。"""


###############################################################################################################################################
def _generate_success_pickup_prompt(
    actor_name: str, prop_name: str, stage_name: str
) -> str:
    return f"""# {actor_name} 从 {stage_name} 场景内成功找到并获取了道具 {prop_name}。
## 导致结果:
- {stage_name} 此场景内不再有这个道具。"""


###############################################################################################################################################


@final
class PickUpPropActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame):
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(PickUpPropAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(PickUpPropAction)
            and entity.has(ActorComponent)
            and not entity.has(DeadAction)
        )

    ####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.handle(entity)

    ####################################################################################################################################
    def handle(self, entity: Entity) -> None:

        pick_up_prop_action = entity.get(PickUpPropAction)
        if len(pick_up_prop_action.values) == 0:
            return

        current_stage_entity = self._context.safe_get_stage_entity(entity)
        if current_stage_entity is None:
            logger.error(f"current_stage_entity is None")
            return

        actor_name = self._context.safe_get_entity_name(entity)
        stage_comp = current_stage_entity.get(StageComponent)

        for prop_name in pick_up_prop_action.values:

            prop_file = self._context._file_system.get_file(
                PropFile, stage_comp.name, prop_name
            )
            if prop_file is None:

                self._context.notify_event(
                    set({entity}),
                    AgentEvent(
                        message_content=_generate_failed_pickup_prompt(
                            actor_name, prop_name
                        )
                    ),
                )
                continue

            extended_systems.file_system_helper.give_prop_file(
                self._context._file_system,
                stage_comp.name,
                pick_up_prop_action.name,
                prop_name,
            )

            self._context.broadcast_event_in_stage(
                current_stage_entity,
                AgentEvent(
                    message_content=_generate_success_pickup_prompt(
                        actor_name, prop_name, stage_comp.name
                    )
                ),
            )

            # 写死的，只能拾取一次。
            break

    ####################################################################################################################################
