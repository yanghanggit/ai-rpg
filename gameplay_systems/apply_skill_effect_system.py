from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from gameplay_systems.action_components import (
    BehaviorAction,
    SkillTargetAction,
    SkillAction,
    SkillUsePropAction,
    DamageAction,
    WorldSkillSystemRuleAction,
    BroadcastAction,
    TagAction,
)
from gameplay_systems.components import (
    BodyComponent,
    RPGAttributesComponent,
    ActorComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import override, List, cast, Optional, Set
from extended_systems.files_def import PropFile
import gameplay_systems.public_builtin_prompt as public_builtin_prompt
from my_agent.agent_task import AgentTask
from my_agent.agent_plan import AgentPlanResponse
import my_format_string.target_and_message_format_string
import my_format_string.attrs_format_string
from rpg_game.rpg_game import RPGGame
from my_data.model_def import AttributesIndex

################################################################################################################################################


def _generate_skill_hit_feedback_prompt(
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


def _generate_skill_event_notification_prompt(
    actor_name: str, target_name: str, reasoning_sentence: str, feedback_sentence: str
) -> str:

    ret_prompt = f"""# 注意场景内发生了如下事件: {actor_name} 向 {target_name} 发动了技能。

## 技能发动的过程描述
{reasoning_sentence}

## {target_name} 受到技能后的反馈
{feedback_sentence}"""

    return ret_prompt


################################################################################################################################################
class SkillFeedbackResponse(AgentPlanResponse):

    @property
    def feedback(self) -> str:
        return self._concatenate_values(BroadcastAction.__name__)


################################################################################################################################################


class ApplySkillEffectSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)

        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game
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
            and entity.has(WorldSkillSystemRuleAction)
            and entity.has(ActorComponent)
        ) or entity.has(SkillUsePropAction)

    ######################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        self._react_entities_copy = entities.copy()

    ######################################################################################################################################################
    @override
    async def a_execute2(self) -> None:

        for entity in self._react_entities_copy:
            await self.handle(entity)

        self._react_entities_copy.clear()

    ######################################################################################################################################################
    async def handle(self, entity: Entity) -> None:
        # 释放技能
        for target in self.extract_targets(entity):

            task = self.create_task(entity, target)
            if task is None:
                self.on_skill_target_agent_off_line_event(entity, target)
                continue

            if task.request() is None:
                self.on_skill_target_agent_off_line_event(entity, target)
                continue

            # 加入伤害计算的逻辑
            self.calculate_and_add_action(entity, target)

            # 场景事件
            response_plan = SkillFeedbackResponse(
                task.agent_name, task.response_content
            )
            self.on_broadcast_skill_event(entity, target, response_plan.feedback)

    ######################################################################################################################################################

    def extract_behavior_sentence(self, entity: Entity) -> str:
        behavior_action = entity.get(BehaviorAction)
        if behavior_action is None or len(behavior_action.values) == 0:
            return ""
        return behavior_action.values[0]

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
        skill_use_prop_action = entity.get(SkillUsePropAction)
        ret: List[PropFile] = []
        for prop_name in skill_use_prop_action.values:
            prop_file = self._context._file_system.get_file(
                PropFile, safe_name, prop_name
            )
            if prop_file is None:
                continue
            ret.append(prop_file)

        return ret

    ######################################################################################################################################################

    def on_broadcast_skill_event(
        self, from_entity: Entity, target_entity: Entity, target_feedback: str
    ) -> None:

        current_stage_entity = self._context.safe_get_stage_entity(from_entity)
        if current_stage_entity is None:
            return

        world_skill_system_rule_tag, world_skill_system_rule_out_come = (
            self.extract_world_skill_system_rule(from_entity)
        )

        self._context.broadcast_event_in_stage(
            current_stage_entity,
            _generate_skill_event_notification_prompt(
                self._context.safe_get_entity_name(from_entity),
                self._context.safe_get_entity_name(target_entity),
                world_skill_system_rule_out_come,
                target_feedback,
            ),
            set({target_entity}),  # 已经参与的双方不需要再被通知了。
        )

    ######################################################################################################################################################
    def calculate_and_add_action(self, entity: Entity, target: Entity) -> None:

        # 拿到原始的
        calculate_attrs: List[int] = self.gen_skill_attrs(entity)
        # 补充上发起者的攻击值
        self.calculate_attr_comp(entity, target, calculate_attrs)
        # 补充上所有参与的道具的属性
        self.calculate_props(entity, target, calculate_attrs)
        # 最终添加到目标的伤害
        self.add_damage(entity, target, calculate_attrs, self.get_damage_buff(entity))

    ######################################################################################################################################################
    def add_damage(
        self, entity: Entity, target: Entity, skill_attrs: List[int], buff: float = 1.0
    ) -> None:

        skill_attrs[AttributesIndex.DAMAGE.value] = int(
            skill_attrs[AttributesIndex.DAMAGE.value] * buff
        )

        if skill_attrs[AttributesIndex.DAMAGE.value] == 0:
            return

        if not target.has(DamageAction):
            target.add(
                DamageAction,
                self._context.safe_get_entity_name(target),
                [],
            )

        target.get(DamageAction).values.append(
            my_format_string.target_and_message_format_string.make_target_and_message(
                self._context.safe_get_entity_name(entity),
                my_format_string.attrs_format_string.from_int_attrs_to_string(
                    skill_attrs
                ),
            )
        )

    ######################################################################################################################################################

    def calculate_attr_comp(
        self, entity: Entity, target: Entity, out_put_skill_attrs: List[int]
    ) -> None:

        if not entity.has(RPGAttributesComponent):
            return

        rpg_attr_comp = entity.get(RPGAttributesComponent)
        out_put_skill_attrs[AttributesIndex.DAMAGE.value] += rpg_attr_comp.attack

    ######################################################################################################################################################
    def calculate_props(
        self, entity: Entity, target: Entity, out_put_skill_attrs: List[int]
    ) -> None:
        prop_files = self.extract_prop_files(entity)
        for prop_file in prop_files:
            for i in range(len(out_put_skill_attrs)):
                out_put_skill_attrs[i] += prop_file._prop_model.attributes[i]

    ######################################################################################################################################################
    def gen_skill_attrs(self, entity: Entity) -> List[int]:
        final_attr: List[int] = []
        for skill_file in self.extract_skill_files(entity):
            if len(final_attr) == 0:
                final_attr = skill_file._prop_model.attributes
            else:
                for i in range(len(final_attr)):
                    final_attr[i] += skill_file._prop_model.attributes[i]
        return final_attr

    ######################################################################################################################################################
    def on_skill_target_agent_off_line_event(
        self, entity: Entity, target: Entity
    ) -> None:

        world_skill_system_rule_tag, world_skill_system_rule_out_come = (
            self.extract_world_skill_system_rule(entity)
        )

        self._context.broadcast_event(
            set({entity}),
            _generate_offline_prompt(
                self._context.safe_get_entity_name(entity),
                self._context.safe_get_entity_name(target),
                world_skill_system_rule_out_come,
            ),
        )

    ######################################################################################################################################################
    def create_task(self, entity: Entity, target: Entity) -> Optional[AgentTask]:

        target_agent_name = self._context.safe_get_entity_name(target)
        target_agent = self._context._langserve_agent_system.get_agent(
            target_agent_name
        )
        if target_agent is None:
            return None

        world_skill_system_rule_tag, world_skill_system_rule_out_come = (
            self.extract_world_skill_system_rule(entity)
        )
        prompt = _generate_skill_hit_feedback_prompt(
            self._context.safe_get_entity_name(entity),
            target_agent_name,
            world_skill_system_rule_out_come,
            world_skill_system_rule_tag,
        )

        return AgentTask.create(
            target_agent,
            public_builtin_prompt.replace_you(prompt, target_agent_name),
        )

    ######################################################################################################################################################
    def extract_world_skill_system_rule(self, entity: Entity) -> tuple[str, str]:
        if not entity.has(WorldSkillSystemRuleAction):
            return "", ""

        world_skill_system_rule_action = entity.get(WorldSkillSystemRuleAction)
        if len(world_skill_system_rule_action.values) < 2:
            return "", ""
        # [response_plan.result_tag, response_plan.out_come]
        return (
            world_skill_system_rule_action.values[0],
            world_skill_system_rule_action.values[1],
        )

    ######################################################################################################################################################
    def get_damage_buff(self, entity: Entity) -> float:

        world_skill_system_rule_tag, world_skill_system_rule_out_come = (
            self.extract_world_skill_system_rule(entity)
        )

        if (
            world_skill_system_rule_tag
            == public_builtin_prompt.ConstantPrompt.CRITICAL_SUCCESS
        ):
            return 1.5  # 先写死，测试的时候再改。todo

        return 1.0  # 默认的。

    ######################################################################################################################################################
