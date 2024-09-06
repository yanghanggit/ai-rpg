from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from gameplay_systems.action_components import (
    BehaviorAction,
    SkillTargetAction,
    SkillAction,
    SkillUsePropAction,
    DamageAction,
    WorldSkillSystemRuleAction,
    BroadcastAction,
)
from gameplay_systems.components import (
    BodyComponent,
    RPGAttributesComponent,
    ActorComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import override, List, cast, Optional, Set
from loguru import logger
from extended_systems.files_def import PropFile
import gameplay_systems.cn_builtin_prompt as builtin_prompt
from my_agent.agent_task import AgentTask
from my_agent.agent_plan_and_action import AgentPlan
import my_format_string.target_and_message_format_string
import my_format_string.attrs_format_string
from rpg_game.rpg_game import RPGGame
from my_data.model_def import AttributesIndex


class SkillFeedbackAgentPlan(AgentPlan):

    @property
    def feedback(self) -> str:
        broadcast_action = self.get_by_key(BroadcastAction.__name__)
        if broadcast_action is None or len(broadcast_action.values) == 0:
            return ""
        return " ".join(broadcast_action.values)


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
            and entity.has(ActorComponent)
        )

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

            response_plan = self.handle_task(task)
            if response_plan is None:
                self.on_skill_target_agent_off_line_event(entity, target)
                continue

            # 加入伤害计算的逻辑
            self.calculate_and_add_action(entity, target)

            # 场景事件
            self.on_notify_others_of_skill_event(entity, target, response_plan.feedback)

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

    def on_notify_others_of_skill_event(
        self, from_entity: Entity, target_entity: Entity, target_feedback: str
    ) -> None:

        current_stage_entity = self._context.safe_get_stage_entity(from_entity)
        if current_stage_entity is None:
            return

        world_skill_system_rule_tag, world_skill_system_rule_out_come = (
            self.extract_world_skill_system_rule(from_entity)
        )

        self._context.broadcast_entities_in_stage(
            current_stage_entity,
            builtin_prompt.make_notify_others_in_stage_of_skill_event_prompt(
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
        self.add_damage(entity, target, calculate_attrs)

    ######################################################################################################################################################
    def add_damage(
        self, entity: Entity, target: Entity, skill_attrs: List[int]
    ) -> None:
        if skill_attrs[AttributesIndex.DAMAGE.value] == 0:
            return

        if not target.has(DamageAction):
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

        self._context.broadcast_entities(
            set({entity}),
            builtin_prompt.make_target_agent_off_line_prompt(
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
        prompt = builtin_prompt.make_skill_hit_feedback_prompt(
            self._context.safe_get_entity_name(entity),
            target_agent_name,
            world_skill_system_rule_out_come,
            world_skill_system_rule_tag,
        )

        return AgentTask.create(
            target_agent,
            builtin_prompt.replace_you(prompt, target_agent_name),
        )

    ######################################################################################################################################################
    def handle_task(self, task: AgentTask) -> Optional[SkillFeedbackAgentPlan]:

        response = task.request()
        if response is None:
            return None

        return SkillFeedbackAgentPlan(task._agent._name, response)

    ######################################################################################################################################################
    def extract_world_skill_system_rule(self, entity: Entity) -> tuple[str, str]:
        if not entity.has(WorldSkillSystemRuleAction):
            return "", ""

        world_skill_system_rule_action = entity.get(WorldSkillSystemRuleAction)
        if len(world_skill_system_rule_action.values) < 2:
            return "", ""
        # [response_plan.result_tag, response_plan.out_come]
        return cast(str, world_skill_system_rule_action.values[0]), cast(
            str, world_skill_system_rule_action.values[1]
        )

    ######################################################################################################################################################
