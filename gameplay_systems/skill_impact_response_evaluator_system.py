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
from typing import final, override, List, Optional, Dict, Set
import gameplay_systems.builtin_prompt_util as builtin_prompt_util
from my_agent.agent_task import AgentTask
from my_agent.agent_plan import AgentPlanResponse
import my_format_string.target_and_message_format_string
import my_format_string.attrs_format_string
from rpg_game.rpg_game import RPGGame
from my_models.entity_models import AttributesIndex
from my_models.event_models import AgentEvent
import gameplay_systems.skill_system_utils

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
class InternalProcessor:
    actor_entity: Entity
    skill_entity: Entity
    agent_task: Optional[AgentTask]
    task_response: Dict[str, InternalPlanResponse] = {}


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
        skill_processors = self._initialize_processors(skill_entities)
        for processor in skill_processors:
            await self._process_skill_impact(processor)

    ######################################################################################################################################################
    def _initialize_processors(
        self, skill_entities: Set[Entity]
    ) -> List[InternalProcessor]:
        ret: List[InternalProcessor] = []
        for skill_entity in skill_entities:
            skill_comp = skill_entity.get(SkillComponent)
            actor_entity = self._context.get_actor_entity(skill_comp.name)
            assert (
                actor_entity is not None
            ), f"actor_entity {skill_comp.name} not found."
            ret.append(InternalProcessor(actor_entity, skill_entity, None))
        return ret

    ######################################################################################################################################################
    async def _process_skill_impact(self, skill_processor: InternalProcessor) -> None:

        skill_comp = skill_processor.skill_entity.get(SkillComponent)
        for target_name in skill_comp.targets:

            target_entity = self._context.get_entity_by_name(target_name)
            if target_entity is None:
                continue

            skill_impact_response_task = self._generate_skill_impact_response_task(
                skill_entity=skill_processor.skill_entity,
                source_entity=skill_processor.actor_entity,
                target_entity=target_entity,
            )
            if skill_impact_response_task is None:
                self._on_skill_target_agent_off_line_event(
                    skill_entity=skill_processor.skill_entity,
                    source_entity=skill_processor.actor_entity,
                    target_entity=target_entity,
                )
                continue

            if skill_impact_response_task.request() is None:
                self._on_skill_target_agent_off_line_event(
                    skill_entity=skill_processor.skill_entity,
                    source_entity=skill_processor.actor_entity,
                    target_entity=target_entity,
                )
                continue

            # 加入伤害计算的逻辑
            self._evaluate_and_apply_action(
                skill_entity=skill_processor.skill_entity,
                source_entity=skill_processor.actor_entity,
                target_entity=target_entity,
            )

            # 场景事件
            response_plan = InternalPlanResponse(
                skill_impact_response_task.agent_name,
                skill_impact_response_task.response_content,
            )
            self._on_broadcast_skill_impact_response_event(
                skill_entity=skill_processor.skill_entity,
                source_entity=skill_processor.actor_entity,
                target_entity=target_entity,
                impact_result=response_plan.impact_result,
            )

    ######################################################################################################################################################
    def _on_broadcast_skill_impact_response_event(
        self,
        skill_entity: Entity,
        source_entity: Entity,
        target_entity: Entity,
        impact_result: str,
    ) -> None:

        current_stage_entity = self._context.safe_get_stage_entity(source_entity)
        if current_stage_entity is None:
            return

        self._context.broadcast_event_in_stage(
            current_stage_entity,
            AgentEvent(
                message=_generate_broadcast_skill_impact_response_prompt(
                    self._context.safe_get_entity_name(source_entity),
                    self._context.safe_get_entity_name(target_entity),
                    skill_entity.get(SkillComponent).world_harmony_inspector_content,
                    impact_result,
                )
            ),
            set({target_entity}),  # 已经参与的双方不需要再被通知了。
        )

    ######################################################################################################################################################
    def _evaluate_and_apply_action(
        self, skill_entity: Entity, source_entity: Entity, target_entity: Entity
    ) -> None:

        # 拿到原始的
        calculate_attrs: List[int] = self._calculate_skill_attributes(
            skill_entity=skill_entity, source_entity=source_entity
        )
        # 补充上发起者的攻击值
        self._calculate_attr_component(source_entity, target_entity, calculate_attrs)
        # 补充上所有参与的道具的属性
        self._calculate_skill_accessory_props(
            skill_entity=skill_entity,
            source_entity=source_entity,
            target_entity=target_entity,
            out_put_skill_attrs=calculate_attrs,
        )
        # 最终添加到目标的伤害
        self._apply_damage(
            source_entity,
            target_entity,
            calculate_attrs,
            self._determine_damage_bonus(
                skill_entity=skill_entity, source_entity=source_entity
            ),
        )

    ######################################################################################################################################################
    def _apply_damage(
        self,
        source_entity: Entity,
        target_entity: Entity,
        skill_attrs: List[int],
        buff: float = 1.0,
    ) -> None:

        skill_attrs[AttributesIndex.DAMAGE.value] = int(
            skill_attrs[AttributesIndex.DAMAGE.value] * buff
        )

        if skill_attrs[AttributesIndex.DAMAGE.value] == 0:
            return

        target_entity.replace(
            DamageAction,
            self._context.safe_get_entity_name(target_entity),
            [],
        )

        target_entity.get(DamageAction).values.append(
            my_format_string.target_and_message_format_string.make_target_and_message(
                self._context.safe_get_entity_name(source_entity),
                my_format_string.attrs_format_string.from_int_attrs_to_string(
                    skill_attrs
                ),
            )
        )

    ######################################################################################################################################################
    def _calculate_attr_component(
        self,
        source_entity: Entity,
        target_entity: Entity,
        out_put_skill_attrs: List[int],
    ) -> None:

        if not source_entity.has(AttributesComponent):
            return

        rpg_attr_comp = source_entity.get(AttributesComponent)
        out_put_skill_attrs[AttributesIndex.DAMAGE.value] += rpg_attr_comp.attack

    ######################################################################################################################################################
    def _calculate_skill_accessory_props(
        self,
        skill_entity: Entity,
        source_entity: Entity,
        target_entity: Entity,
        out_put_skill_attrs: List[int],
    ) -> None:

        data = gameplay_systems.skill_system_utils.parse_skill_accessory_prop_files(
            context=self._context, skill_entity=skill_entity, actor_entity=source_entity
        )
        for prop_file_and_count_data in data:
            for i in range(len(out_put_skill_attrs)):
                prop_file = prop_file_and_count_data[0]
                cunsume_count = prop_file_and_count_data[1]
                out_put_skill_attrs[i] += (
                    prop_file.prop_model.attributes[i] * cunsume_count
                )

    ######################################################################################################################################################
    def _calculate_skill_attributes(
        self, skill_entity: Entity, source_entity: Entity
    ) -> List[int]:
        final_attr: List[int] = []
        for (
            skill_prop_file
        ) in gameplay_systems.skill_system_utils.parse_skill_prop_files(
            context=self._context, skill_entity=skill_entity, actor_entity=source_entity
        ):
            if len(final_attr) == 0:
                final_attr = skill_prop_file.prop_model.attributes
            else:
                for i in range(len(final_attr)):
                    final_attr[i] += skill_prop_file.prop_model.attributes[i]
        return final_attr

    ######################################################################################################################################################
    def _on_skill_target_agent_off_line_event(
        self, skill_entity: Entity, source_entity: Entity, target_entity: Entity
    ) -> None:

        self._context.notify_event(
            set({source_entity}),
            AgentEvent(
                message=_generate_offline_prompt(
                    self._context.safe_get_entity_name(source_entity),
                    self._context.safe_get_entity_name(target_entity),
                    skill_entity.get(SkillComponent).world_harmony_inspector_content,
                )
            ),
        )

    ######################################################################################################################################################
    def _generate_skill_impact_response_task(
        self, skill_entity: Entity, source_entity: Entity, target_entity: Entity
    ) -> Optional[AgentTask]:

        target_agent_name = self._context.safe_get_entity_name(target_entity)
        target_agent = self._context.agent_system.get_agent(target_agent_name)
        if target_agent is None:
            return None

        prompt = _generate_skill_impact_response_prompt(
            self._context.safe_get_entity_name(source_entity),
            target_agent_name,
            skill_entity.get(SkillComponent).world_harmony_inspector_content,
            skill_entity.get(SkillComponent).world_harmony_inspector_tag,
        )

        return AgentTask.create(
            target_agent,
            builtin_prompt_util.replace_you(prompt, target_agent_name),
        )

    ######################################################################################################################################################
    def _determine_damage_bonus(
        self, skill_entity: Entity, source_entity: Entity
    ) -> float:

        if (
            skill_entity.get(SkillComponent).world_harmony_inspector_tag
            == builtin_prompt_util.ConstantSkillPrompt.CRITICAL_SUCCESS
        ):
            return 1.5  # 先写死，测试的时候再改。todo

        return 1.0  # 默认的。

    ######################################################################################################################################################
