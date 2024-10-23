from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from typing import final, override
from gameplay_systems.action_components import RemovePropAction, StageNarrateAction
from rpg_game.rpg_entitas_context import RPGEntitasContext
from rpg_game.rpg_game import RPGGame
from extended_systems.files_def import PropFile
from gameplay_systems.components import StageComponent
from my_data.model_def import AgentEvent


def _generate_prop_lost_prompt(stage_name: str, prop_name: str) -> str:
    return f"""# 场景 {stage_name} 内的道具 {prop_name} 已经不在了，所以无法对其进行任何操作。
## 原因分析:
- 该道具可能已被移出场景，或被其他角色拾取。
"""


################################################################################################################################################


def _generate_successful_prop_removal_prompt(stage_name: str, prop_name: str) -> str:
    return f"""# 场景 {stage_name} 的道具 {prop_name} 已经被 {stage_name} 成功移除。
## 原因分析
- {prop_name} 已经因某种原因被摧毁。 {stage_name} 作为其拥有者，根据游戏机制，主动将其移除，以保证逻辑的连贯性与合理性。
## 造成结果
- {stage_name} 后续的 {StageNarrateAction.__name__} 的内容生成将不再提及 {prop_name}（及任何相关信息）"""


############################################################################################################
@final
class RemovePropActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(RemovePropAction): GroupEvent.ADDED}

    ############################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(RemovePropAction) and entity.has(StageComponent)

    ############################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.handle(entity)

    ############################################################################################################
    def handle(self, entity: Entity) -> None:
        remove_prop_action = entity.get(RemovePropAction)
        if len(remove_prop_action.values) == 0:
            return

        for prop_name in remove_prop_action.values:

            prop_file = self._context._file_system.get_file(
                PropFile, remove_prop_action.name, prop_name
            )
            if prop_file is None:
                self.on_prop_lost_event(entity, prop_name)
                continue

            self._context._file_system.remove_file(prop_file)
            self.on_prop_remove_event(entity, prop_name)

    ############################################################################################################
    def on_prop_lost_event(self, entity: Entity, prop_name: str) -> None:
        safe_name = self._context.safe_get_entity_name(entity)
        self._context.notify_event(
            set({entity}),
            AgentEvent(
                message_content=_generate_prop_lost_prompt(safe_name, prop_name)
            ),
        )

    ############################################################################################################
    def on_prop_remove_event(self, entity: Entity, prop_name: str) -> None:
        safe_name = self._context.safe_get_entity_name(entity)
        self._context.notify_event(
            set({entity}),
            AgentEvent(
                message_content=_generate_successful_prop_removal_prompt(
                    safe_name, prop_name
                )
            ),
        )

    ############################################################################################################
