from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from my_components.action_components import (
    StealPropAction,
    DeadAction,
)
from my_components.components import (
    ActorComponent,
)
import gameplay_systems.action_component_utils
from typing import final, override
import gameplay_systems.file_system_utils
from extended_systems.prop_file import PropFile
import my_format_string.target_message
from rpg_game.rpg_game import RPGGame
from loguru import logger
from my_models.event_models import AgentEvent

####################################################################################################################################


def _generate_steal_prompt(
    source_name: str, target_name: str, prop_name: str, action_result: bool
) -> str:
    if not action_result:
        return f"# 发生事件: {source_name} 试图从 {target_name} 盗取 {prop_name}, 但是失败了。"

    return f"""# 发生事件: {source_name} 从 {target_name} 成功盗取了 {prop_name}。
# 导致结果
- {target_name} 现在不再拥有 {prop_name}。
- {source_name} 现在拥有了 {prop_name}。"""


####################################################################################################################################


@final
class StealActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame):
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(StealPropAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(StealPropAction)
            and entity.has(ActorComponent)
            and not entity.has(DeadAction)
        )

    ####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_steal_action(entity)

    ####################################################################################################################################
    def _process_steal_action(self, source_entity: Entity) -> None:

        steal_action: StealPropAction = source_entity.get(StealPropAction)
        target_and_message = (
            my_format_string.target_message.extract_target_message_pairs(
                steal_action.values
            )
        )

        for target_entity_name, prop_file_name in target_and_message:

            if (
                gameplay_systems.action_component_utils.validate_conversation(
                    self._context, source_entity, target_entity_name
                )
                != gameplay_systems.action_component_utils.ConversationError.VALID
            ):
                # 不能交谈就是不能偷
                continue

            target_entity = self._context.get_entity_by_name(target_entity_name)
            if target_entity is None:
                # 不存在的目标
                continue

            # 判断文件的合理性
            target_prop_file = self._context.file_system.get_file(
                PropFile, target_entity_name, prop_file_name
            )

            if target_prop_file is None or not target_prop_file.is_non_consumable_item:
                self._notify_steal_event(
                    source_entity=source_entity,
                    target_entity=target_entity,
                    prop_file_name=prop_file_name,
                    steal_action_result=False,
                )
                continue

            ## 执行偷窃
            self._execute_steal_action(source_entity, target_entity, target_prop_file)

            ## 通知事件
            self._notify_steal_event(
                source_entity=target_entity,
                target_entity=target_entity,
                prop_file_name=prop_file_name,
                steal_action_result=True,
            )

    ####################################################################################################################################
    def _notify_steal_event(
        self,
        source_entity: Entity,
        target_entity: Entity,
        prop_file_name: str,
        steal_action_result: bool,
    ) -> None:

        target_entity_name = self._context.safe_get_entity_name(target_entity)
        self._context.notify_event(
            set({source_entity, target_entity}),
            AgentEvent(
                message=_generate_steal_prompt(
                    self._context.safe_get_entity_name(source_entity),
                    target_entity_name,
                    prop_file_name,
                    steal_action_result,
                )
            ),
        )

    ####################################################################################################################################
    def _execute_steal_action(
        self, source_entity: Entity, target_entity: Entity, target_prop_file: PropFile
    ) -> None:

        target_actor_name = self._context.safe_get_entity_name(target_entity)
        gameplay_systems.file_system_utils.transfer_file(
            self._context.file_system,
            target_actor_name,
            self._context.safe_get_entity_name(source_entity),
            target_prop_file.name,
        )

    ####################################################################################################################################


####################################################################################################################################
