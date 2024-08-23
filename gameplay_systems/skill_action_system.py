from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from gameplay_systems.action_components import (
    BehaviorAction,
    TargetAction,
    SkillAction,
    PropAction,
    TagAction,
    BroadcastAction,
)
from gameplay_systems.components import AppearanceComponent
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import override, Any, List, cast, Optional, Set
from loguru import logger
from file_system.files_def import PropFile
import gameplay_systems.cn_builtin_prompt as builtin_prompt
from my_agent.lang_serve_agent_request_task import LangServeAgentRequestTask
from my_agent.agent_plan import AgentPlan
from gameplay_systems.cn_constant_prompt import _CNConstantPrompt_ as ConstantPrompt
import gameplay_systems.planning_helper
from gameplay_systems.action_components import (
    STAGE_AVAILABLE_ACTIONS_REGISTER,
    ACTOR_AVAILABLE_ACTIONS_REGISTER,
)
import gameplay_systems.cn_builtin_prompt as builtin_prompt


class WorldSkillSystemResponsePlan(AgentPlan):

    def __init__(self, name: str, input_str: str) -> None:
        super().__init__(name, input_str)

    @property
    def result_description(self) -> str:
        tip_action = self.get_by_key(TagAction.__name__)
        if tip_action is None or len(tip_action.values) == 0:
            return ConstantPrompt.FAILURE
        return tip_action.values[0]

    @property
    def reasoning_sentence(self) -> str:
        broadcast_action = self.get_by_key(BroadcastAction.__name__)
        if broadcast_action is None or len(broadcast_action.values) == 0:
            return ""
        return " ".join(broadcast_action.values)


class SkillActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, world_system_name: str) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._world_system_name: str = world_system_name

    ######################################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(SkillAction): GroupEvent.ADDED}

    ######################################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(SkillAction)
            and entity.has(TargetAction)
            and entity.has(BehaviorAction)
        )

    ######################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.handle(entity)

    ######################################################################################################################################################
    def handle(self, entity: Entity) -> None:

        assert entity.has(SkillAction) and entity.has(TargetAction)

        # 没有世界系统就是错误
        world_entity = self._context.get_world_entity(self._world_system_name)
        if world_entity is None:
            logger.error(f"{self._world_system_name}, world_entity is None.")
            return

        # 准备数据
        appearance = self.get_appearance(entity)
        skill_files = self.get_skill_files(entity)
        prop_files = self.get_prop_files(entity)

        world_response_plan = self.request_world_skill_system_reasoning(
            entity, world_entity, appearance, skill_files, prop_files
        )

        if world_response_plan is None:

            self._context.add_agent_context_message(
                set({entity}),
                builtin_prompt.make_world_skill_system_off_line_error_prompt(
                    self._context.safe_get_entity_name(entity),
                    self.get_behavior_sentence(entity),
                ),
            )
            # 全局技能系统是不是掉线了？
            return

        # 单独处理失败和大失败
        if (
            world_response_plan.result_description == ConstantPrompt.BIG_FAILURE
            or world_response_plan.result_description == ConstantPrompt.FAILURE
        ):

            self._context.add_agent_context_message(
                set({entity}),
                builtin_prompt.make_world_skill_system_reasoning_result_is_failure_prompt(
                    self._context.safe_get_entity_name(entity),
                    world_response_plan.result_description,
                    self.get_behavior_sentence(entity),
                    world_response_plan.reasoning_sentence,
                ),
            )

            # 不要再往下走了。全局技能系统推理出失败 就提示下一下截断掉
            return

        # 释放技能
        for target in self.get_targets(entity):

            skill_reponse_plan = self.request_release_skill_to_target_feedback(
                entity, target, world_response_plan
            )

            if skill_reponse_plan is None:

                self._context.add_agent_context_message(
                    set({entity}),
                    builtin_prompt.make_skill_skill_target_agent_off_line_error_prompt(
                        self._context.safe_get_entity_name(entity),
                        self._context.safe_get_entity_name(target),
                        world_response_plan.reasoning_sentence,
                    ),
                )

                # 目标是不是掉线了？
                continue

            self.add_actions(target, skill_reponse_plan)

    ######################################################################################################################################################

    def get_behavior_sentence(self, entity: Entity) -> str:
        behavior_action = entity.get(BehaviorAction)
        if behavior_action is None or len(behavior_action.values) == 0:
            return ""
        return cast(str, behavior_action.values[0])

    ######################################################################################################################################################
    def get_targets(self, entity: Entity) -> Set[Entity]:
        assert entity.has(TargetAction)
        targets = set()
        for target_name in entity.get(TargetAction).values:
            target = self._context.get_entity_by_name(target_name)
            if target is not None:
                targets.add(target)
        return targets

    ######################################################################################################################################################
    def request_release_skill_to_target_feedback(
        self,
        entity: Entity,
        target: Entity,
        world_response_plan: WorldSkillSystemResponsePlan,
    ) -> Optional[AgentPlan]:

        agent_name = self._context.safe_get_entity_name(target)
        agent = self._context._langserve_agent_system.get_agent(agent_name)
        if agent is None:
            return None

        prompt = builtin_prompt.make_reasoning_skill_target_feedback_prompt(
            self._context.safe_get_entity_name(entity),
            agent_name,
            world_response_plan.reasoning_sentence,
            world_response_plan.result_description,
        )

        task = LangServeAgentRequestTask.create(
            agent,
            builtin_prompt.replace_mentions_of_your_name_with_you_prompt(
                prompt, agent_name
            ),
        )

        if task is None:
            return None

        response = task.request()
        if response is None:
            logger.debug(f"{agent._name}, response is None.")
            return None

        return AgentPlan(agent._name, response)

    ######################################################################################################################################################
    def add_actions(self, target: Entity, agent_plan: AgentPlan) -> None:

        all_register: List[Any] = (
            STAGE_AVAILABLE_ACTIONS_REGISTER + ACTOR_AVAILABLE_ACTIONS_REGISTER
        )

        if not gameplay_systems.planning_helper.check_plan(
            target, agent_plan, all_register
        ):
            logger.warning(f"ActorPlanningSystem: check_plan failed, {agent_plan}")
            self._context._langserve_agent_system.remove_last_conversation_between_human_and_ai(
                agent_plan._name
            )
            return

        for action in agent_plan._actions:
            gameplay_systems.planning_helper.add_action_component(
                target, action, all_register
            )

    ######################################################################################################################################################
    def request_world_skill_system_reasoning(
        self,
        entity: Entity,
        world_entity: Entity,
        appearance: str,
        skill_files: List[PropFile],
        prop_files: List[PropFile],
    ) -> Optional[WorldSkillSystemResponsePlan]:

        # 生成提示
        prompt = builtin_prompt.make_world_reasoning_release_skill_prompt(
            self._context.safe_get_entity_name(entity),
            appearance,
            skill_files,
            prop_files,
        )

        agent = self._context._langserve_agent_system.get_agent(
            self._context.safe_get_entity_name(world_entity)
        )
        if agent is None:
            return None

        task = LangServeAgentRequestTask.create_without_context(agent, prompt)
        if task is None:
            return None

        response = task.request()
        if response is None:
            return None

        return WorldSkillSystemResponsePlan(agent._name, response)

    ######################################################################################################################################################
    def get_skill_files(self, entity: Entity) -> List[PropFile]:
        assert entity.has(SkillAction) and entity.has(TargetAction)

        ret: List[PropFile] = []

        safe_name = self._context.safe_get_entity_name(entity)
        skill_action = entity.get(SkillAction)
        for skill_name in skill_action.values:

            skill_file = self._context._file_system.get_file(
                PropFile, safe_name, skill_name
            )
            if skill_file is None or not skill_file.is_skill:
                continue

            ret.append(skill_file)

        return ret

    ######################################################################################################################################################
    def get_appearance(self, entity: Entity) -> str:
        assert entity.has(AppearanceComponent)
        if not entity.has(AppearanceComponent):
            return ""
        return str(entity.get(AppearanceComponent).appearance)

    ######################################################################################################################################################
    def get_prop_files(self, entity: Entity) -> List[PropFile]:
        if not entity.has(PropAction):
            return []

        safe_name = self._context.safe_get_entity_name(entity)
        prop_action = entity.get(PropAction)
        ret: List[PropFile] = []
        for prop_name in prop_action.values:
            prop_file = self._context._file_system.get_file(
                PropFile, safe_name, prop_name
            )
            if prop_file is None:
                continue
            ret.append(prop_file)

        return ret

    ######################################################################################################################################################
