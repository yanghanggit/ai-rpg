from dataclasses import dataclass
from entitas import Matcher, ExecuteProcessor, Entity  # type: ignore
from components.actions import (
    DamageAction,
    HealAction,
)
from components.components import (
    AttributesComponent,
    DestroyFlagComponent,
    SkillComponent,
)
from game.rpg_game_context import RPGGameContext
from typing import final, override, List, Optional, Set
import rpg_game_systems.prompt_utils
import format_string.target_message
import format_string.ints_string
from game.rpg_game import RPGGame
from rpg_models.entity_models import Attributes
from rpg_models.event_models import AgentEvent
import rpg_game_systems.skill_entity_utils
import rpg_game_systems.action_component_utils


################################################################################################################################################
def _generate_notify_skill_hit_prompt(
    actor_name: str, target_name: str, inspector_content: str, inspector_tag: str
) -> str:

    return f"""# 发生事件: {actor_name} 向 {target_name} 使用技能。
## 技能事件描述
{inspector_content}
## 系统判断结果
{inspector_tag}"""


################################################################################################################################################
def _generate_broadcast_skill_event_prompt(
    source_name: str,
    target_name: str,
    inspector_content: str,
) -> str:
    return f"""# 发生事件: {source_name} 向 {target_name} 使用技能。
## 事件描述
{inspector_content}"""


################################################################################################################################################
@dataclass
class InternalProcessData:
    source_entity: Entity
    skill_entity: Entity
    target_entities: List[Entity]


################################################################################################################################################


