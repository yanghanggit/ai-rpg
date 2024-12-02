from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from components.action_components import GoToAction, DeadAction
from components.components import (
    ActorComponent,
    EnterStageFlagComponent,
    StageGraphComponent,
    StageEnvironmentComponent,
)
from game.rpg_game_context import RPGGameContext
from typing import final, override, Optional, Dict, List
from game.rpg_game import RPGGame
from models.event_models import AgentEvent, PreStageExitEvent, PostStageEnterEvent
import copy
from loguru import logger


################################################################################################################################################
def _generate_exit_stage_prompt(actor_name: str, current_stage_name: str) -> str:
    return f"# 发生事件: {actor_name} 离开了场景:{current_stage_name}。"


################################################################################################################################################
def _generate_stage_entry_prompt(actor_name: str, target_stage_name: str) -> str:
    return f"# 发生事件: {actor_name} 进入了场景:{target_stage_name}。"


################################################################################################################################################
def _generate_stage_change_prompt(
    actor_name: str, target_stage_name: str, previous_stage_name: str
) -> str:
    return f"# 发生事件: {actor_name} 离开了场景:{previous_stage_name}, 然后进入了场景:{target_stage_name}。"


################################################################################################################################################
def _generate_last_impression_prompt(
    actor_name: str,
    current_stage: str,
    stage_narrate: str,
    actor_appearance_mapping: Dict[str, str],
    stage_graph: List[str],
) -> str:

    # 连接的场景
    if len(stage_graph) == 0:
        stage_graph.append(f"无")

    # 场景内角色的外观组织信息
    if actor_name in actor_appearance_mapping:
        actor_appearance_mapping.pop(actor_name, None)

    actor_appearance_mapping_prompt: List[str] = []
    for target_name, appearance in actor_appearance_mapping.items():
        actor_appearance_mapping_prompt.append(
            f"""### {target_name}
角色外观:{appearance}
"""
        )

    if len(actor_appearance_mapping_prompt) == 0:
        actor_appearance_mapping_prompt.append("无任何角色。")

    return f"""# 提示: {actor_name} 将要离开场景:{current_stage}。
## {actor_name} 对于场景——{current_stage}，最后的印象(场景描述):
{stage_narrate}
### (如从本场景离开)可以去往的场景
{"\n".join(stage_graph)}

## {actor_name} 对于其他角色最后的印象:
{"\n".join(actor_appearance_mapping_prompt)}"""


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
class StageTransitionHandler:

    def __init__(
        self, context: RPGGameContext, entity: Entity, target_stage_name: str
    ) -> None:

        self._context: RPGGameContext = context
        self._entity: Entity = entity
        self._target_stage_name: str = target_stage_name

        self._current_stage_name: str = entity.get(ActorComponent).current_stage
        self._current_stage_entity: Optional[Entity] = self._context.get_stage_entity(
            self._current_stage_name
        )

    ###############################################################################################################################################
    @property
    def current_stage_entity(self) -> Entity:
        assert self._current_stage_entity is not None
        return self._current_stage_entity

    ###############################################################################################################################################
    @property
    def target_stage_entity(self) -> Optional[Entity]:
        stage_name = self._resolve_target_stage_name(self._entity)
        return self._context.get_stage_entity(stage_name)

    ###############################################################################################################################################
    @property
    def target_stage_name(self) -> str:
        return self._resolve_target_stage_name(self._entity)

    ###############################################################################################################################################
    def _resolve_target_stage_name(self, actor_entity: Entity) -> str:
        assert actor_entity.has(ActorComponent)
        assert actor_entity.has(GoToAction)
        go_to_action = actor_entity.get(GoToAction)
        if len(go_to_action.values) == 0:
            return ""
        return str(go_to_action.values[0])


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################


