from dataclasses import dataclass
from entitas import Matcher, ExecuteProcessor, Entity  # type: ignore
from my_components.action_components import (
    DamageAction,
    AnnounceAction,
    TagAction,
)
from my_components.components import (
    AttributesComponent,
    DestroyComponent,
    SkillComponent,
    StageComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import final, override, List, Optional, Set
import gameplay_systems.prompt_utils
from my_agent.agent_task import AgentTask
from my_agent.agent_plan import AgentPlanResponse
import my_format_string.target_message
import my_format_string.ints_string
from rpg_game.rpg_game import RPGGame
from my_models.entity_models import Attributes
from my_models.event_models import AgentEvent
import gameplay_systems.skill_entity_utils
from my_agent.lang_serve_agent import LangServeAgent
from loguru import logger
import gameplay_systems.action_component_utils


################################################################################################################################################
def _generate_skill_impact_response_prompt(
    actor_name: str,
    target_name: str,
    world_harmony_inspector_content: str,
    world_harmony_inspector_tag: str,
    is_stage: bool,
) -> str:

    prompt = f"""# {actor_name} 向 {target_name} 发动技能。
## 事件描述
 {world_harmony_inspector_content}

## 系统判断结果
{world_harmony_inspector_tag}

## 判断步骤
第1步:回顾 {target_name} 的当前状态。
第2步:结合 事件描述 与 系统判断结果，推理技能对 {target_name} 的影响。例如改变你的状态，或者对你造成伤害等。
第3步:更新 {target_name} 的状态，作为最终输出。

## 输出要求
- 请遵循 输出格式指南。
- 返回结果只带如下的键: {AnnounceAction.__name__} 和 {TagAction.__name__}。
- {AnnounceAction.__name__} 的内容格式要求为: "{target_name}对技能的反馈与更新后的状态描述"。"""

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
    def impact(self) -> str:
        return self._concatenate_values(AnnounceAction.__name__)


################################################################################################################################################
@dataclass
class InternalProcessData:
    source_entity: Entity
    skill_entity: Entity
    target_entities: List[Entity]
    target_agents: List[LangServeAgent]
    target_tasks: List[AgentTask]
    target_responses: List[InternalPlanResponse]


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

        # 全部收集起来，然后批量执行
        populate_target_tasks: List[AgentTask] = []
        for process_data in internal_process_data:
            populate_target_tasks.extend(self._populate_target_tasks(process_data))

        # 批量执行
        await AgentTask.gather(populate_target_tasks)

        for process_data in internal_process_data:
            self._process_skill_impact(process_data)

    ######################################################################################################################################################
    def _populate_target_tasks(
        self, internal_process_data: InternalProcessData
    ) -> List[AgentTask]:

        ret: List[AgentTask] = []

        for data_index in range(len(internal_process_data.target_entities)):
            internal_process_data.target_tasks[data_index] = (
                self._generate_skill_impact_response_task(
                    internal_process_data,
                    target_entity=internal_process_data.target_entities[data_index],
                    target_agent=internal_process_data.target_agents[data_index],
                )
            )

            ret.append(internal_process_data.target_tasks[data_index])

        return ret

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
            target_agents=[],
            target_tasks=[],
            target_responses=[],
        )

        for target_name in skill_comp.targets:

            target_entity = self._context.get_entity_by_name(target_name)
            assert target_entity is not None, f"target_entity {target_name} not found."
            if target_entity is None:
                continue

            agent = self._context.safe_get_agent(target_entity)
            # 目标
            ret.target_entities.append(target_entity)

            # 目标的agent
            ret.target_agents.append(agent)

            # 空的任务
            ret.target_tasks.append(
                AgentTask.create_with_full_context(
                    agent,
                    gameplay_systems.prompt_utils.replace_you(
                        skill_comp.command, agent.name
                    ),
                )
            )

            # 空的回复
            ret.target_responses.append(InternalPlanResponse(agent.name, ""))

        # 最后的检查，出问题了就返回None
        if len(ret.target_entities) == 0:
            return None

        return ret

    ######################################################################################################################################################
    def _process_skill_impact(self, internal_process_data: InternalProcessData) -> None:

        # 然后处理返回结果
        for data_index in range(len(internal_process_data.target_tasks)):

            # 拿任务，看看有没有返回内容
            agent_task = internal_process_data.target_tasks[data_index]
            if agent_task.response_content == "":
                self._notify_skill_target_agent_offline(
                    internal_process_data,
                    target_entity=internal_process_data.target_entities[data_index],
                )
                # 没有返回内容，通知掉线后直接跳过
                continue

            # 计算处理完毕，开始处理数据，第一步先存储下来。
            internal_process_data.target_responses[data_index] = InternalPlanResponse(
                agent_task.agent_name,
                agent_task.response_content,
            )

            # 开始处理计算！！！！！！！！！！！！！！！！！！
            self._evaluate_and_apply_action(
                internal_process_data,
                target_entity=internal_process_data.target_entities[data_index],
                target_plan_response=internal_process_data.target_responses[data_index],
            )

            # 通知技能的影响结果
            self._notify_skill_impact_outcome(
                internal_process_data,
                target_entity=internal_process_data.target_entities[data_index],
                impact_result=internal_process_data.target_responses[data_index].impact,
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

        self._context.broadcast_event(
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
        self,
        internal_process_data: InternalProcessData,
        target_entity: Entity,
        target_plan_response: InternalPlanResponse,
    ) -> None:

        # 拿到原始的
        total_skill_attributes: List[int] = self._summarize_skill_attributes(
            internal_process_data,
        )

        assert (
            len(total_skill_attributes) > 0
        ), f"total_skill_attributes {total_skill_attributes} not found."
        if len(total_skill_attributes) == 0:
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

        # 处理场景是否要添加动作。
        self._evaluate_stage_actions(
            internal_process_data, target_entity, target_plan_response
        )

    ######################################################################################################################################################
    def _evaluate_stage_actions(
        self,
        internal_process_data: InternalProcessData,
        target_stage_entity: Entity,
        internal_plan_response: InternalPlanResponse,
    ) -> None:

        if not target_stage_entity.has(StageComponent):
            return

        gameplay_systems.action_component_utils.add_stage_actions(
            self._context, target_stage_entity, internal_plan_response
        )
        assert False, "add_stage_actions not implemented"

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

        total_skill_attributes[Attributes.DAMAGE] = int(
            total_skill_attributes[Attributes.DAMAGE] * calculate_bonus
        )
        if total_skill_attributes[Attributes.DAMAGE] == 0:
            return

        #
        formatted_damage_message = (
            my_format_string.target_message.generate_target_message_pair(
                self._context.safe_get_entity_name(source_entity),
                my_format_string.ints_string.convert_ints_to_string(
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
        skill_attribute_output[Attributes.DAMAGE] += attr_comp.attack

    ######################################################################################################################################################
    def _compute_skill_accessory_attributes(
        self,
        internal_process_data: InternalProcessData,
        target_entity: Entity,
        skill_attribute_outputs: List[int],
    ) -> None:

        if len(skill_attribute_outputs) == 0:
            return

        data = gameplay_systems.skill_entity_utils.parse_skill_accessory_prop_files(
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

        skill_prop_files = gameplay_systems.skill_entity_utils.parse_skill_prop_files(
            context=self._context,
            skill_entity=internal_process_data.skill_entity,
            actor_entity=internal_process_data.source_entity,
        )
        assert (
            len(skill_prop_files) > 0
        ), f"skill_prop_files {skill_prop_files} not found."
        if len(skill_prop_files) == 0:
            return []

        accumulated_attributes: List[int] = skill_prop_files[
            0
        ].prop_model.attributes.copy()
        for skill_prop_file in skill_prop_files[1:]:
            for j in range(len(accumulated_attributes)):
                accumulated_attributes[j] += skill_prop_file.prop_model.attributes[j]
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

        target_name = self._context.safe_get_entity_name(target_entity)
        skill_comp = internal_process_data.skill_entity.get(SkillComponent)

        prompt = _generate_skill_impact_response_prompt(
            actor_name=self._context.safe_get_entity_name(
                internal_process_data.source_entity
            ),
            target_name=target_name,
            world_harmony_inspector_content=skill_comp.world_harmony_inspector_content,
            world_harmony_inspector_tag=skill_comp.world_harmony_inspector_tag,
            is_stage=target_entity.has(StageComponent),
        )

        return AgentTask.create_with_full_context(
            target_agent,
            gameplay_systems.prompt_utils.replace_you(prompt, target_name),
        )

    ######################################################################################################################################################
    def _calculate_bonus(
        self,
        internal_process_data: InternalProcessData,
        reference_value: int = Attributes.BASE_VALUE_SCALE,
    ) -> float:
        skill_comp = internal_process_data.skill_entity.get(SkillComponent)
        value = skill_comp.world_harmony_inspector_value / reference_value
        if value < 0:
            value = 0

        return value

    ######################################################################################################################################################
