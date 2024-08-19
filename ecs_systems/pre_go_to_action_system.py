from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from ecs_systems.action_components import (
    GoToAction,
    StageNarrateAction,
    TagAction,
    DeadAction,
)
from ecs_systems.components import (
    StageComponent,
    ActorComponent,
    StageExitCondStatusComponent,
    StageExitCondCheckActorStatusComponent,
    StageExitCondCheckActorPropsComponent,
    AppearanceComponent,
    StageEntryCondStatusComponent,
    StageEntryCondCheckActorStatusComponent,
    StageEntryCondCheckActorPropsComponent,
)
from my_agent.agent_action import AgentAction
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from ecs_systems.stage_director_component import StageDirectorComponent
from ecs_systems.stage_director_event import IStageDirectorEvent
import ecs_systems.cn_builtin_prompt as builtin_prompt
from ecs_systems.cn_constant_prompt import _CNConstantPrompt_
from typing import Optional, cast, override, List
from ecs_systems.check_status_action_system import CheckStatusActionHelper
from my_agent.agent_plan import AgentPlan
from my_agent.lang_serve_agent_request_task import LangServeAgentRequestTask


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class ActorGoToFailedBecauseStageInvalid(IStageDirectorEvent):

    def __init__(self, actor_name: str, stage_name: str) -> None:
        self._actor_name: str = actor_name
        self._stage_name: str = stage_name

    def to_actor(self, actor_name: str, extended_context: RPGEntitasContext) -> str:
        if actor_name != self._actor_name:
            # 跟你无关不用关注，原因类的东西，是失败后矫正用，所以只有自己知道即可
            return ""
        return builtin_prompt.go_to_stage_failed_because_stage_is_invalid_prompt(
            self._actor_name, self._stage_name
        )

    def to_stage(self, stage_name: str, extended_context: RPGEntitasContext) -> str:
        return ""


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class ActorGoToFailedBecauseAlreadyInStage(IStageDirectorEvent):

    def __init__(self, actor_name: str, stage_name: str) -> None:
        self._actor_name: str = actor_name
        self._stage_name: str = stage_name

    def to_actor(self, actor_name: str, extended_context: RPGEntitasContext) -> str:
        if actor_name != self._actor_name:
            # 跟你无关不用关注，原因类的东西，是失败后矫正用，所以只有自己知道即可
            return ""
        return builtin_prompt.go_to_stage_failed_because_already_in_stage_prompt(
            self._actor_name, self._stage_name
        )

    def to_stage(self, stage_name: str, extended_context: RPGEntitasContext) -> str:
        return ""


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class ActorExitStageFailedBecauseStageRefuse(IStageDirectorEvent):
    def __init__(self, actor_name: str, stage_name: str, tips: str) -> None:
        self._actor_name: str = actor_name
        self._stage_name: str = stage_name
        self._tips: str = tips

    def to_actor(self, actor_name: str, extended_context: RPGEntitasContext) -> str:
        if actor_name != self._actor_name:
            return ""
        return builtin_prompt.exit_stage_failed_beacuse_stage_refuse_prompt(
            self._actor_name, self._stage_name, self._tips
        )

    def to_stage(self, stage_name: str, extended_context: RPGEntitasContext) -> str:
        return ""


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class ActorEnterStageFailedBecauseStageRefuse(IStageDirectorEvent):
    def __init__(self, actor_name: str, stage_name: str, tips: str) -> None:
        self._actor_name: str = actor_name
        self._stage_name: str = stage_name
        self._tips: str = tips

    def to_actor(self, actor_name: str, extended_context: RPGEntitasContext) -> str:
        if actor_name != self._actor_name:
            return ""
        return builtin_prompt.enter_stage_failed_beacuse_stage_refuse_prompt(
            self._actor_name, self._stage_name, self._tips
        )

    def to_stage(self, stage_name: str, extended_context: RPGEntitasContext) -> str:
        return ""


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class StageConditionsHelper:

    _tips: str
    _stage_name: str
    _stage_cond_status_prompt: str
    _cond_check_actor_status_prompt: str
    _cond_check_actor_props_prompt: str

    def __init__(self, tig: str) -> None:
        self._tips = tig
        self.clear()

    ####################################################################################################################################
    def clear(self) -> None:
        self._stage_name = ""
        self._stage_cond_status_prompt = str(_CNConstantPrompt_.NONE_PROMPT)
        self._cond_check_actor_status_prompt = str(_CNConstantPrompt_.NONE_PROMPT)
        self._cond_check_actor_props_prompt = str(_CNConstantPrompt_.NONE_PROMPT)

    ####################################################################################################################################
    def prepare_exit_cond(
        self, stage_entity: Entity, context: RPGEntitasContext
    ) -> None:
        self.clear()
        self._stage_name = context.safe_get_entity_name(stage_entity)
        # 准备好数据
        if stage_entity.has(StageExitCondStatusComponent):
            self._stage_cond_status_prompt = cast(
                StageExitCondStatusComponent,
                stage_entity.get(StageExitCondStatusComponent),
            ).condition
        # 准备好数据
        if stage_entity.has(StageExitCondCheckActorStatusComponent):
            self._cond_check_actor_status_prompt = cast(
                StageExitCondCheckActorStatusComponent,
                stage_entity.get(StageExitCondCheckActorStatusComponent),
            ).condition
        # 准备好数据
        if stage_entity.has(StageExitCondCheckActorPropsComponent):
            self._cond_check_actor_props_prompt = cast(
                StageExitCondCheckActorPropsComponent,
                stage_entity.get(StageExitCondCheckActorPropsComponent),
            ).condition

    ####################################################################################################################################
    def prepare_entry_cond(
        self, stage_entity: Entity, context: RPGEntitasContext
    ) -> None:
        self.clear()
        self._stage_name = context.safe_get_entity_name(stage_entity)
        # 准备好数据
        if stage_entity.has(StageEntryCondStatusComponent):
            self._stage_cond_status_prompt = cast(
                StageEntryCondStatusComponent,
                stage_entity.get(StageEntryCondStatusComponent),
            ).condition
        # 准备好数据
        if stage_entity.has(StageEntryCondCheckActorStatusComponent):
            self._cond_check_actor_status_prompt = cast(
                StageEntryCondCheckActorStatusComponent,
                stage_entity.get(StageEntryCondCheckActorStatusComponent),
            ).condition
        # 准备好数据
        if stage_entity.has(StageEntryCondCheckActorPropsComponent):
            self._cond_check_actor_props_prompt = cast(
                StageEntryCondCheckActorPropsComponent,
                stage_entity.get(StageEntryCondCheckActorPropsComponent),
            ).condition


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################


