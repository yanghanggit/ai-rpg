from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from gameplay_systems.action_components import (
    BehaviorAction,
    SkillTargetAction,
    SkillAction,
    SkillPropAction,
    TagAction,
    BroadcastAction,
    DamageAction,
)
from gameplay_systems.components import (
    BodyComponent,
    RPGAttributesComponent,
    RPGCurrentWeaponComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import override, List, cast, Optional, Set
from loguru import logger
from file_system.files_def import PropFile
import gameplay_systems.cn_builtin_prompt as builtin_prompt
from my_agent.lang_serve_agent_request_task import LangServeAgentRequestTask
from my_agent.agent_plan import AgentPlan
from gameplay_systems.cn_constant_prompt import _CNConstantPrompt_ as ConstantPrompt
import gameplay_systems.cn_builtin_prompt as builtin_prompt
import my_format_string.target_and_message_format_string
import my_format_string.attrs_format_string
from rpg_game.rpg_game import RPGGame
from my_data.model_def import AttributesIndex


class WorldSkillSystemReasoningResponse(AgentPlan):

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

    def __init__(
        self, context: RPGEntitasContext, rpg_game: RPGGame, system_name: str
    ) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game
        self._system_name: str = system_name

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
        )

    ######################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.handle(entity)

    ######################################################################################################################################################
    def handle(self, entity: Entity) -> None:

        assert entity.has(SkillAction) and entity.has(SkillTargetAction)

        # 没有世界系统就是错误
        world_entity = self._context.get_world_entity(self._system_name)
        if world_entity is None:
            logger.error(f"{self._system_name}, world_entity is None.")
            return

        # 准备数据
        body = self.get_body(entity)
        skill_files = self.get_skill_files(entity)
        prop_files = self.get_prop_files(entity)

        world_response = self.request_world_skill_system_reasoning(
            entity, world_entity, body, skill_files, prop_files
        )

        if world_response is None:
            self.on_world_skill_system_off_line_error(entity)
            return  # 全局技能系统是不是掉线了？

        # 单独处理失败和大失败
        if (
            world_response.result_description == ConstantPrompt.BIG_FAILURE
            or world_response.result_description == ConstantPrompt.FAILURE
        ):

            self.on_world_skill_system_reasoning_result_is_failure(
                entity, world_response
            )
            return  # 不要再往下走了。全局技能系统推理出失败 就提示下一下截断掉

        # 释放技能
        self.handle_release_skill(entity, world_response)

    ######################################################################################################################################################
    def handle_release_skill(
        self, entity: Entity, world_response: WorldSkillSystemReasoningResponse
    ) -> None:
        # 释放技能
        for target in self.get_targets(entity):

            target_response = self.request_release_skill_to_target_reasoning(
                entity, target, world_response
            )

            if target_response is None:
                self.on_skill_skill_target_agent_off_line_error(
                    entity, target, world_response
                )
                continue  # 目标是不是掉线了？

            # 加入伤害计算的逻辑
            self.on_add_action_to_target(entity, target)

            # 场景事件
            self.on_notify_release_skill_event(entity, target, world_response)

    ######################################################################################################################################################
    def on_notify_release_skill_event(
        self,
        entity: Entity,
        target_entity: Entity,
        world_response: WorldSkillSystemReasoningResponse,
    ) -> None:

        current_stage_entity = self._context.safe_get_stage_entity(entity)
        if current_stage_entity is None:
            return

        self._context.add_agent_context_message(
            set({current_stage_entity}),
            builtin_prompt.make_notify_release_skill_event_prompt(
                self._context.safe_get_entity_name(entity),
                self._context.safe_get_entity_name(target_entity),
                world_response.reasoning_sentence,
            ),
        )

    ######################################################################################################################################################
    def on_add_action_to_target(self, entity: Entity, target: Entity) -> None:

        # 拿到原始的
        skill_attrs: List[int] = self.get_skill_attrs(entity)
        # 补充上发起者的攻击值
        self.add_value_of_attr_component_to_skill_attrs(entity, target, skill_attrs)
        # 补充上所有参与的道具的属性
        self.add_values_from_prop_files(entity, target, skill_attrs)
        # 最终添加到目标的伤害行为
        self.on_add_damage_action_to_target(entity, target, skill_attrs)

    ######################################################################################################################################################
    def on_add_damage_action_to_target(
        self, entity: Entity, target: Entity, skill_attrs: List[int]
    ) -> None:
        if skill_attrs[AttributesIndex.ATTACK.value] == 0:
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

    def add_value_of_attr_component_to_skill_attrs(
        self, entity: Entity, target: Entity, out_put_skill_attrs: List[int]
    ) -> None:

        if not entity.has(RPGAttributesComponent):
            return

        rpg_attr_comp = entity.get(RPGAttributesComponent)
        out_put_skill_attrs[AttributesIndex.MAX_HP.value] += rpg_attr_comp.maxhp
        out_put_skill_attrs[AttributesIndex.CUR_HP.value] += rpg_attr_comp.hp
        out_put_skill_attrs[AttributesIndex.ATTACK.value] += rpg_attr_comp.attack
        out_put_skill_attrs[AttributesIndex.DEFENSE.value] += rpg_attr_comp.defense

    ######################################################################################################################################################
    def add_values_from_prop_files(
        self, entity: Entity, target: Entity, out_put_skill_attrs: List[int]
    ) -> None:
        prop_files = self.get_prop_files(entity)
        for prop_file in prop_files:
            for i in range(len(out_put_skill_attrs)):
                out_put_skill_attrs[i] += prop_file._prop_model.attributes[i]

    ######################################################################################################################################################
    def get_skill_attrs(self, entity: Entity) -> List[int]:
        final_attr: List[int] = []
        for skill_file in self.get_skill_files(entity):
            if len(final_attr) == 0:
                final_attr = skill_file._prop_model.attributes
            else:
                for i in range(len(final_attr)):
                    final_attr[i] += skill_file._prop_model.attributes[i]
        return final_attr

    ######################################################################################################################################################
    def on_world_skill_system_off_line_error(self, entity: Entity) -> None:
        self._context.add_agent_context_message(
            set({entity}),
            builtin_prompt.make_world_skill_system_off_line_error_prompt(
                self._context.safe_get_entity_name(entity),
                self.get_behavior_sentence(entity),
            ),
        )

    ######################################################################################################################################################
    def on_world_skill_system_reasoning_result_is_failure(
        self, entity: Entity, world_response_plan: WorldSkillSystemReasoningResponse
    ) -> None:
        self._context.add_agent_context_message(
            set({entity}),
            builtin_prompt.make_world_skill_system_reasoning_result_is_failure_prompt(
                self._context.safe_get_entity_name(entity),
                world_response_plan.result_description,
                self.get_behavior_sentence(entity),
                world_response_plan.reasoning_sentence,
            ),
        )

    ######################################################################################################################################################
    def on_skill_skill_target_agent_off_line_error(
        self,
        entity: Entity,
        target: Entity,
        world_response_plan: WorldSkillSystemReasoningResponse,
    ) -> None:
        self._context.add_agent_context_message(
            set({entity}),
            builtin_prompt.make_skill_skill_target_agent_off_line_error_prompt(
                self._context.safe_get_entity_name(entity),
                self._context.safe_get_entity_name(target),
                world_response_plan.reasoning_sentence,
            ),
        )

    ######################################################################################################################################################

    def get_behavior_sentence(self, entity: Entity) -> str:
        behavior_action = entity.get(BehaviorAction)
        if behavior_action is None or len(behavior_action.values) == 0:
            return ""
        return cast(str, behavior_action.values[0])

    ######################################################################################################################################################
    def get_targets(self, entity: Entity) -> Set[Entity]:
        assert entity.has(SkillTargetAction)
        targets = set()
        for target_name in entity.get(SkillTargetAction).values:
            target = self._context.get_entity_by_name(target_name)
            if target is not None:
                targets.add(target)
        return targets

    ######################################################################################################################################################
    def request_release_skill_to_target_reasoning(
        self,
        entity: Entity,
        target: Entity,
        world_response_plan: WorldSkillSystemReasoningResponse,
    ) -> Optional[AgentPlan]:

        agent_name = self._context.safe_get_entity_name(target)
        agent = self._context._langserve_agent_system.get_agent(agent_name)
        if agent is None:
            return None

        prompt = builtin_prompt.make_reasoning_skill_target_reasoning_prompt(
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
    def request_world_skill_system_reasoning(
        self,
        entity: Entity,
        world_entity: Entity,
        actor_info: str,
        skill_files: List[PropFile],
        prop_files: List[PropFile],
    ) -> Optional[WorldSkillSystemReasoningResponse]:

        # 生成提示
        prompt = builtin_prompt.make_world_reasoning_release_skill_prompt(
            self._context.safe_get_entity_name(entity),
            actor_info,
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

        return WorldSkillSystemReasoningResponse(agent._name, response)

    ######################################################################################################################################################
    def get_skill_files(self, entity: Entity) -> List[PropFile]:
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
    def get_body(self, entity: Entity) -> str:
        assert entity.has(BodyComponent)
        if not entity.has(BodyComponent):
            return ""
        return str(entity.get(BodyComponent).body)

    ######################################################################################################################################################
    def get_prop_files(self, entity: Entity) -> List[PropFile]:
        if not entity.has(SkillPropAction):
            return []

        safe_name = self._context.safe_get_entity_name(entity)
        prop_action = entity.get(SkillPropAction)
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
