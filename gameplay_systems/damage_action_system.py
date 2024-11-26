from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from my_components.action_components import DamageAction, DeadAction
from my_components.components import (
    AttributesComponent,
    ClothesComponent,
    ActorComponent,
    StageComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import final, override
from extended_systems.prop_file import PropFile
import my_format_string.target_message
import my_format_string.ints_string
from rpg_game.rpg_game import RPGGame
from my_models.entity_models import Attributes
import gameplay_systems.file_system_utils
from my_models.file_models import PropType
from my_models.event_models import AgentEvent
from loguru import logger


################################################################################################################################################
def _generate_kill_notification_prompt(
    source_name: str, target_name: str, effective_damage: int
) -> str:
    return f"""# 发生事件: {source_name} 对 {target_name} 的行动造成了 {target_name} 死亡。
{target_name} 受到了 {effective_damage} 伤害。"""


################################################################################################################################################
def _generate_damage_event_description_prompt1(
    source_name: str,
    target_name: str,
    effective_damage: int,
) -> str:
    return f"# 发生事件: {source_name} 对 {target_name} 的行动造成了 {effective_damage} 伤害。"


################################################################################################################################################
def _generate_damage_event_description_prompt2(
    source_name: str,
    target_name: str,
    effective_damage: int,
    applied_damage: int,
    remaining_hp: int,
    max_hp: int,
) -> str:
    defense = applied_damage - effective_damage
    defense = max(0, defense)
    return f"""# 发生事件: {source_name} 对 {target_name} 的行动，最终造成了 {effective_damage} 伤害。
防御抵消(自身防御力和衣服提供的防御力) {defense} 伤害.
剩余生命值 {remaining_hp}/{max_hp}。"""


################################################################################################################################################
################################################################################################################################################
################################################################################################################################################


@final
class DamageActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ######################################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(DamageAction): GroupEvent.ADDED}

    ######################################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(DamageAction)
            and entity.has(AttributesComponent)
            and (entity.has(StageComponent) or entity.has(ActorComponent))
        )

    ######################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_damage_action(entity)

    ######################################################################################################################################################
    def _process_damage_action(self, target_entity: Entity) -> None:

        damage_action = target_entity.get(DamageAction)
        if len(damage_action.values) == 0:
            return

        for (
            source_entity_name,
            attribute_values_string,
        ) in my_format_string.target_message.extract_target_message_pairs(
            damage_action.values
        ):
            attribute_values = my_format_string.ints_string.convert_string_to_ints(
                attribute_values_string
            )

            assert (
                len(attribute_values) > Attributes.DAMAGE
            ), f"属性数组长度不够:{attribute_values}"

            self._apply_damage_to_target(
                source_entity_name,
                target_entity,
                attribute_values[Attributes.DAMAGE],
            )

    ######################################################################################################################################################
    def _apply_damage_to_target(
        self, source_entity_name: str, target_entity: Entity, applied_damage: int
    ) -> None:
        # 目标拿出来
        target_attr_comp = target_entity.get(AttributesComponent)

        # 简单的战斗计算，简单的血减掉伤害
        current_health = target_attr_comp.cur_hp

        # 必须控制在0和最大值之间
        effective_damage = applied_damage - self._compute_entity_defense(target_entity)
        if effective_damage < 0:
            effective_damage = 0

        remaining_health = current_health - effective_damage
        remaining_health = max(0, min(remaining_health, target_attr_comp.max_hp))

        # 结果修改
        target_entity.replace(
            AttributesComponent,
            target_attr_comp.name,
            target_attr_comp.max_hp,
            remaining_health,
            target_attr_comp.damage,
            target_attr_comp.defense,
            target_attr_comp.heal,
        )

        ##死亡是关键
        is_dead = remaining_health <= 0

        ## 死后处理大流程，step最后——死亡组件系统必须要添加
        if is_dead:
            target_entity.replace(
                DeadAction,
                self._context.safe_get_entity_name(target_entity),
                [],
            )

            # 死亡夺取
            self._reward_on_death(source_entity_name, target_entity)

        ## 导演系统，单独处理，有旧的代码
        self._notify_damage_outcome(
            source_entity_name=source_entity_name,
            target_entity=target_entity,
            applied_damage=applied_damage,
            effective_damage=effective_damage,
            is_dead=is_dead,
        )

    ######################################################################################################################################################
    def _notify_damage_outcome(
        self,
        source_entity_name: str,
        target_entity: Entity,
        effective_damage: int,
        applied_damage: int,
        is_dead: bool,
    ) -> None:
        pass

        current_stage_entity = self._context.safe_get_stage_entity(target_entity)
        assert current_stage_entity is not None
        if current_stage_entity is None:
            return

        target_name = self._context.safe_get_entity_name(target_entity)
        if is_dead:
            # 直接打死。
            self._context.broadcast_event(
                current_stage_entity,
                AgentEvent(
                    message=_generate_kill_notification_prompt(
                        source_name=source_entity_name,
                        target_name=target_name,
                        effective_damage=effective_damage,
                    )
                ),
            )
            return

        if target_entity.has(StageComponent):
            logger.warning(f"场景{target_name}受到了伤害，但是不会死亡。不需要通知了")
            return

        # 通知其他人，数据相对简单
        self._context.broadcast_event(
            current_stage_entity,
            AgentEvent(
                message=_generate_damage_event_description_prompt1(
                    source_entity_name,
                    target_name,
                    effective_damage,
                )
            ),
            set([target_entity]),
        )

        # 通知自己，数据相对全面
        attr_comp = target_entity.get(AttributesComponent)
        self._context.notify_event(
            set([target_entity]),
            AgentEvent(
                message=_generate_damage_event_description_prompt2(
                    source_name=source_entity_name,
                    target_name=target_name,
                    effective_damage=effective_damage,
                    applied_damage=applied_damage,
                    remaining_hp=attr_comp.cur_hp,
                    max_hp=attr_comp.max_hp,
                )
            ),
        )

    ######################################################################################################################################################
    # todo
    def _reward_on_death(self, source_entity_name: str, target_entity: Entity) -> None:

        logger.warning(
            f"_reward_on_death {source_entity_name}击败了{self._context.safe_get_entity_name(target_entity)}"
        )

        target_entity_name = self._context.safe_get_entity_name(target_entity)
        categorized_prop_files = (
            gameplay_systems.file_system_utils.categorize_files_by_type(
                self._context.file_system, target_entity_name
            )
        )

        for prop_file in categorized_prop_files[PropType.TYPE_NON_CONSUMABLE_ITEM]:
            gameplay_systems.file_system_utils.transfer_file(
                self._context.file_system,
                target_entity_name,
                source_entity_name,
                prop_file.name,
                prop_file.count,
            )

    ######################################################################################################################################################
    def _compute_entity_defense(self, entity: Entity) -> int:
        # 输出的防御力
        total_defense: int = 0

        # 基础防御力
        attr_comp = entity.get(AttributesComponent)
        total_defense += attr_comp.defense

        # 计算衣服带来的防御力
        if entity.has(ClothesComponent):
            clothes_comp = entity.get(ClothesComponent)
            current_clothe_prop_file = self._context.file_system.get_file(
                PropFile, clothes_comp.name, clothes_comp.propname
            )
            assert current_clothe_prop_file is not None
            if current_clothe_prop_file is not None:
                total_defense += current_clothe_prop_file.defense

        return total_defense


######################################################################################################################################################