@final
class GoToActionSystem(ReactiveProcessor):

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
            self._process_go_to_action(entity)

    ###############################################################################################################################################
    def _process_go_to_action(self, entity: Entity) -> None:

        go_to_action = entity.get(GoToAction)
        if len(go_to_action.values) == 0:
            logger.error(f"GoToActionSystem: {entity} has no target stage")
            return

        helper = StageTransitionHandler(self._context, entity, go_to_action.values[0])
        if (
            helper.target_stage_entity is None
            or helper.current_stage_entity is None
            or helper.target_stage_entity == helper.current_stage_entity
        ):
            logger.error(f"GoToActionSystem: {entity} invalid helper")
            return

        # 离开前的处理
        self._prepare_for_exit_stage(helper)
        # 正式离开
        self._exit_current_stage(helper)
        # 进入新的场景
        self._enter_target_stage(helper)
        # 进入新场景之后的处理
        self._handle_post_stage_entry(helper)

    ###############################################################################################################################################
    def _enter_target_stage(self, helper: StageTransitionHandler) -> None:

        actor_comp = helper._entity.get(ActorComponent)

        # 真正的进入场景
        helper._entity.replace(
            ActorComponent, actor_comp.name, helper.target_stage_name
        )

        # 标记一下
        helper._entity.replace(
            EnterStageFlagComponent, actor_comp.name, helper.target_stage_name
        )

        # 更新场景标记
        self._context.update_stage_tag_component(
            helper._entity, helper._current_stage_name, helper.target_stage_name
        )

        # 通知新场景的人，我进入了场景，#自己不用通知，下面会单独通知。
        assert helper.target_stage_entity is not None
        self._context.broadcast_event(
            helper.target_stage_entity,
            AgentEvent(
                message=_generate_stage_entry_prompt(
                    actor_comp.name, helper.target_stage_name
                )
            ),
            set({helper._entity}),
        )

        # 通知自己，我切换了场景
        self._context.notify_event(
            set({helper._entity}),
            AgentEvent(
                message=_generate_stage_change_prompt(
                    actor_comp.name,
                    helper.target_stage_name,
                    helper._current_stage_name,
                )
            ),
        )

    ###############################################################################################################################################
    def _handle_post_stage_entry(self, helper: StageTransitionHandler) -> None:

        stage_entity = self._context.safe_get_stage_entity(helper._entity)
        assert stage_entity is not None
        assert stage_entity == helper.target_stage_entity

        # 外观拿出来。组织信息
        my_name = self._context.safe_get_entity_name(helper._entity)
        actor_names = self._context.retrieve_actor_names_on_stage(stage_entity)
        actor_names.discard(my_name)
        if len(actor_names) == 0:
            actor_names.add("无任何角色。")

        # 组织提示词
        prompt = f"""# 提示: 场景: {helper.target_stage_name} 的信息
## 场景内角色
{"\n".join(actor_names)}"""

        # 通知
        self._context.notify_event(
            set({helper._entity}),
            PostStageEnterEvent(message=prompt),
        )

    ###############################################################################################################################################
    def _prepare_for_exit_stage(self, helper: StageTransitionHandler) -> None:
        assert helper.current_stage_entity.has(StageGraphComponent)
        assert helper.current_stage_entity.has(StageEnvironmentComponent)

        # 外观拿出来。
        my_name = self._context.safe_get_entity_name(helper._entity)
        actor_appearance_on_stage = self._context.retrieve_stage_actor_appearance(
            helper.current_stage_entity
        )
        actor_appearance_on_stage.pop(my_name)

        # 最后通知
        self._context.notify_event(
            set({helper._entity}),
            PreStageExitEvent(
                message=_generate_last_impression_prompt(
                    actor_name=my_name,
                    current_stage=helper._current_stage_name,
                    stage_narrate=helper.current_stage_entity.get(
                        StageEnvironmentComponent
                    ).narrate,
                    actor_appearance_mapping=actor_appearance_on_stage,
                    stage_graph=copy.deepcopy(
                        helper.current_stage_entity.get(StageGraphComponent).stage_graph
                    ),
                )
            ),
        )

    ###############################################################################################################################################
    def _exit_current_stage(self, helper: StageTransitionHandler) -> None:

        # 离开场景的事件需要通知相关的人
        actor_comp = helper._entity.get(ActorComponent)
        self._context.broadcast_event(
            helper.current_stage_entity,
            AgentEvent(
                message=_generate_exit_stage_prompt(
                    actor_comp.name, helper._current_stage_name
                )
            ),
            set({helper._entity}),
        )

        # 离开场景 设置成空
        helper._entity.replace(ActorComponent, actor_comp.name, "")

        # 更新场景标记
        self._context.update_stage_tag_component(
            helper._entity, helper._current_stage_name, ""
        )


###############################################################################################################################################