class HandleStageConditionsResponseHelper:
    def __init__(self, plan: AgentPlan) -> None:
        self._plan: AgentPlan = plan
        self._tips_action: Optional[AgentAction] = None
        self._result_action: Optional[AgentAction] = None

    ###############################################################################################################################################
    @property
    def result(self) -> bool:
        if self._result_action is None:
            return False
        assert self._result_action._action_name == TagAction.__name__
        return self._result_action.bool_value(0)

    ###############################################################################################################################################
    @property
    def tips(self) -> str:
        if self._tips_action is None:
            return str(_CNConstantPrompt_.NONE_PROMPT)

        assert self._tips_action._action_name == StageNarrateAction.__name__
        if len(self._tips_action._values) == 0:
            return str(_CNConstantPrompt_.NONE_PROMPT)
        return self._tips_action.join_values()

    ###############################################################################################################################################
    def parse(self) -> bool:

        if self._plan is None:
            return False

        self._tips_action = self._plan.get_action_by_key(StageNarrateAction.__name__)
        self._result_action = self._plan.get_action_by_key(TagAction.__name__)
        if self._tips_action is None or self._result_action is None:
            logger.error(
                f"HandleStageConditionsResponseHelper 大模型推理错误，没有达到预期的格式 = {self._plan}"
            )
            return False

        return True