@final
class SkillHitImpactSystem(ExecuteProcessor):

    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game

    ######################################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    ######################################################################################################################################################
    @override
    async def a_execute1(self) -> None:

        skill_entities = self._context.get_group(
            Matcher(all_of=[SkillComponent], none_of=[DestroyFlagComponent])
        ).entities.copy()

        internal_process_data_list = self._initialize_internal_process_data_list(
            skill_entities
        )
        for internal_process_data in internal_process_data_list:
            self._notify_skill_hit(internal_process_data)
            self._process_skill_impact(internal_process_data)

    ######################################################################################################################################################
    def _notify_skill_hit(self, internal_process_data: InternalProcessData) -> None:

        for data_index in range(len(internal_process_data.target_entities)):

            target_entity = internal_process_data.target_entities[data_index]

            target_name = self._context.safe_get_entity_name(target_entity)
            skill_comp = internal_process_data.skill_entity.get(SkillComponent)

            prompt = _generate_notify_skill_hit_prompt(
                actor_name=self._context.safe_get_entity_name(
                    internal_process_data.source_entity
                ),
                target_name=target_name,
                inspector_content=skill_comp.inspector_content,
                inspector_tag=skill_comp.inspector_tag,
            )

            self._context.notify_event(
                set({target_entity}),
                AgentEvent(message=prompt),
            )

    ######################################################################################################################################################
    def _initialize_internal_process_data_list(
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
        assert (
            len(skill_comp.targets) > 0
        ), f"skill_comp.targets {skill_comp.targets} not found."
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
        )

        for target_name in skill_comp.targets:

            target_entity = self._context.get_entity_by_name(target_name)
            assert target_entity is not None, f"target_entity {target_name} not found."
            if target_entity is None:
                continue
            # 目标
            ret.target_entities.append(target_entity)

        # 最后的检查，出问题了就返回None
        if len(ret.target_entities) == 0:
            return None

        return ret

    ######################################################################################################################################################
    def _process_skill_impact(self, internal_process_data: InternalProcessData) -> None:

        # 然后处理返回结果
        for data_index in range(len(internal_process_data.target_entities)):
            # 开始处理计算！！！！！！！！！！！！！！！！！！
            self._evaluate_and_apply_action(
                internal_process_data,
                target_entity=internal_process_data.target_entities[data_index],
            )

            # 通知技能的影响结果
            self._broadcast_skill_event(
                internal_process_data,
                target_entity=internal_process_data.target_entities[data_index],
            )

    ######################################################################################################################################################
    def _broadcast_skill_event(
        self,
        internal_process_data: InternalProcessData,
        target_entity: Entity,
    ) -> None:

        current_stage_entity = self._context.safe_get_stage_entity(
            internal_process_data.source_entity
        )
        if current_stage_entity is None:
            return

        self._context.broadcast_event(
            current_stage_entity,
            AgentEvent(
                message=_generate_broadcast_skill_event_prompt(
                    source_name=self._context.safe_get_entity_name(
                        internal_process_data.source_entity
                    ),
                    target_name=self._context.safe_get_entity_name(target_entity),
                    inspector_content=internal_process_data.skill_entity.get(
                        SkillComponent
                    ).inspector_content,
                )
            ),
            set({target_entity}),  # 已经参与的双方不需要再被通知了。
        )

    ######################################################################################################################################################
    def _evaluate_and_apply_action(
        self,
        internal_process_data: InternalProcessData,
        target_entity: Entity,
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
        self._compute_entity_attributes(internal_process_data, total_skill_attributes)

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

        total_skill_attributes[Attributes.HEAL] = int(
            total_skill_attributes[Attributes.HEAL] * calculate_bonus
        )
        if total_skill_attributes[Attributes.HEAL] == 0:
            return

        #
        formatted_heal_message = (
            format_string.target_message.generate_target_message_pair(
                self._context.safe_get_entity_name(source_entity),
                format_string.ints_string.convert_ints_to_string(
                    total_skill_attributes
                ),
            )
        )

        if not target_entity.has(HealAction):
            target_entity.replace(
                HealAction,
                self._context.safe_get_entity_name(target_entity),
                [formatted_heal_message],
            )
        else:

            heal_action = target_entity.get(HealAction)
            heal_action.values.append(formatted_heal_message)
            target_entity.replace(HealAction, heal_action.name, heal_action.values)

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
            format_string.target_message.generate_target_message_pair(
                self._context.safe_get_entity_name(source_entity),
                format_string.ints_string.convert_ints_to_string(
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
        internal_process_data: InternalProcessData,
        skill_attribute_output: List[int],
    ) -> None:

        if not internal_process_data.source_entity.has(AttributesComponent):
            return
        attr_comp = internal_process_data.source_entity.get(AttributesComponent)
        assert (
            len(internal_process_data.target_entities) > 0
        ), f"target_entities {internal_process_data.target_entities} not found."

        # 不能同时存在。
        assert (
            skill_attribute_output[Attributes.DAMAGE]
            * skill_attribute_output[Attributes.HEAL]
            == 0
        )

        # 均摊到每个属性上 todo
        if skill_attribute_output[Attributes.DAMAGE] != 0:
            skill_attribute_output[Attributes.DAMAGE] += int(
                attr_comp.damage / len(internal_process_data.target_entities)
            )

        if skill_attribute_output[Attributes.HEAL] != 0:
            skill_attribute_output[Attributes.HEAL] += int(
                attr_comp.heal / len(internal_process_data.target_entities)
            )

    ######################################################################################################################################################
    def _compute_skill_accessory_attributes(
        self,
        internal_process_data: InternalProcessData,
        target_entity: Entity,
        skill_attribute_outputs: List[int],
    ) -> None:

        if len(skill_attribute_outputs) == 0:
            return

        data = rpg_game_systems.skill_entity_utils.parse_skill_accessory_prop_files(
            context=self._context,
            skill_entity=internal_process_data.skill_entity,
            actor_entity=internal_process_data.source_entity,
        )

        for prop_file_with_count in data:
            for attr_index in range(len(skill_attribute_outputs)):
                prop_file = prop_file_with_count[0]
                cunsume_count = prop_file_with_count[1]
                assert cunsume_count >= 1, f"cunsume_count {cunsume_count} not found."
                assert (
                    len(internal_process_data.target_entities) > 0
                ), f"internal_process_data {internal_process_data.target_entities} not found."

                if prop_file.prop_model.attributes[attr_index] == 0:
                    # 没有属性就不需要计算了
                    continue

                # 均摊到每个属性上 todo
                attr_value = (
                    prop_file.prop_model.attributes[attr_index]
                    * cunsume_count
                    / len(internal_process_data.target_entities)
                )
                skill_attribute_outputs[attr_index] += int(attr_value)

    ######################################################################################################################################################
    def _summarize_skill_attributes(
        self, internal_process_data: InternalProcessData
    ) -> List[int]:

        skill_prop_files = rpg_game_systems.skill_entity_utils.parse_skill_prop_files(
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
    def _calculate_bonus(
        self,
        internal_process_data: InternalProcessData,
        reference_value: int = Attributes.BASE_VALUE_SCALE,
    ) -> float:
        assert reference_value > 0, f"reference_value {reference_value} not found."
        skill_comp = internal_process_data.skill_entity.get(SkillComponent)
        value = skill_comp.inspector_value / reference_value
        if value < 0:
            value = 0

        return value

    ######################################################################################################################################################
