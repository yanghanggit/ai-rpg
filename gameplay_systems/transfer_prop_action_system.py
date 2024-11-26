from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from my_components.action_components import (
    TransferPropAction,
    DeadAction,
)
from my_components.components import ActorComponent
import gameplay_systems.action_component_utils
from typing import final, override
import gameplay_systems.file_system_utils
from extended_systems.prop_file import PropFile
import my_format_string.target_message
from rpg_game.rpg_game import RPGGame
from my_models.event_models import AgentEvent
import my_format_string.complex_prop_name
from extended_systems.prop_file import generate_prop_type_prompt


@final
class TransferPropActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame):
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(TransferPropAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(TransferPropAction)
            and entity.has(ActorComponent)
            and not entity.has(DeadAction)
        )

    ####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_transfer_prop_action(entity)

    ####################################################################################################################################
    def _process_transfer_prop_action(self, entity: Entity) -> None:

        transfer_prop_action = entity.get(TransferPropAction)
        target_and_message = (
            my_format_string.target_message.extract_target_message_pairs(
                values=transfer_prop_action.values, symbol1="@", symbol2="/"
            )
        )

        for target_name, complex_prop_name in target_and_message:

            if (
                gameplay_systems.action_component_utils.validate_conversation(
                    self._context, entity, target_name
                )
                != gameplay_systems.action_component_utils.ConversationError.VALID
            ):
                # 目标不存在
                self._notify_target_inaccessible_event(entity, target_name)
                continue

            ## 获取目标实体
            target_entity = self._context.get_actor_entity(target_name)
            assert target_entity is not None

            ## 分析数据
            parsed_prop_name, parsed_transfer_count = (
                my_format_string.complex_prop_name.parse_complex_prop_name(
                    complex_prop_name
                )
            )

            transferable_prop_file = self._context.file_system.get_file(
                PropFile, transfer_prop_action.name, parsed_prop_name
            )
            if transferable_prop_file is None:
                # 提示 道具不存在
                self._notify_invalid_prop_usage_event(entity, complex_prop_name)
                continue

            if not (
                transferable_prop_file.is_consumable_item
                or transferable_prop_file.is_non_consumable_item
            ):
                # 提示 类型不对, 只能2种类型。
                self._notify_invalid_prop_type_event(entity, transferable_prop_file)
                continue

            if (
                parsed_transfer_count > transferable_prop_file.count
                or parsed_transfer_count <= 0
            ):
                # 提示 数量错误。
                self._notify_invalid_transfer_count_event(
                    entity, transferable_prop_file, parsed_transfer_count
                )
                continue

            # 核心执行逻辑
            gameplay_systems.file_system_utils.transfer_file(
                self._context.file_system,
                transferable_prop_file.owner_name,
                self._context.safe_get_entity_name(target_entity),
                transferable_prop_file.name,
                parsed_transfer_count,
            )

            # 提示 完成转移。
            self._notify_prop_transfer_completion(
                entity, target_entity, transferable_prop_file, parsed_transfer_count
            )

    ####################################################################################################################################
    def _notify_invalid_prop_usage_event(
        self, source_entity: Entity, complex_prop_name: str
    ) -> None:
        source_name = self._context.safe_get_entity_name(source_entity)

        prompt = f"""# 提示: {source_name} 试图执行({TransferPropAction.__name__}), 但是失败了。
## 分析与建议
- 输入的道具的参数不正确: {complex_prop_name}。
- 注意正确的格式: "{TransferPropAction.__name__}":["@道具接收角色全名(只能是场景内的角色)/交付的道具全名=数量"]"""

        self._context.notify_event(
            set({source_entity}),
            AgentEvent(
                message=prompt,
            ),
        )

    ####################################################################################################################################
    def _notify_invalid_prop_type_event(
        self, source_entity: Entity, prop_file: PropFile
    ) -> None:
        source_name = self._context.safe_get_entity_name(source_entity)

        prompt = f"""# 提示: {source_name} 试图执行({TransferPropAction.__name__}), 但是失败了。
## 分析与建议
- {prop_file.name} 不是可以执行操作的道具。类型为: {generate_prop_type_prompt(prop_file)}。
- 只能是 非消耗品 与 消耗品 2种类型。其余类型的道具无法移交。"""

        self._context.notify_event(
            set({source_entity}),
            AgentEvent(
                message=prompt,
            ),
        )

    ####################################################################################################################################
    def _notify_invalid_transfer_count_event(
        self, source_entity: Entity, prop_file: PropFile, transfer_count: int
    ) -> None:
        source_name = self._context.safe_get_entity_name(source_entity)

        prompt = f"""提示: {source_name} 试图执行({TransferPropAction.__name__}), 但是失败了。
## 分析与建议
- 转移数量错误: {transfer_count}。请确保转移的数量在合理范围内。
- {prop_file.name} 的数量不足以执行操作。当前数量: {prop_file.count}。"""

        self._context.notify_event(
            set({source_entity}),
            AgentEvent(
                message=prompt,
            ),
        )

    ####################################################################################################################################
    def _notify_prop_transfer_completion(
        self,
        source_entity: Entity,
        target_entity: Entity,
        prop_file: PropFile,
        transfer_count: int,
    ) -> None:

        source_name = self._context.safe_get_entity_name(source_entity)
        target_name = self._context.safe_get_entity_name(target_entity)
        prompt = f"""# 提示: {source_name} 成功将道具转移({TransferPropAction.__name__})给{target_name}。
## 详情
- 转移道具: {prop_file.name}
- 数量: {transfer_count}"""

        self._context.notify_event(
            set({source_entity, target_entity}),
            AgentEvent(
                message=prompt,
            ),
        )

        # 如果全部交易完毕，道具将会被移除。
        if prop_file.count == 0:
            self._notify_prop_removal_event(source_entity, prop_file)

    ####################################################################################################################################
    def _notify_prop_removal_event(
        self, source_entity: Entity, prop_file: PropFile
    ) -> None:
        if prop_file.count > 0:
            return

        source_name = self._context.safe_get_entity_name(source_entity)
        assert (
            self._context.file_system.get_file(
                PropFile, prop_file.owner_name, prop_file.name
            )
            is None
        ), f"道具 {prop_file.name} 未被移除。"

        prompt = f"""# 提示: {source_name} 在执行 {TransferPropAction.__name__} 成功后。{prop_file.name} 为 {prop_file.count}。以被移除。"""
        self._context.notify_event(
            set({source_entity}),
            AgentEvent(
                message=prompt,
            ),
        )

    ####################################################################################################################################
    def _notify_target_inaccessible_event(
        self,
        source_entity: Entity,
        target_name: str,
    ) -> None:

        source_name = self._context.safe_get_entity_name(source_entity)

        prompt = f"""# 提示: {source_name} 试图将道具转移({TransferPropAction.__name__}) {target_name}, 但失败了。
## 原因分析与建议
- 请检查目标的全名: {target_name}，确保是完整匹配:游戏规则-全名机制
- 请检查目标是否存在于当前场景中。"""

        self._context.notify_event(
            set({source_entity}),
            AgentEvent(
                message=prompt,
            ),
        )

    ####################################################################################################################################
