from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from components.actions import (
    GoToAction,
    DeadAction,
)
from components.components import (
    ActorComponent,
    StageGraphComponent,
)
from game.rpg_game_context import RPGGameContext
from loguru import logger
from typing import final, override, Set, NamedTuple
from game.rpg_game import RPGGame
from rpg_models.event_models import AgentEvent


################################################################################################################################################
def _generate_stage_validation_error_prompt(actor_name: str, stage_name: str) -> str:
    return f"""# 提示：{actor_name} 无法前往场景：{stage_name}
## 原因分析
1. 场景: {stage_name}，目前不可访问，可能未开放或已关闭。
2. 场景全名格式错误，会导致系统识别失败。请确保使用的 场景全名（见‘全名机制’）严格匹配！
3. {actor_name} 当前所在的场景与目标场景:{stage_name} 之间没有路径连接。
## 建议
请{actor_name} 重新考虑目的地。"""


################################################################################################################################################
def _generate_stage_conflict_prompt(actor_name: str, stage_name: str) -> str:
    return f"""# 提示：注意！{actor_name} 已经在 {stage_name} 场景中。
## 原因分析与建议
去往 {stage_name} 场景是重复且无意义的。
请重新考虑去往的目的地"""


###############################################################################################################################################
@final
class StageValidatorSystem(ReactiveProcessor):

    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGGameContext = context
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
            if not self._validate_stage_transition(entity):
                self._remove_action_component(entity)

    ###############################################################################################################################################
    def _validate_stage_transition(self, entity: Entity) -> bool:
        safe_actor_name = self._context.safe_get_entity_name(entity)
        current_stage_entity = self._context.safe_get_stage_entity(entity)
        assert current_stage_entity is not None
        if current_stage_entity is None:
            logger.error(f"{safe_actor_name}没有当前场景，这是个错误")
            return False

        target_stage_name = self._get_target_stage_name(entity)
        target_stage_entity = self._context.get_stage_entity(
            self._get_target_stage_name(entity)
        )
        if target_stage_entity is None:

            self._context.notify_event(
                set({entity}),
                AgentEvent(
                    message=_generate_stage_validation_error_prompt(
                        safe_actor_name, target_stage_name
                    )
                ),
            )

            return False

        if current_stage_entity == target_stage_entity:

            self._context.notify_event(
                set({entity}),
                AgentEvent(
                    message=_generate_stage_conflict_prompt(
                        safe_actor_name, target_stage_name
                    )
                ),
            )

            return False

        stage_graph_comp = current_stage_entity.get(StageGraphComponent)
        if len(stage_graph_comp.stage_graph) > 0:
            if target_stage_name not in stage_graph_comp.stage_graph:

                self._context.notify_event(
                    set({entity}),
                    AgentEvent(
                        message=_generate_stage_validation_error_prompt(
                            safe_actor_name, target_stage_name
                        )
                    ),
                )
                return False

        return True

    ###############################################################################################################################################
    def _get_target_stage_name(self, actor_entity: Entity) -> str:
        assert actor_entity.has(ActorComponent)
        assert actor_entity.has(GoToAction)
        go_to_action = actor_entity.get(GoToAction)
        if len(go_to_action.values) == 0:
            return ""
        return str(go_to_action.values[0])

    ###############################################################################################################################################
    def _remove_action_component(
        self, actor_entity: Entity, action_comps: Set[type[NamedTuple]] = {GoToAction}
    ) -> None:

        for action_comp in action_comps:
            if actor_entity.has(action_comp):
                actor_entity.remove(action_comp)

    ###############################################################################################################################################
