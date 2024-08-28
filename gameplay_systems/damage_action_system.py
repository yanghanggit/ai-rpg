from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from gameplay_systems.action_components import DamageAction, DeadAction
from gameplay_systems.components import (
    RPGAttributesComponent,
    RPGCurrentClothesComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import cast, override
import gameplay_systems.cn_builtin_prompt as builtin_prompt
from file_system.files_def import PropFile
import my_format_string.target_and_message_format_string
import my_format_string.attrs_format_string
from rpg_game.rpg_game import RPGGame
from build_game.data_model import AttributesIndex


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
        return entity.has(DamageAction) and entity.has(RPGAttributesComponent)

    ######################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.handle(entity)

    ######################################################################################################################################################
    def handle(self, target_entity: Entity) -> None:

        damage_action = target_entity.get(DamageAction)
        if len(damage_action.values) == 0:
            return

        for val in damage_action.values:
            target_and_message = my_format_string.target_and_message_format_string.parse_target_and_message(
                cast(str, val)
            )
            if target_and_message[0] is None or target_and_message[1] is None:
                continue

            from_name = target_and_message[0]
            find_entity = self._context.get_entity_by_name(from_name)
            if find_entity is None:
                assert find_entity is not None, f"找不到实体:{from_name}"
                continue

            attrs_array = my_format_string.attrs_format_string.from_string_to_int_attrs(
                target_and_message[1]
            )
            assert len(attrs_array) > AttributesIndex.ATTACK.value, f"属性数组长度不够:{attrs_array}"
            if len(attrs_array) > AttributesIndex.ATTACK.value:
                self.handle_target_damage(from_name, target_entity, attrs_array[AttributesIndex.ATTACK.value])

    ######################################################################################################################################################
    def handle_target_damage(
        self, from_name: str, target_entity: Entity, input_damage: int
    ) -> None:
        # 目标拿出来
        target_rpg_comp = target_entity.get(RPGAttributesComponent)

        # 简单的战斗计算，简单的血减掉伤害
        hp = target_rpg_comp.hp

        # 必须控制在0和最大值之间
        final_damage = input_damage - self.final_defense_val(target_entity)
        if final_damage < 0:
            final_damage = 0

        left_hp = hp - final_damage
        left_hp = max(0, min(left_hp, target_rpg_comp.maxhp))

        # 结果修改
        target_entity.replace(
            RPGAttributesComponent,
            target_rpg_comp.name,
            target_rpg_comp.maxhp,
            left_hp,
            target_rpg_comp.attack,
            target_rpg_comp.defense,
        )

        ##死亡是关键
        is_dead = (left_hp <= 0)

        ## 死后处理大流程，step最后——死亡组件系统必须要添加
        if is_dead:

            if not target_entity.has(DeadAction):
                # 复制一个，不用以前的，怕GC不掉
                target_entity.add(
                    DeadAction,
                    self._context.safe_get_entity_name(target_entity),
                    DeadAction.__name__,
                    [],
                )

        ## 导演系统，单独处理，有旧的代码
        self.on_damage_event(from_name, target_entity, final_damage, is_dead)

    ######################################################################################################################################################
    def on_damage_event(
        self, from_name: str, target_entity: Entity, damage: int, is_dead: bool
    ) -> None:
        pass

        current_stage_entity = self._context.safe_get_stage_entity(target_entity)
        assert current_stage_entity is not None
        if current_stage_entity is None:
            return

        target_name = self._context.safe_get_entity_name(target_entity)
        if is_dead:
            # 直接打死。
            self._context.add_agent_context_message(
                set({current_stage_entity}),
                builtin_prompt.make_kill_prompt(from_name, target_name),
            )

        else:
            # 没有打死。
            rpg_attr_comp = target_entity.get(RPGAttributesComponent)
            self._context.add_agent_context_message(
                set({current_stage_entity}),
                builtin_prompt.make_damage_event_prompt(
                    from_name,
                    target_name,
                    damage,
                    rpg_attr_comp.hp,
                    rpg_attr_comp.maxhp,
                ),
            )

    ######################################################################################################################################################
    def final_defense_val(self, entity: Entity) -> int:
        # 输出的防御力
        final: int = 0

        # 基础防御力
        rpg_attr_comp = entity.get(RPGAttributesComponent)
        final += cast(int, rpg_attr_comp.defense)

        # 计算衣服带来的防御力
        if entity.has(RPGCurrentClothesComponent):

            clothes_comp = entity.get(RPGCurrentClothesComponent)

            current_clothe_prop_file = self._context._file_system.get_file(
                PropFile, clothes_comp.name, clothes_comp.propname
            )
            assert current_clothe_prop_file is not None
            if current_clothe_prop_file is not None:
                final += current_clothe_prop_file.defense

        return final


######################################################################################################################################################
