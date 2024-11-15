from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from my_components.action_components import GoToAction, DeadAction
from my_components.components import (
    ActorComponent,
    EnterStageFlagComponent,
    StageComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import final, override, Optional
import gameplay_systems.prompt_utils as prompt_utils
from rpg_game.rpg_game import RPGGame
from extended_systems.archive_file import StageArchiveFile
from my_models.event_models import AgentEvent, PreStageExitEvent
from loguru import logger


################################################################################################################################################
def _generate_exit_stage_prompt(actor_name: str, current_stage_name: str) -> str:
    return f"# 发生事件: {actor_name} 离开了 {current_stage_name} 场景。"


################################################################################################################################################
def _generate_stage_entry_prompt(actor_name: str, target_stage_name: str) -> str:
    return f"# 发生事件: {actor_name} 进入了场景 {target_stage_name}。"


################################################################################################################################################
def _generate_stage_change_prompt(
    actor_name: str, target_stage_name: str, previous_stage_name: str
) -> str:
    return f"# 发生事件: {actor_name} 离开了 {previous_stage_name} 场景, 然后进入了 {target_stage_name} 场景。"


################################################################################################################################################
def _generate_last_impression_of_stage_prompt(
    actor_name: str, stage_name: str, stage_narrate: str
) -> str:
    return f"""# 提示: {actor_name} 将要离开 {stage_name} 场景。
## {actor_name} 对于 {stage_name} 最后的印象(场景描述):
{stage_narrate}"""


################################################################################################################################################
def _generate_last_impression_of_actor_prompt(
    actor_name: str, target_name: str, appearance: str
) -> str:
    return f"""# 提示: {actor_name} 将要离开 {target_name}。
## {actor_name} 对于 {target_name} 最后的印象(外观描述):
{appearance}"""


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
class StageTransitionHandler:

    def __init__(
        self, context: RPGEntitasContext, entity: Entity, target_stage_name: str
    ) -> None:

        self._context: RPGEntitasContext = context
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

        if prompt_utils.is_unknown_stage_name(go_to_action.values[0]):
            guid = prompt_utils.extract_guid_from_unknown_stage_name(
                go_to_action.values[0]
            )
            stage_entity = self._context.get_entity_by_guid(guid)
            if stage_entity is not None and stage_entity.has(StageComponent):
                return self._context.safe_get_entity_name(stage_entity)

        return str(go_to_action.values[0])


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################


@final
class GoToActionSystem(ReactiveProcessor):

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
        # 离开
        self._exit_current_stage(helper)
        # 进入新的场景
        self._enter_target_stage(helper)

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
        self._context.broadcast_event_in_stage(
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
    def _prepare_for_exit_stage(self, helper: StageTransitionHandler) -> None:

        my_name = self._context.safe_get_entity_name(helper._entity)

        stage_archive = self._context._file_system.get_file(
            StageArchiveFile, my_name, helper._current_stage_name
        )

        if stage_archive is not None and stage_archive.stage_narrate != "":
            self._context.notify_event(
                set({helper._entity}),
                PreStageExitEvent(
                    message=_generate_last_impression_of_stage_prompt(
                        my_name, helper._current_stage_name, stage_archive.stage_narrate
                    )
                ),
            )

        actor_appearance_in_stage = self._context.gather_actor_appearance_in_stage(
            helper.current_stage_entity
        )
        actor_appearance_in_stage.pop(my_name)
        for actor_name, appearance in actor_appearance_in_stage.items():
            self._context.notify_event(
                set({helper._entity}),
                PreStageExitEvent(
                    message=_generate_last_impression_of_actor_prompt(
                        my_name, actor_name, appearance
                    )
                ),
            )

    ###############################################################################################################################################
    def _exit_current_stage(self, helper: StageTransitionHandler) -> None:

        # 离开场景的事件需要通知相关的人
        actor_comp = helper._entity.get(ActorComponent)
        self._context.broadcast_event_in_stage(
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
