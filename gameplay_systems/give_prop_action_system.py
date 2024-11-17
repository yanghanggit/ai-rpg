from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from my_components.action_components import (
    GivePropAction,
    DeadAction,
)
from my_components.components import ActorComponent
import gameplay_systems.action_component_utils
from typing import final, override
import gameplay_systems.file_system_utils
from extended_systems.prop_file import PropFile
import my_format_string.target_and_message_format_string
from rpg_game.rpg_game import RPGGame
from my_models.event_models import AgentEvent
from loguru import logger


################################################################################################################################################
def _generate_lost_target_prompt(source_name: str, target_name: str) -> str:
    return f"# 提示: {source_name} 试图将道具给予 {target_name}, 但是失败了。"


################################################################################################################################################
def _generate_give_prop_prompt(
    source_name: str, target_name: str, prop_name: str, action_result: bool
) -> str:
    if not action_result:
        return (
            f"# 提示: {source_name} 试图将 {prop_name} 给予 {target_name}, 但是失败了。"
        )

    return f"""# 发生事件: {source_name} 将 {prop_name} 成功给予了 {target_name}。
## 导致结果
- {source_name} 现在不再拥有 {prop_name}。
- {target_name} 现在拥有了 {prop_name}。"""


################################################################################################################################################
################################################################################################################################################
################################################################################################################################################


@final
class GivePropActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame):
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(GivePropAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(GivePropAction)
            and entity.has(ActorComponent)
            and not entity.has(DeadAction)
        )

    ####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_give_prop_action(entity)

    ####################################################################################################################################
    def _process_give_prop_action(self, entity: Entity) -> None:

        give_prop_action = entity.get(GivePropAction)
        target_and_message = (
            my_format_string.target_and_message_format_string.target_and_message_values(
                give_prop_action.values, "@", "/"
            )
        )

        for target_name, prop_name in target_and_message:

            if (
                gameplay_systems.action_component_utils.validate_conversation(
                    self._context, entity, target_name
                )
                != gameplay_systems.action_component_utils.ConversationError.VALID
            ):
                # 不能交谈就是不能交换道具
                logger.warning("不能交谈就是不能交换道具")
                self._notify_lost_target_event(entity, target_name)
                continue

            target_entity = self._context.get_actor_entity(target_name)
            assert target_entity is not None

            action_result = self._give_prop(entity, target_entity, prop_name)
            self._notify_give_prop_event(
                entity, target_entity, prop_name, action_result
            )

    ####################################################################################################################################
    def _notify_lost_target_event(
        self,
        source_entity: Entity,
        target_name: str,
    ) -> None:
        self._context.notify_event(
            set({source_entity}),
            AgentEvent(
                message=_generate_lost_target_prompt(
                    source_name=self._context.safe_get_entity_name(source_entity),
                    target_name=target_name,
                )
            ),
        )

    ####################################################################################################################################
    def _notify_give_prop_event(
        self,
        source_entity: Entity,
        target_entity: Entity,
        prop_name: str,
        action_result: bool,
    ) -> None:
        self._context.notify_event(
            set({source_entity, target_entity}),
            AgentEvent(
                message=_generate_give_prop_prompt(
                    source_name=self._context.safe_get_entity_name(source_entity),
                    target_name=self._context.safe_get_entity_name(target_entity),
                    prop_name=prop_name,
                    action_result=action_result,
                )
            ),
        )

    ####################################################################################################################################
    def _give_prop(
        self, srouce_entity: Entity, target_entity: Entity, prop_name: str
    ) -> bool:
        safe_name = self._context.safe_get_entity_name(srouce_entity)
        prop_file = self._context.file_system.get_file(PropFile, safe_name, prop_name)
        if prop_file is None:
            return False
        gameplay_systems.file_system_utils.transfer_file(
            self._context.file_system,
            safe_name,
            self._context.safe_get_entity_name(target_entity),
            prop_file.name,
        )
        return True


####################################################################################################################################
