from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from my_components.action_components import (
    InspectAction,
    DeadAction,
)
from my_components.components import (
    ActorComponent,
)
from typing import final, override, List
from rpg_game.rpg_game import RPGGame
import gameplay_systems.file_system_utils
from extended_systems.prop_file import PropFile
from rpg_game.rpg_game import RPGGame
from loguru import logger
from my_models.event_models import AgentEvent
import gameplay_systems.action_component_utils
from gameplay_systems.actor_entity_utils import ActorStatusEvaluator
from extended_systems.prop_file import (
    PropFile,
    generate_prop_file_appearance_prompt,
)


####################################################################################################################################
def _generate_invalid_target_prompt(source_name: str, target_name: str) -> str:
    return f"""# 提示: {source_name} 对 {target_name} 进行执行 探查 行动失败。
# 原因分析
- {target_name} 不存在，或者不是可以被 探查 的对象。
- {target_name} 与 {source_name} 已不在同一个场景中。"""


#######################################################################################################################################
def _generate_inspect_prompt(
    source_name: str,
    target_name: str,
    health_description: str,
    prop_files: List[PropFile],
) -> str:
    # 道具信息
    props_prompt = [generate_prop_file_appearance_prompt(prop) for prop in prop_files]
    if len(props_prompt) == 0:
        props_prompt.append("无")

    # 最终返回
    return f"""# 发生事件: {source_name} 对 {target_name} 进行了探查。获得了如下信息。
## {target_name} 健康状态
生命值: {health_description}
## {target_name} 可以被探查到的道具
{"\n".join(props_prompt)}"""


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
@final
class InspectActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame):
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(InspectAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(InspectAction)
            and entity.has(ActorComponent)
            and not entity.has(DeadAction)
        )

    ####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_inspect_action(entity)

    ####################################################################################################################################
    def _process_inspect_action(self, source_entity: Entity) -> None:

        inspect_action: InspectAction = source_entity.get(InspectAction)
        if len(inspect_action.values) == 0:
            return

        for target_name in inspect_action.values:

            if (
                gameplay_systems.action_component_utils.validate_conversation(
                    self._context, source_entity, target_name
                )
                != gameplay_systems.action_component_utils.ConversationError.VALID
            ):
                self._notify_invalid_target_event(source_entity, target_name)
                continue

            target_entity = self._context.get_entity_by_name(target_name)
            assert target_entity is not None, f"未找到名为 {target_name} 的实体。"
            if target_entity is None or not target_entity.has(ActorComponent):
                # 不存在的目标
                self._notify_invalid_target_event(source_entity, target_name)
                continue

            self._notify_inspect_event(source_entity, target_entity)

    ####################################################################################################################################
    def _notify_inspect_event(
        self, source_entity: Entity, target_entity: Entity
    ) -> None:

        assert target_entity.has(ActorComponent)
        actor_status_evaluator = ActorStatusEvaluator(self._context, target_entity)
        self._context.notify_event(
            set({source_entity}),
            AgentEvent(
                message=_generate_inspect_prompt(
                    self._context.safe_get_entity_name(source_entity),
                    actor_status_evaluator.actor_name,
                    actor_status_evaluator.format_health_info,
                    actor_status_evaluator.inspectable_prop_files,
                )
            ),
        )

    ####################################################################################################################################
    def _notify_invalid_target_event(
        self,
        source_entity: Entity,
        target_name: str,
    ) -> None:

        self._context.notify_event(
            set({source_entity}),
            AgentEvent(
                message=_generate_invalid_target_prompt(
                    self._context.safe_get_entity_name(source_entity),
                    target_name,
                )
            ),
        )

    ####################################################################################################################################
