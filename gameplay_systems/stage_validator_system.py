from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from gameplay_systems.action_components import (
    GoToAction,
    DeadAction,
)
from gameplay_systems.components import (
    StageComponent,
    ActorComponent,
    StageGraphComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
import gameplay_systems.public_builtin_prompt as public_builtin_prompt
from typing import final, override, Set, Any
from rpg_game.rpg_game import RPGGame
from my_models.models_def import AgentEvent


################################################################################################################################################
def _generate_stage_validation_error_prompt(actor_name: str, stage_name: str) -> str:
    return f"""# {actor_name} 无法前往 {stage_name}
## 可能的原因
1. {stage_name} 目前不可访问，可能未开放或已关闭。
2. 场景名称"{stage_name}"格式不正确,如“xxx的深处/北部/边缘/附近/其他区域”，这样的表达可能导致无法正确识别。
    - 必须根据 游戏规则设定 中 对场景名字严格匹配。
3. {actor_name} 无法从当前场景去往 {stage_name}。即当前场景与目标场景{stage_name}之间没有连接。
## 建议
- 请 {actor_name} 重新考虑目的地。"""


################################################################################################################################################
def _generate_stage_already_in_prompt(actor_name: str, stage_name: str) -> str:
    return f"# 注意！{actor_name} 已经在 {stage_name} 场景中。需要重新考虑去往的目的地"


###############################################################################################################################################
@final
class StageValidatorSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ###############################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(GoToAction): GroupEvent.ADDED}

    ###############################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(GoToAction)
            and entity.has(ActorComponent)
            and not entity.has(DeadAction)
        )

    ###############################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:

        for entity in entities:
            if not self.handle(entity):
                self.on_remove_action(entity)

    ###############################################################################################################################################
    def handle(self, entity: Entity) -> bool:
        safe_actor_name = self._context.safe_get_entity_name(entity)
        current_stage_entity = self._context.safe_get_stage_entity(entity)
        if current_stage_entity is None:
            # assert False, f"{safe_actor_name}没有当前场景，这是个错误"
            logger.error(f"{safe_actor_name}没有当前场景，这是个错误")
            return False

        target_stage_name = self.get_target_stage_name(entity)
        target_stage_entity = self._context.get_stage_entity(
            self.get_target_stage_name(entity)
        )
        if target_stage_entity is None:

            self._context.notify_event(
                set({entity}),
                AgentEvent(
                    message_content=_generate_stage_validation_error_prompt(
                        safe_actor_name, target_stage_name
                    )
                ),
            )

            return False

        if current_stage_entity == target_stage_entity:

            self._context.notify_event(
                set({entity}),
                AgentEvent(
                    message_content=_generate_stage_already_in_prompt(
                        safe_actor_name, target_stage_name
                    )
                ),
            )

            return False

        assert current_stage_entity.has(StageGraphComponent)
        stage_graph_comp = current_stage_entity.get(StageGraphComponent)
        if len(stage_graph_comp.stage_graph) > 0:
            if target_stage_name not in stage_graph_comp.stage_graph:

                self._context.notify_event(
                    set({entity}),
                    AgentEvent(
                        message_content=_generate_stage_validation_error_prompt(
                            safe_actor_name, target_stage_name
                        )
                    ),
                )
                return False

        return True

    ###############################################################################################################################################
    def get_target_stage_name(self, actor_entity: Entity) -> str:
        assert actor_entity.has(ActorComponent)
        assert actor_entity.has(GoToAction)

        go_to_action = actor_entity.get(GoToAction)
        if len(go_to_action.values) == 0:
            return ""

        if public_builtin_prompt.is_stage_name_unknown(go_to_action.values[0]):
            guid = public_builtin_prompt.extract_stage_guid(go_to_action.values[0])
            stage_entity = self._context.get_entity_by_guid(guid)
            if stage_entity is not None and stage_entity.has(StageComponent):
                return self._context.safe_get_entity_name(stage_entity)

        return str(go_to_action.values[0])

    ###############################################################################################################################################
    def on_remove_action(
        self, actor_entity: Entity, action_comps: Set[type[Any]] = {GoToAction}
    ) -> None:

        for action_comp in action_comps:
            if actor_entity.has(action_comp):
                actor_entity.remove(action_comp)

    ###############################################################################################################################################
