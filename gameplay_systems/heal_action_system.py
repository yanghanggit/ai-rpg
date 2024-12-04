from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from components.actions import HealAction
from components.components import (
    AttributesComponent,
    ActorComponent,
    StageComponent,
)
from game.rpg_game_context import RPGGameContext
from typing import final, override
import format_string.target_message
import format_string.ints_string
from game.rpg_game import RPGGame
from models.entity_models import Attributes
from models.event_models import AgentEvent
from loguru import logger


# ################################################################################################################################################
def _generate_heal_event_description_prompt1(
    source_name: str,
    target_name: str,
    applied_heal: int,
) -> str:
    return f"""# 发生事件: {source_name} 对 {target_name} 的行动，治疗了 {applied_heal} 生命值。"""


# ################################################################################################################################################
def _generate_heal_event_description_prompt2(
    source_name: str,
    target_name: str,
    applied_heal: int,
    remaining_hp: int,
    max_hp: int,
) -> str:
    return f"""# 发生事件: {source_name} 对 {target_name} 的行动，治疗了 {applied_heal} 生命值。
{target_name} 的生命值变为 {remaining_hp}/{max_hp}。"""


################################################################################################################################################
################################################################################################################################################
################################################################################################################################################


@final
class HealActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game

    ######################################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(HealAction): GroupEvent.ADDED}

    ######################################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(HealAction)
            and entity.has(AttributesComponent)
            and (entity.has(StageComponent) or entity.has(ActorComponent))
        )

    ######################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_heal_action(entity)

    ######################################################################################################################################################
    def _process_heal_action(self, target_entity: Entity) -> None:

        heal_action = target_entity.get(HealAction)
        if len(heal_action.values) == 0:
            return

        for (
            source_entity_name,
            attribute_values_string,
        ) in format_string.target_message.extract_target_message_pairs(
            heal_action.values
        ):
            attribute_values = format_string.ints_string.convert_string_to_ints(
                attribute_values_string
            )

            assert (
                len(attribute_values) > Attributes.HEAL
            ), f"属性数组长度不够:{attribute_values}"

            self._apply_heal_to_target(
                source_entity_name,
                target_entity,
                attribute_values[Attributes.HEAL],
            )

    ######################################################################################################################################################
    def _apply_heal_to_target(
        self, source_entity_name: str, target_entity: Entity, applied_heal: int
    ) -> None:
        # 目标拿出来
        target_attr_comp = target_entity.get(AttributesComponent)

        cur_hp = target_attr_comp.cur_hp
        cur_hp += applied_heal
        cur_hp = max(0, min(cur_hp, target_attr_comp.max_hp))

        # 结果修改
        target_entity.replace(
            AttributesComponent,
            target_attr_comp.name,
            target_attr_comp.max_hp,
            cur_hp,
            target_attr_comp.damage,
            target_attr_comp.defense,
            target_attr_comp.heal,
        )

        ## 导演系统，单独处理，有旧的代码
        self._notify_heal_outcome(
            source_entity_name=source_entity_name,
            target_entity=target_entity,
            applied_heal=applied_heal,
        )

    ######################################################################################################################################################
    def _notify_heal_outcome(
        self,
        source_entity_name: str,
        target_entity: Entity,
        applied_heal: int,
    ) -> None:

        current_stage_entity = self._context.safe_get_stage_entity(target_entity)
        assert current_stage_entity is not None
        if current_stage_entity is None:
            return

        target_name = self._context.safe_get_entity_name(target_entity)
        if target_entity.has(StageComponent):
            logger.error(f"目标是场景，不应该有治疗行为:{target_name}")
            return

        # 通知其他人，数据相对简单
        self._context.broadcast_event(
            current_stage_entity,
            AgentEvent(
                message=_generate_heal_event_description_prompt1(
                    source_name=source_entity_name,
                    target_name=target_name,
                    applied_heal=applied_heal,
                )
            ),
            set([target_entity]),
        )

        # 通知自己，数据相对全面
        attr_comp = target_entity.get(AttributesComponent)
        self._context.notify_event(
            set([target_entity]),
            AgentEvent(
                message=_generate_heal_event_description_prompt2(
                    source_name=source_entity_name,
                    target_name=target_name,
                    applied_heal=applied_heal,
                    remaining_hp=attr_comp.cur_hp,
                    max_hp=attr_comp.max_hp,
                )
            ),
        )


######################################################################################################################################################
