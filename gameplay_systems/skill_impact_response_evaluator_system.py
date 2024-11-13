from dataclasses import dataclass
from entitas import Matcher, ExecuteProcessor, Entity  # type: ignore
from my_components.action_components import (
    DamageAction,
    BroadcastAction,
    TagAction,
)
from my_components.components import (
    AttributesComponent,
    DestroyComponent,
    SkillComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import final, override, List, Optional, Set
import gameplay_systems.builtin_prompt_utils as builtin_prompt_utils
from my_agent.agent_task import AgentTask
from my_agent.agent_plan import AgentPlanResponse
import my_format_string.target_and_message_format_string
import my_format_string.attrs_format_string
from rpg_game.rpg_game import RPGGame
from my_models.entity_models import AttributesIndex
from my_models.event_models import AgentEvent
import gameplay_systems.skill_system_utils
from my_agent.lang_serve_agent import LangServeAgent
from loguru import logger

################################################################################################################################################


def _generate_skill_impact_response_prompt(
    actor_name: str,
    target_name: str,
    reasoning_sentence: str,
    result_desc: str,
) -> str:

    prompt = f"""# {actor_name} 向 {target_name} 发动技能。
## 事件描述
 {reasoning_sentence}

## 系统判断结果
{result_desc}

## 判断步骤
第1步:回顾 {target_name} 的当前状态。
第2步:结合 事件描述 与 系统判断结果，推理技能对 {target_name} 的影响。例如改变你的状态，或者对你造成伤害等。
第3步:更新 {target_name} 的状态，作为最终输出。

## 输出要求
- 请遵循 输出格式指南。
- 返回结果只带如下的键: {BroadcastAction.__name__} 和 {TagAction.__name__}。
- {BroadcastAction.__name__} 的内容格式要求为: "{target_name}对技能的反馈与更新后的状态描述"。
"""

    return prompt


################################################################################################################################################


def _generate_offline_prompt(
    actor_name: str, target_name: str, reasoning_sentence: str
) -> str:

    prompt = f"""# 注意! {actor_name} 无法对 {target_name} 使用技能，本次技能释放被系统取消。
## 行动内容语句({actor_name} 发起)
{reasoning_sentence}
"""
    return prompt


################################################################################################################################################


def _generate_broadcast_skill_impact_response_prompt(
    actor_name: str, target_name: str, reasoning_sentence: str, feedback_sentence: str
) -> str:

    ret_prompt = f"""# 注意场景内发生了如下事件: {actor_name} 向 {target_name} 发动了技能。

## 技能发动的过程描述
{reasoning_sentence}

## {target_name} 受到技能后的反馈
{feedback_sentence}"""

    return ret_prompt


################################################################################################################################################
@final
class InternalPlanResponse(AgentPlanResponse):

    @property
    def impact_result(self) -> str:
        return self._concatenate_values(BroadcastAction.__name__)


################################################################################################################################################
@dataclass
class InternalProcessData:
    source_entity: Entity
    skill_entity: Entity
    target_entities: List[Entity]
    agents: List[LangServeAgent]
    agent_tasks: List[AgentTask]
    task_responses: List[InternalPlanResponse]


################################################################################################################################################


@final
class SkillImpactResponseEvaluatorSystem(ExecuteProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ######################################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    ######################################################################################################################################################
    @override
    async def a_execute1(self) -> None:

        # 只关注技能
        skill_entities = self._context.get_group(
            Matcher(all_of=[SkillComponent], none_of=[DestroyComponent])
        ).entities.copy()

        # 组成成方便的数据结构
        internal_process_data = self._initialize_internal_process_data(skill_entities)
        for process_data in internal_process_data:
            await self._process_skill_impact(process_data)

    ######################################################################################################################################################
    def _initialize_internal_process_data(
        self, skill_entities: Set[Entity]
    ) -> List[InternalProcessData]:

        ret: List[InternalProcessData] = []

        for skill_entity in skill_entities:
            create_internal_process_data = self._create_interal_process_data(
                skill_entity
            )
            if create_internal_process_data is None:
                continue
            ret.append(create_internal_process_data)

        return ret

    ######################################################################################################################################################
    def _create_interal_process_data(
        self, skill_entity: Entity
    ) -> Optional[InternalProcessData]:
        skill_comp = skill_entity.get(SkillComponent)
        if len(skill_comp.targets) < 1:
            return None

        source_entity = self._context.get_actor_entity(skill_comp.name)
        assert source_entity is not None, f"actor_entity {skill_comp.name} not found."

        if source_entity is None:
            return None

        ret = InternalProcessData(
            source_entity=source_entity,
            skill_entity=skill_entity,
            target_entities=[],
            agents=[],
            agent_tasks=[],
            task_responses=[],
        )

        for target_name in skill_comp.targets:

            target_entity = self._context.get_entity_by_name(target_name)
            assert target_entity is not None, f"target_entity {target_name} not found."
            if target_entity is None:
                continue

            agent = self._context.agent_system.get_agent(target_name)
            assert agent is not None, f"agent {target_name} not found."
            if agent is None:
                continue

            # 目标
            ret.target_entities.append(target_entity)

            # 目标的agent
            ret.agents.append(agent)

            # 空的任务
            ret.agent_tasks.append(
                AgentTask.create(
                    agent,
                    builtin_prompt_utils.replace_you(skill_comp.command, agent._name),
                )
            )

            # 空的回复
            ret.task_responses.append(InternalPlanResponse(agent._name, ""))

        # 最后的检查，出问题了就返回None
        if len(ret.target_entities) == 0:
            return None

        return ret

    ######################################################################################################################################################
    async def _process_skill_impact(
        self, internal_process_data: InternalProcessData
    ) -> None:

        for data_index in range(len(internal_process_data.target_entities)):

            target_entity = internal_process_data.target_entities[data_index]
            target_agent = internal_process_data.agents[data_index]
            agent_task = internal_process_data.agent_tasks[data_index] = (
                self._generate_skill_impact_response_task(
                    internal_process_data,
                    target_entity=target_entity,
                    target_agent=target_agent,
                )
            )

            # 这里单步上行
            if agent_task.request() is None:
                self._notify_skill_target_agent_offline(
                    internal_process_data,
                    target_entity=target_entity,
                )
                continue

            # 加入伤害计算的逻辑
            self._evaluate_and_apply_action(
                internal_process_data,
                target_entity=target_entity,
            )

            # 场景事件
            task_response = internal_process_data.task_responses[data_index] = (
                InternalPlanResponse(
                    agent_task.agent_name,
                    agent_task.response_content,
                )
            )
            self._notify_skill_impact_outcome(
                internal_process_data,
                target_entity=target_entity,
                impact_result=task_response.impact_result,
            )

    ######################################################################################################################################################
    def _notify_skill_impact_outcome(
        self,
        internal_process_data: InternalProcessData,
        target_entity: Entity,
        impact_result: str,
    ) -> None:

        current_stage_entity = self._context.safe_get_stage_entity(
            internal_process_data.source_entity
        )
        if current_stage_entity is None:
            return

        self._context.broadcast_event_in_stage(
            current_stage_entity,
            AgentEvent(
                message=_generate_broadcast_skill_impact_response_prompt(
                    self._context.safe_get_entity_name(
                        internal_process_data.source_entity
                    ),
                    self._context.safe_get_entity_name(target_entity),
                    internal_process_data.skill_entity.get(
                        SkillComponent
                    ).world_harmony_inspector_content,
                    impact_result,
                )
            ),
            set({target_entity}),  # 已经参与的双方不需要再被通知了。
        )

    ######################################################################################################################################################
    def _evaluate_and_apply_action(
        self, internal_process_data: InternalProcessData, target_entity: Entity
    ) -> None:

        # 拿到原始的
        total_skill_attributes: List[int] = self._summarize_skill_attributes(
            internal_process_data,
        )

        if len(total_skill_attributes) == 0:
            assert False, f"total_skill_attributes {total_skill_attributes} not found."
            return

        # 补充上发起者的攻击值
        self._compute_entity_attributes(
            internal_process_data.source_entity, target_entity, total_skill_attributes
        )

        # 补充上所有参与的道具的属性
        self._compute_skill_accessory_attributes(
            internal_process_data,
            target_entity=target_entity,
            skill_attribute_outputs=total_skill_attributes,
        )

        # 最终添加到目标的伤害
        self._calculate_and_apply_damage(
            internal_process_data.source_entity,
            target_entity,
            total_skill_attributes,
            self._calculate_bonus(
                internal_process_data,
            ),
        )

        # 添加到最终的治疗
        self._calculate_and_apply_heal(
            internal_process_data.source_entity,
            target_entity,
            total_skill_attributes,
            self._calculate_bonus(
                internal_process_data,
            ),
        )

    ######################################################################################################################################################
    def _calculate_and_apply_heal(
        self,
        source_entity: Entity,
        target_entity: Entity,
        total_skill_attributes: List[int],
        calculate_bonus: float,
    ) -> None:
        assert False, "heal not implemented"
        logger("heal not implemented")

    ######################################################################################################################################################
    def _calculate_and_apply_damage(
        self,
        source_entity: Entity,
        target_entity: Entity,
        total_skill_attributes: List[int],
        calculate_bonus: float,
    ) -> None:

        total_skill_attributes[AttributesIndex.DAMAGE] = int(
            total_skill_attributes[AttributesIndex.DAMAGE] * calculate_bonus
        )
        if total_skill_attributes[AttributesIndex.DAMAGE] == 0:
            return

        #
        formatted_damage_message = (
            my_format_string.target_and_message_format_string.make_target_and_message(
                self._context.safe_get_entity_name(source_entity),
                my_format_string.attrs_format_string.from_int_attrs_to_string(
                    total_skill_attributes
                ),
            )
        )

        if not target_entity.has(DamageAction):
            target_entity.replace(
                DamageAction,
                self._context.safe_get_entity_name(target_entity),
                [formatted_damage_message],
            )
        else:

            damage_action = target_entity.get(DamageAction)
            damage_action.values.append(formatted_damage_message)
            target_entity.replace(
                DamageAction, damage_action.name, damage_action.values
            )

    ######################################################################################################################################################
    def _compute_entity_attributes(
        self,
        source_entity: Entity,
        target_entity: Entity,
        skill_attribute_output: List[int],
    ) -> None:

        if not source_entity.has(AttributesComponent):
            return
        attr_comp = source_entity.get(AttributesComponent)
        skill_attribute_output[AttributesIndex.DAMAGE] += attr_comp.attack

    ######################################################################################################################################################
    def _compute_skill_accessory_attributes(
        self,
        internal_process_data: InternalProcessData,
        target_entity: Entity,
        skill_attribute_outputs: List[int],
    ) -> None:

        if len(skill_attribute_outputs) == 0:
            return

        data = gameplay_systems.skill_system_utils.parse_skill_accessory_prop_files(
            context=self._context,
            skill_entity=internal_process_data.skill_entity,
            actor_entity=internal_process_data.source_entity,
        )

        for prop_file_with_count in data:
            for attr_index in range(len(skill_attribute_outputs)):
                prop_file = prop_file_with_count[0]
                cunsume_count = prop_file_with_count[1]
                skill_attribute_outputs[attr_index] += prop_file.prop_model.attributes[
                    attr_index
                ]

    ######################################################################################################################################################
    def _summarize_skill_attributes(
        self, internal_process_data: InternalProcessData
    ) -> List[int]:

        skill_prop_files = gameplay_systems.skill_system_utils.parse_skill_prop_files(
            context=self._context,
            skill_entity=internal_process_data.skill_entity,
            actor_entity=internal_process_data.source_entity,
        )
        assert (
            len(skill_prop_files) > 0
        ), f"skill_prop_files {skill_prop_files} not found."
        if len(skill_prop_files) == 0:
            return []

        accumulated_attributes: List[int] = []
        for skill_prop_file in skill_prop_files:
            if len(accumulated_attributes) == 0:
                accumulated_attributes = skill_prop_file.prop_model.attributes.copy()
            else:
                for i in range(len(accumulated_attributes)):
                    accumulated_attributes[i] += skill_prop_file.prop_model.attributes[
                        i
                    ]
        return accumulated_attributes

    ######################################################################################################################################################
    def _notify_skill_target_agent_offline(
        self, internal_process_data: InternalProcessData, target_entity: Entity
    ) -> None:

        self._context.notify_event(
            set({internal_process_data.source_entity}),
            AgentEvent(
                message=_generate_offline_prompt(
                    self._context.safe_get_entity_name(
                        internal_process_data.source_entity
                    ),
                    self._context.safe_get_entity_name(target_entity),
                    internal_process_data.skill_entity.get(
                        SkillComponent
                    ).world_harmony_inspector_content,
                )
            ),
        )

    ######################################################################################################################################################
    def _generate_skill_impact_response_task(
        self,
        internal_process_data: InternalProcessData,
        target_entity: Entity,
        target_agent: LangServeAgent,
    ) -> AgentTask:

        target_agent_name = self._context.safe_get_entity_name(target_entity)

        prompt = _generate_skill_impact_response_prompt(
            self._context.safe_get_entity_name(internal_process_data.source_entity),
            target_agent_name,
            internal_process_data.skill_entity.get(
                SkillComponent
            ).world_harmony_inspector_content,
            internal_process_data.skill_entity.get(
                SkillComponent
            ).world_harmony_inspector_tag,
        )

        return AgentTask.create(
            target_agent,
            builtin_prompt_utils.replace_you(prompt, target_agent_name),
        )

    ######################################################################################################################################################
    def _calculate_bonus(self, internal_process_data: InternalProcessData) -> float:
        skill_comp = internal_process_data.skill_entity.get(SkillComponent)
        value = skill_comp.world_harmony_inspector_value / 100
        if value < 0:
            value = 0

        return value

    ######################################################################################################################################################