###############################################################################################################################################


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
class PreBeforeGoToActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context

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

            # f"未知场景({guid})"
            self.handle_guid_stage_name(entity)

            # 检查目标场景是否有效，可能是无效的，例如不存在，或者已经在目标场景了
            if not self.check_target_stage_is_valid(entity):
                self.on_failed(entity)
                continue

            # 检查离开当前场景的条件是否满足，需要LLM推理
            exit_result = self.handle_exit_stage_with_conditions(entity)
            if not exit_result:
                self.on_failed(entity)
                continue

            # 检查进入目标场景的条件是否满足，需要LLM推理
            enter_result = self.handle_enter_stage_with_conditions(entity)
            if not enter_result:
                self.on_failed(entity)
                continue

            # 通过了，可以去下一个场景了
            logger.debug(
                f"{self._context.safe_get_entity_name(entity)} 通过了离开和进入条件，可以去下一个场景了"
            )

    ###############################################################################################################################################
    def check_target_stage_is_valid(self, actor_entity: Entity) -> bool:

        safe_actor_name = self._context.safe_get_entity_name(actor_entity)
        current_stage_entity = self._context.safe_get_stage_entity(actor_entity)
        if current_stage_entity is None:
            logger.error(f"{safe_actor_name}没有当前场景，这是个错误")
            return False

        target_stage_name = self.get_target_stage_name(actor_entity)
        target_stage_entity = self.get_target_stage_entity(actor_entity)
        if target_stage_entity is None:
            # 无效的去往目标!
            StageDirectorComponent.add_event_to_stage_director(
                self._context,
                current_stage_entity,
                ActorGoToFailedBecauseStageInvalid(safe_actor_name, target_stage_name),
            )
            return False

        if current_stage_entity == target_stage_entity:
            # 已经在这个场景里了，不要重复去了
            StageDirectorComponent.add_event_to_stage_director(
                self._context,
                current_stage_entity,
                ActorGoToFailedBecauseAlreadyInStage(
                    safe_actor_name, target_stage_name
                ),
            )
            return False

        return True

    ###############################################################################################################################################
    def need_check_exit_cond(self, stage_entity: Entity) -> bool:
        return (
            stage_entity.has(StageExitCondStatusComponent)
            or stage_entity.has(StageExitCondCheckActorStatusComponent)
            or stage_entity.has(StageExitCondCheckActorPropsComponent)
        )

    ###############################################################################################################################################
    def need_check_entry_cond(self, stage_entity: Entity) -> bool:
        return (
            stage_entity.has(StageEntryCondStatusComponent)
            or stage_entity.has(StageEntryCondCheckActorStatusComponent)
            or stage_entity.has(StageEntryCondCheckActorPropsComponent)
        )

    ###############################################################################################################################################
    def handle_exit_stage_with_conditions(self, actor_entity: Entity) -> bool:
        #
        current_stage_entity = self._context.safe_get_stage_entity(actor_entity)
        assert current_stage_entity is not None
        if not self.need_check_exit_cond(current_stage_entity):
            return True
        #
        actor_name = self._context.safe_get_entity_name(actor_entity)
        current_stage_name = self._context.safe_get_entity_name(current_stage_entity)
        #
        stage_exit_cond_helper = StageConditionsHelper(
            f"离开{current_stage_name}的检查所有条件"
        )
        stage_exit_cond_helper.prepare_exit_cond(current_stage_entity, self._context)
        # 准备好数据

        final_prompt = builtin_prompt.stage_exit_conditions_check_prompt(
            actor_name,
            current_stage_name,
            stage_exit_cond_helper._stage_cond_status_prompt,
            stage_exit_cond_helper._cond_check_actor_status_prompt,
            self.get_actor_status_prompt(actor_entity),
            stage_exit_cond_helper._cond_check_actor_props_prompt,
            self.get_actor_props_prompt(actor_entity),
        )

        ## 让大模型去推断是否可以离开，分别检查stage自身，角色状态（例如长相），角色道具（拥有哪些道具与文件）
        agent = self._context._langserve_agent_system.get_agent(current_stage_name)
        if agent is None:
            return False

        task = LangServeAgentRequestTask.create(agent, final_prompt)
        if task is None:
            return False

        response = task.request()
        if response is None:
            return False

        plan = AgentPlan(current_stage_name, response)
        handle_response_helper = HandleStageConditionsResponseHelper(plan)
        if not handle_response_helper.parse():
            return False

        #
        if not handle_response_helper.result:
            # 通知事件
            StageDirectorComponent.add_event_to_stage_director(
                self._context,
                current_stage_entity,
                ActorExitStageFailedBecauseStageRefuse(
                    actor_name, current_stage_name, handle_response_helper.tips
                ),
            )
            return False

        logger.debug(f"允许通过！说明如下: {handle_response_helper.tips}")
        ## 可以删除，允许通过！这个上下文就拿掉，不需要了。
        self._context._langserve_agent_system.remove_last_conversation_between_human_and_ai(
            current_stage_name
        )
        return True

    ###############################################################################################################################################
    def handle_enter_stage_with_conditions(self, actor_entity: Entity) -> bool:

        target_stage_entity = self.get_target_stage_entity(actor_entity)
        assert target_stage_entity is not None
        if target_stage_entity is None:
            return False

        ##
        if not self.need_check_entry_cond(target_stage_entity):
            return True

        ##
        actor_name = self._context.safe_get_entity_name(actor_entity)
        target_stage_name = self._context.safe_get_entity_name(target_stage_entity)
        #
        stage_exit_cond_helper = StageConditionsHelper(
            f"进入{target_stage_name}的检查所有条件"
        )
        stage_exit_cond_helper.prepare_entry_cond(target_stage_entity, self._context)

        # 最终提示词
        final_prompt = builtin_prompt.stage_entry_conditions_check_prompt(
            actor_name,
            target_stage_name,
            stage_exit_cond_helper._stage_cond_status_prompt,
            stage_exit_cond_helper._cond_check_actor_status_prompt,
            self.get_actor_status_prompt(actor_entity),
            stage_exit_cond_helper._cond_check_actor_props_prompt,
            self.get_actor_props_prompt(actor_entity),
        )

        ## 让大模型去推断是否可以离开，分别检查stage自身，角色状态（例如长相），角色道具（拥有哪些道具与文件）
        agent = self._context._langserve_agent_system.get_agent(target_stage_name)
        if agent is None:
            return False

        task = LangServeAgentRequestTask.create(agent, final_prompt)
        if task is None:
            return False

        response = task.request()
        if response is None:
            return False

        plan = AgentPlan(target_stage_name, response)
        handle_response_helper = HandleStageConditionsResponseHelper(plan)
        if not handle_response_helper.parse():
            return False

        if not handle_response_helper.result:
            # 通知事件, 因为没动，得是当前场景需要通知
            current_stage_entity = self._context.safe_get_stage_entity(actor_entity)
            assert current_stage_entity is not None
            StageDirectorComponent.add_event_to_stage_director(
                self._context,
                current_stage_entity,
                ActorEnterStageFailedBecauseStageRefuse(
                    actor_name, target_stage_name, handle_response_helper.tips
                ),
            )
            return False

        logger.debug(f"允许通过！说明如下: {handle_response_helper.tips}")
        ## 可以删除，允许通过！这个上下文就拿掉，不需要了。
        self._context._langserve_agent_system.remove_last_conversation_between_human_and_ai(
            target_stage_name
        )
        return True

    ###############################################################################################################################################
    def get_target_stage_entity(self, actor_entity: Entity) -> Optional[Entity]:
        return self._context.get_stage_entity(self.get_target_stage_name(actor_entity))

    ###############################################################################################################################################
    def get_target_stage_name(self, actor_entity: Entity) -> str:
        assert actor_entity.has(ActorComponent)
        assert actor_entity.has(GoToAction)

        go_to_comp: GoToAction = actor_entity.get(GoToAction)
        action: AgentAction = go_to_comp.action
        return action.value(0)

    ###############################################################################################################################################
    # todo 目前就把角色外观信息当作状态信息，后续可以加入更多的状态信息
    def get_actor_status_prompt(self, actor_entity: Entity) -> str:

        assert actor_entity.has(ActorComponent)
        assert actor_entity.has(AppearanceComponent)

        safe_name = self._context.safe_get_entity_name(actor_entity)
        appearance_comp = actor_entity.get(AppearanceComponent)
        return builtin_prompt.actor_status_when_stage_change_prompt(
            safe_name, cast(str, appearance_comp.appearance)
        )

    ###############################################################################################################################################
    def get_actor_props_prompt(self, actor_entity: Entity) -> List[str]:
        helper = CheckStatusActionHelper(self._context)
        helper.check_status(actor_entity)
        target_type_prop_files = (
            helper._prop_files_as_weapon_clothes_non_consumable_item
            + helper._prop_files_as_special_components
        )
        return [
            builtin_prompt.prop_prompt(prop, True, True)
            for prop in target_type_prop_files
        ]

    ###############################################################################################################################################
    def on_failed(self, actor_entity: Entity) -> None:
        if actor_entity.has(GoToAction):
            actor_entity.remove(GoToAction)

    ###############################################################################################################################################
    def handle_guid_stage_name(self, actor_entity: Entity) -> None:
        assert actor_entity.has(ActorComponent)
        assert actor_entity.has(GoToAction)

        go_to_comp: GoToAction = actor_entity.get(GoToAction)
        action: AgentAction = go_to_comp.action
        check_unknown_guid_stage_name = action.value(0)
        if not builtin_prompt.is_unknown_guid_stage_name_prompt(
            check_unknown_guid_stage_name
        ):
            return

        logger.debug(f"current_name = {check_unknown_guid_stage_name}")
        guid = builtin_prompt.extract_from_unknown_guid_stage_name_prompt(
            check_unknown_guid_stage_name
        )
        stage_entity = self._context.get_entity_by_guid(guid)
        if stage_entity is None:
            logger.error(f"未知的场景GUID({guid})")
            return

        if not stage_entity.has(StageComponent):
            logger.error(f"({guid}) 对应的不是一个场景")
            return

        action._values[0] = self._context.safe_get_entity_name(stage_entity)


###############################################################################################################################################
