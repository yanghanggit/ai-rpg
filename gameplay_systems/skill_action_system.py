from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from gameplay_systems.action_components import (
    BehaviorAction,
    SkillTargetAction,
    SkillAction,
    SkillUsePropAction,
    TagAction,
    BroadcastAction,
    DamageAction,
    MindVoiceAction,
)
from gameplay_systems.components import (
    BodyComponent,
    RPGAttributesComponent,
    ActorComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import override, List, cast, Optional, Set, Dict
from loguru import logger
from extended_systems.files_def import PropFile
import gameplay_systems.cn_builtin_prompt as builtin_prompt
from my_agent.agent_task import AgentTask, AgentTasksGather
from my_agent.agent_plan_and_action import AgentPlan
from gameplay_systems.cn_constant_prompt import _CNConstantPrompt_ as ConstantPrompt
import gameplay_systems.cn_builtin_prompt as builtin_prompt
import my_format_string.target_and_message_format_string
import my_format_string.attrs_format_string
from rpg_game.rpg_game import RPGGame
from my_data.model_def import AttributesIndex


class ActorCanUseSkillResponse(AgentPlan):

    def __init__(self, name: str, input_str: str) -> None:
        super().__init__(name, input_str)

    @property
    def tag(self) -> bool:
        tag_action = self.get_by_key(TagAction.__name__)
        if tag_action is None or len(tag_action.values) == 0:
            return False
        return (
            tag_action.values[0].lower() == "yes"
            or tag_action.values[0].lower() == "true"
        )

    @property
    def out_come(self) -> str:
        mind_voice_action = self.get_by_key(MindVoiceAction.__name__)
        if mind_voice_action is None or len(MindVoiceAction.values) == 0:
            return ConstantPrompt.FAILURE
        return " ".join(mind_voice_action.values)


######################################################################################################################################################


class WorldSkillSystemResponse(AgentPlan):

    OPTION_PARAM_NAME: str = "actor"

    def __init__(self, name: str, input_str: str) -> None:
        super().__init__(name, input_str)

    @property
    def tag(self) -> str:
        tip_action = self.get_by_key(TagAction.__name__)
        if tip_action is None or len(tip_action.values) == 0:
            return ConstantPrompt.FAILURE
        return tip_action.values[0]

    @property
    def out_come(self) -> str:
        broadcast_action = self.get_by_key(BroadcastAction.__name__)
        if broadcast_action is None or len(broadcast_action.values) == 0:
            return ""
        return " ".join(broadcast_action.values)


######################################################################################################################################################


class SkillActionSystem(ReactiveProcessor):

    def __init__(
        self, context: RPGEntitasContext, rpg_game: RPGGame, system_name: str
    ) -> None:
        super().__init__(context)

        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game
        self._system_name: str = system_name
        self._react_entities_copy: List[Entity] = []

    ######################################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(SkillAction): GroupEvent.ADDED}

    ######################################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(SkillAction)
            and entity.has(SkillTargetAction)
            and entity.has(BehaviorAction)
            and entity.has(ActorComponent)
        )

    ######################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        self._react_entities_copy = entities.copy()

    ######################################################################################################################################################
    async def a_execute2(self) -> None:

        if (
            self._context.get_world_entity(self._system_name) is not None
            and len(self._react_entities_copy) > 0
        ):
            await self.phase_execute(self._react_entities_copy, self._system_name)

        self._react_entities_copy.clear()

    ######################################################################################################################################################
    async def phase_execute(
        self, entities: List[Entity], world_skill_system_name: str
    ) -> None:

        # 结合自身条件进行判断
        await self.phase1_actor_self_reasoning(entities)

        # 世界全局做合理性判断
        world_skill_system_response = await self.phase2_world_skill_system_reasoning(
            entities, world_skill_system_name
        )
        for actor_name, response_plan in world_skill_system_response.items():
            actor_entity = self._context.get_actor_entity(actor_name)
            if actor_entity is None:
                continue

            # 最终释放给目标，并获取目标的反馈
            self.phase3_skill_to_targets(actor_entity, response_plan)

    ######################################################################################################################################################
    async def phase1_actor_self_reasoning(self, entities: List[Entity]) -> None:

        if len(entities) == 0:
            return

        # 第一个大阶段，角色自己检查是否可以使用技能
        create_tasks = self.create_tasks_actor_can_use_skill(entities)
        if len(create_tasks) == 0:
            return

        response = await AgentTasksGather(
            "第一个阶段，检查角色自身是否可以使用技能",
            [task for task in create_tasks.values()],
        ).gather()

        if len(response) == 0:
            logger.debug(f"phase1_response is None.")
            return

        self.handle_actor_can_use_skill(create_tasks, entities)

    ######################################################################################################################################################
    async def phase2_world_skill_system_reasoning(
        self,
        entities: List[Entity],
        world_skill_system_name: str,
    ) -> Dict[str, WorldSkillSystemResponse]:

        if len(entities) == 0:
            return {}

        # 第二个大阶段，全局技能系统检查技能组合是否合法
        create_tasks = self.create_tasks_world_skill_system_validate_skill_combo(
            entities, world_skill_system_name
        )
        if len(create_tasks) == 0:
            return {}

        response = await AgentTasksGather(
            "第二个阶段，检查技能组合是否合法", create_tasks
        ).gather()
        if len(response) == 0:
            logger.debug(f"phase2_response is None.")
            return {}

        return self.handle_world_skill_system_validate_skill_combo(
            create_tasks, entities
        )

    ######################################################################################################################################################
    def phase3_skill_to_targets(
        self, entity: Entity, world_skill_system_response: WorldSkillSystemResponse
    ) -> None:
        # 释放技能
        for target in self.extract_targets(entity):

            target_response = self.request_skill_to_target_feedback_reasoning(
                entity, target, world_skill_system_response
            )

            if target_response is None:
                self.add_target_agent_off_line_event(
                    entity, target, world_skill_system_response
                )
                continue

            # 加入伤害计算的逻辑
            self.calculate_and_add_action_to_target(entity, target)

            # 场景事件
            self.add_notify_others_of_skill_use_event(
                entity, target, world_skill_system_response
            )

    ######################################################################################################################################################
    def handle_actor_can_use_skill(
        self, tasks: Dict[str, AgentTask], entities: List[Entity]
    ) -> None:

        for agent_name, task in tasks.items():

            if task.response_content == "":
                continue

            actor_entity = self._context.get_actor_entity(agent_name)
            if actor_entity is None:
                continue

            response_plan = ActorCanUseSkillResponse(agent_name, task.response_content)
            if not response_plan.tag:
                entities.remove(actor_entity)
                continue

    ######################################################################################################################################################
    def handle_world_skill_system_validate_skill_combo(
        self, tasks: List[AgentTask], entities: List[Entity]
    ) -> Dict[str, WorldSkillSystemResponse]:

        ret: Dict[str, WorldSkillSystemResponse] = {}

        for task in tasks:

            actor_name = task._option_param.get(
                WorldSkillSystemResponse.OPTION_PARAM_NAME, ""
            )
            entity = self._context.get_actor_entity(actor_name)
            if entity is None:
                continue

            if task.response_content == "":
                self.add_world_skill_system_off_line_event(entity)
                continue

            response_plan = WorldSkillSystemResponse(
                task.agent_name, task.response_content
            )

            # 单独处理失败和大失败
            if response_plan.tag == ConstantPrompt.FAILURE:

                # 不往下进行了。
                entities.remove(entity)

                # 剧情通知
                self.add_world_skill_system_validate_skill_combo_fail_event(
                    entity, response_plan
                )

                continue

            ret[actor_name] = response_plan

        return ret

    ######################################################################################################################################################

    def extract_behavior_sentence(self, entity: Entity) -> str:
        behavior_action = entity.get(BehaviorAction)
        if behavior_action is None or len(behavior_action.values) == 0:
            return ""
        return cast(str, behavior_action.values[0])

    ######################################################################################################################################################
    def extract_targets(self, entity: Entity) -> Set[Entity]:
        assert entity.has(SkillTargetAction)
        targets = set()
        for target_name in entity.get(SkillTargetAction).values:
            target = self._context.get_entity_by_name(target_name)
            if target is not None:
                targets.add(target)
        return targets

    ######################################################################################################################################################
    def extract_skill_files(self, entity: Entity) -> List[PropFile]:
        assert entity.has(SkillAction) and entity.has(SkillTargetAction)

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
    def extract_body_info(self, entity: Entity) -> str:
        if not entity.has(BodyComponent):
            return ""
        return str(entity.get(BodyComponent).body)

    ######################################################################################################################################################
    def extract_prop_files(self, entity: Entity) -> List[PropFile]:
        if not entity.has(SkillUsePropAction):
            return []

        safe_name = self._context.safe_get_entity_name(entity)
        prop_action = entity.get(SkillUsePropAction)
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

    def add_notify_others_of_skill_use_event(
        self,
        from_entity: Entity,
        target_entity: Entity,
        world_skill_system_response: WorldSkillSystemResponse,
    ) -> None:

        current_stage_entity = self._context.safe_get_stage_entity(from_entity)
        if current_stage_entity is None:
            return

        self._context.notify_event_to_all_entities_in_stage(
            current_stage_entity,
            builtin_prompt.make_notify_others_of_skill_use_prompt(
                self._context.safe_get_entity_name(from_entity),
                self._context.safe_get_entity_name(target_entity),
                world_skill_system_response.out_come,
            ),
            set({from_entity, target_entity}),
        )

    ######################################################################################################################################################
    def calculate_and_add_action_to_target(
        self, entity: Entity, target: Entity
    ) -> None:

        # 拿到原始的
        need_calculate_skill_attrs: List[int] = self.extract_skill_attrs(entity)
        # 补充上发起者的攻击值
        self.calculate_values_of_attr_comp(entity, target, need_calculate_skill_attrs)
        # 补充上所有参与的道具的属性
        self.calculate_values_of_props(entity, target, need_calculate_skill_attrs)
        # 最终添加到目标的伤害行为
        self.add_damage_action(entity, target, need_calculate_skill_attrs)

    ######################################################################################################################################################
    def add_damage_action(
        self, entity: Entity, target: Entity, skill_attrs: List[int]
    ) -> None:
        if skill_attrs[AttributesIndex.DAMAGE.value] == 0:
            return

        if not target.has(DamageAction):
            # 保底先有一个。
            target.add(
                DamageAction,
                self._context.safe_get_entity_name(target),
                DamageAction.__name__,
                [],
            )

        cast(List[str], target.get(DamageAction).values).append(
            my_format_string.target_and_message_format_string.make_target_and_message(
                self._context.safe_get_entity_name(entity),
                my_format_string.attrs_format_string.from_int_attrs_to_string(
                    skill_attrs
                ),
            )
        )

    ######################################################################################################################################################

    def calculate_values_of_attr_comp(
        self, entity: Entity, target: Entity, out_put_skill_attrs: List[int]
    ) -> None:

        if not entity.has(RPGAttributesComponent):
            return

        rpg_attr_comp = entity.get(RPGAttributesComponent)
        out_put_skill_attrs[AttributesIndex.DAMAGE.value] += rpg_attr_comp.attack

    ######################################################################################################################################################
    def calculate_values_of_props(
        self, entity: Entity, target: Entity, out_put_skill_attrs: List[int]
    ) -> None:
        prop_files = self.extract_prop_files(entity)
        for prop_file in prop_files:
            for i in range(len(out_put_skill_attrs)):
                out_put_skill_attrs[i] += prop_file._prop_model.attributes[i]

    ######################################################################################################################################################
    def extract_skill_attrs(self, entity: Entity) -> List[int]:
        final_attr: List[int] = []
        for skill_file in self.extract_skill_files(entity):
            if len(final_attr) == 0:
                final_attr = skill_file._prop_model.attributes
            else:
                for i in range(len(final_attr)):
                    final_attr[i] += skill_file._prop_model.attributes[i]
        return final_attr

    ######################################################################################################################################################
    def add_world_skill_system_off_line_event(self, entity: Entity) -> None:
        self._context.notify_event_to_entity(
            set({entity}),
            builtin_prompt.make_world_skill_system_off_line_prompt(
                self._context.safe_get_entity_name(entity),
                self.extract_behavior_sentence(entity),
            ),
        )

    ######################################################################################################################################################
    def add_world_skill_system_validate_skill_combo_fail_event(
        self, entity: Entity, world_response_plan: WorldSkillSystemResponse
    ) -> None:
        self._context.notify_event_to_entity(
            set({entity}),
            builtin_prompt.make_world_skill_system_validate_skill_combo_fail_prompt(
                self._context.safe_get_entity_name(entity),
                world_response_plan.tag,
                self.extract_behavior_sentence(entity),
                world_response_plan.out_come,
            ),
        )

    ######################################################################################################################################################
    def add_target_agent_off_line_event(
        self,
        entity: Entity,
        target: Entity,
        world_response_plan: WorldSkillSystemResponse,
    ) -> None:
        self._context.notify_event_to_entity(
            set({entity}),
            builtin_prompt.make_target_agent_off_line_prompt(
                self._context.safe_get_entity_name(entity),
                self._context.safe_get_entity_name(target),
                world_response_plan.out_come,
            ),
        )

    ######################################################################################################################################################
    def request_skill_to_target_feedback_reasoning(
        self,
        entity: Entity,
        target: Entity,
        world_response_plan: WorldSkillSystemResponse,
    ) -> Optional[AgentPlan]:

        agent_name = self._context.safe_get_entity_name(target)
        agent = self._context._langserve_agent_system.get_agent(agent_name)
        if agent is None:
            return None

        prompt = builtin_prompt.make_skill_to_target_feedback_reasoning_prompt(
            self._context.safe_get_entity_name(entity),
            agent_name,
            world_response_plan.out_come,
            world_response_plan.tag,
        )

        task = AgentTask.create(
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
    def create_tasks_actor_can_use_skill(
        self, entities: List[Entity]
    ) -> Dict[str, AgentTask]:

        ret: Dict[str, AgentTask] = {}

        for entity in entities:

            agent_name = self._context.safe_get_entity_name(entity)

            agent = self._context._langserve_agent_system.get_agent(agent_name)
            if agent is None:
                continue

            prompt = builtin_prompt.make_reasoning_actor_can_use_skill_prompt(
                agent_name,
                self.extract_body_info(entity),
                self.extract_skill_files(entity),
                self.extract_prop_files(entity),
            )

            task = AgentTask.create(
                agent,
                builtin_prompt.replace_mentions_of_your_name_with_you_prompt(
                    prompt, agent_name
                ),
            )
            if task is None:
                continue

            ret[agent._name] = task

        return ret

    ######################################################################################################################################################
    def create_tasks_world_skill_system_validate_skill_combo(
        self, entities: List[Entity], world_skill_system_name: str
    ) -> List[AgentTask]:

        ret: List[AgentTask] = []

        world_system_agent = self._context._langserve_agent_system.get_agent(
            world_skill_system_name
        )
        if world_system_agent is None:
            return ret

        for entity in entities:

            prompt = builtin_prompt.make_reasoning_world_skill_system_validate_skill_combo_prompt(
                self._context.safe_get_entity_name(entity),
                self.extract_body_info(entity),
                self.extract_skill_files(entity),
                self.extract_prop_files(entity),
                self.extract_behavior_sentence(entity),
            )

            task = AgentTask.create_process_context_without_saving(
                world_system_agent, prompt
            )
            if task is None:
                continue

            safe_name = self._context.safe_get_entity_name(entity)
            task._option_param.setdefault(
                WorldSkillSystemResponse.OPTION_PARAM_NAME, safe_name
            )
            ret.append(task)

        return ret

    ######################################################################################################################################################
