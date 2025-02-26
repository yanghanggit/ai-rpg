from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity  # type: ignore
from game.rpg_game_context import RPGGameContext
from components.actions import (
    StealPropAction,
    DeadAction,
    InspectAction,
)
from components.components import (
    ActorComponent,
)
import rpg_game_systems.action_component_utils
from typing import final, override
import rpg_game_systems.file_system_utils
from extended_systems.prop_file import PropFile
import format_string.target_message
from game.rpg_game import RPGGame
from rpg_models.event_models import AgentEvent


@final
class StealPropActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGGameContext, rpg_game: RPGGame):
        super().__init__(context)
        self._context: RPGGameContext = context
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
        target_and_message = format_string.target_message.extract_target_message_pairs(
            values=steal_action.values, symbol1="@", symbol2="/"
        )

        for target_entity_name, prop_file_name in target_and_message:

            error = rpg_game_systems.action_component_utils.validate_conversation(
                self._context, source_entity, target_entity_name
            )
            if error != rpg_game_systems.action_component_utils.ConversationError.VALID:
                # 目标不存在
                self._notify_target_inaccessible_event(
                    source_entity, target_entity_name
                )
                continue

            target_entity = self._context.get_entity_by_name(target_entity_name)
            assert target_entity is not None

            # 判断文件的合理性
            target_prop_file = self._context.file_system.get_file(
                PropFile, target_entity_name, prop_file_name
            )

            if target_prop_file is None:
                # 道具不存在。
                self._notify_prop_not_found_event(
                    source_entity,
                    target_entity=target_entity,
                    prop_file_name=prop_file_name,
                )
                continue

            if not target_prop_file.is_non_consumable_item:
                # 道具不可被盗取, 就当道具不存在提示。
                self._notify_prop_not_found_event(
                    source_entity,
                    target_entity=target_entity,
                    prop_file_name=prop_file_name,
                )
                continue

            ## 执行偷窃 = 执行了道具的转移
            self._execute_transfer_prop(source_entity, target_entity, target_prop_file)

            ## 通知事件，成功盗取完成
            self._notify_steal_completed(
                source_entity=target_entity,
                target_entity=target_entity,
                target_prop_file=target_prop_file,
            )

    ####################################################################################################################################
    def _notify_prop_not_found_event(
        self, source_entity: Entity, target_entity: Entity, prop_file_name: str
    ) -> None:

        source_name = self._context.safe_get_entity_name(source_entity)
        target_name = self._context.safe_get_entity_name(target_entity)

        prompt = f"""# 提示: {source_name} 试图从 {target_name} 盗取道具 {prop_file_name}，但是失败了。
## 原因分析与建议
- 请检查道具的全名: {prop_file_name}，确保是完整匹配:游戏规则-全名机制
- 请检查道具是否存在于目标 {target_name} 身上。使用{InspectAction.__name__}查看目标的道具信息。
- {prop_file_name} 是否是可以被盗取的道具类型。"""

        self._context.notify_event(
            set({source_entity}),
            AgentEvent(message=prompt),
        )

    ####################################################################################################################################
    def _notify_target_inaccessible_event(
        self, source_entity: Entity, target_name: str
    ) -> None:

        source_name = self._context.safe_get_entity_name(source_entity)

        prompt = f"""# 提示: {source_name} 试图对一个不存在的目标 {target_name} 进行盗取{StealPropAction.__name__}。
    ## 原因分析与建议
    - 请检查目标的全名: {target_name}，确保是完整匹配:游戏规则-全名机制
    - 请检查目标是否存在于当前场景中。"""

        self._context.notify_event(
            set({source_entity}),
            AgentEvent(message=prompt),
        )

    ####################################################################################################################################
    def _notify_steal_completed(
        self,
        source_entity: Entity,
        target_entity: Entity,
        target_prop_file: PropFile,
    ) -> None:

        source_name = self._context.safe_get_entity_name(source_entity)
        target_name = self._context.safe_get_entity_name(target_entity)

        prompt = f"""# 发生事件: {source_name} 从 {target_name} 成功盗取了 {target_prop_file.name}。
## 导致结果
- {target_name} 现在不再拥有 {target_prop_file.name}。
- {source_name} 现在拥有了 {target_prop_file.name}。"""

        self._context.notify_event(
            set({source_entity, target_entity}),
            AgentEvent(message=prompt),
        )

    ####################################################################################################################################
    def _execute_transfer_prop(
        self, source_entity: Entity, target_entity: Entity, target_prop_file: PropFile
    ) -> None:

        rpg_game_systems.file_system_utils.transfer_file(
            self._context.file_system,
            self._context.safe_get_entity_name(target_entity),
            self._context.safe_get_entity_name(source_entity),
            target_prop_file.name,
            target_prop_file.count,
        )

    ####################################################################################################################################
