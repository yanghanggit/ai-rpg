from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity  # type: ignore
from game.rpg_game_context import RPGGameContext
from components.actions import (
    EquipPropAction,
    DeadAction,
    UpdateAppearanceAction,
)
from components.components import (
    ActorComponent,
    WeaponComponent,
    ClothesComponent,
)
from loguru import logger
from typing import final, override, Optional
from extended_systems.prop_file import PropFile
from game.rpg_game import RPGGame
from models.event_models import AgentEvent


################################################################################################################################################
def _generate_equipment_not_found_prompt(actor_name: str, prop_name: str) -> str:
    return f"""# 提示: {actor_name} 没有道具: {prop_name}。所以无法装备。"""


################################################################################################################################################
def _generate_equipment_weapon_prompt(
    actor_name: str,
    prop_file_weapon: PropFile,
    previous_prop_file_weapon: Optional[PropFile],
) -> str:
    assert prop_file_weapon.is_weapon
    if previous_prop_file_weapon is not None:
        return f"""# 发生事件: {actor_name} 装备了武器: {prop_file_weapon.name}，卸下了武器: {previous_prop_file_weapon.name}"""

    return f"""# 发生事件: {actor_name} 装备了武器: {prop_file_weapon.name}"""


################################################################################################################################################
def _generate_equipment_clothing_prompt(
    actor_name: str,
    prop_file_clothes: PropFile,
    previous_prop_file_clothes: Optional[PropFile],
) -> str:
    assert prop_file_clothes.is_clothes
    if previous_prop_file_clothes is not None:
        return f"""# 发生事件: {actor_name} 装备了衣服: {prop_file_clothes.name}，卸下了衣服: {previous_prop_file_clothes.name}"""
    return f"""# 发生事件: {actor_name} 装备了衣服: {prop_file_clothes.name}"""


################################################################################################################################################
def _generate_equipment_repeat_prompt(actor_name: str, prop_file: PropFile) -> str:
    return f"""# 提示: {actor_name} 已经装备了{prop_file.name}。
无需使用动作:{EquipPropAction.__name__}，重复装备！"""


################################################################################################################################################
################################################################################################################################################
################################################################################################################################################


@final
class EquipPropActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGGameContext, rpg_game: RPGGame):
        super().__init__(context)
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(EquipPropAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(EquipPropAction)
            and entity.has(ActorComponent)
            and not entity.has(DeadAction)
        )

    ####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:

        # 处理装备动作
        for entity in entities:
            self._process_equipment_action(entity)

        # 移除装备动作
        for entity in entities:
            assert entity.has(EquipPropAction)
            if entity.has(EquipPropAction):
                entity.remove(EquipPropAction)

    ####################################################################################################################################
    def _process_equipment_action(self, entity: Entity) -> None:

        equip_prop_action = entity.get(EquipPropAction)
        if len(equip_prop_action.values) == 0:
            return

        actor_name = self._context.safe_get_entity_name(entity)
        for equip_prop_file_name in equip_prop_action.values:

            prop_file = self._context.file_system.get_file(
                PropFile, actor_name, equip_prop_file_name
            )

            if prop_file is None:
                logger.error(
                    f"EquipPropActionSystem: {actor_name} can't find prop {equip_prop_file_name}"
                )

                self._context.notify_event(
                    set({entity}),
                    AgentEvent(
                        message=_generate_equipment_not_found_prompt(
                            actor_name, equip_prop_file_name
                        )
                    ),
                )
                continue

            need_add_update_appearance = False

            if prop_file.is_weapon:
                need_add_update_appearance = (
                    need_add_update_appearance
                    or self._apply_weapon_equipment(entity, prop_file)
                )

            elif prop_file.is_clothes:
                need_add_update_appearance = (
                    need_add_update_appearance
                    or self._apply_clothing_equipment(entity, prop_file)
                )

            else:
                logger.error(
                    f"EquipPropActionSystem: {actor_name} can't equip prop {equip_prop_file_name}"
                )

            # 添加更新外观的action
            if need_add_update_appearance:
                self._add_update_appearance_action(entity)

    ####################################################################################################################################
    def _apply_weapon_equipment(
        self, entity: Entity, weapon_prop_file_to_equip: PropFile
    ) -> bool:

        assert weapon_prop_file_to_equip.is_weapon

        previous_prop_file_weapon: Optional[PropFile] = None
        if entity.has(WeaponComponent):
            weapon_component = entity.get(WeaponComponent)
            previous_prop_file_weapon = self._context.file_system.get_file(
                PropFile, weapon_component.name, weapon_component.prop_name
            )
            assert previous_prop_file_weapon is not None
            if previous_prop_file_weapon.name == weapon_prop_file_to_equip.name:
                self._context.notify_event(
                    set({entity}),
                    AgentEvent(
                        message=_generate_equipment_repeat_prompt(
                            self._context.safe_get_entity_name(entity),
                            weapon_prop_file_to_equip,
                        )
                    ),
                )
                return False

        # 替换武器
        entity.replace(
            WeaponComponent,
            weapon_prop_file_to_equip.owner_name,
            weapon_prop_file_to_equip.name,
        )

        # 通知事件
        self._context.notify_event(
            set({entity}),
            AgentEvent(
                message=_generate_equipment_weapon_prompt(
                    weapon_prop_file_to_equip.owner_name,
                    weapon_prop_file_to_equip,
                    previous_prop_file_weapon,
                )
            ),
        )

        return True

    ####################################################################################################################################
    def _apply_clothing_equipment(
        self, entity: Entity, clothes_prop_file_to_equip: PropFile
    ) -> bool:

        assert clothes_prop_file_to_equip.is_clothes

        previous_prop_file_clothes: Optional[PropFile] = None
        if entity.has(ClothesComponent):
            clothes_component = entity.get(ClothesComponent)
            previous_prop_file_clothes = self._context.file_system.get_file(
                PropFile, clothes_component.name, clothes_component.prop_name
            )
            assert previous_prop_file_clothes is not None
            if previous_prop_file_clothes.name == clothes_prop_file_to_equip.name:
                self._context.notify_event(
                    set({entity}),
                    AgentEvent(
                        message=_generate_equipment_repeat_prompt(
                            self._context.safe_get_entity_name(entity),
                            clothes_prop_file_to_equip,
                        )
                    ),
                )
                return False

        # 替换衣服
        entity.replace(
            ClothesComponent,
            clothes_prop_file_to_equip.owner_name,
            clothes_prop_file_to_equip.name,
        )

        # 通知事件
        self._context.notify_event(
            set({entity}),
            AgentEvent(
                message=_generate_equipment_clothing_prompt(
                    clothes_prop_file_to_equip.owner_name,
                    clothes_prop_file_to_equip,
                    previous_prop_file_clothes,
                )
            ),
        )

        return True

    ####################################################################################################################################
    def _add_update_appearance_action(self, entity: Entity) -> None:
        entity.replace(
            UpdateAppearanceAction,
            self._context.safe_get_entity_name(entity),
            [],
        )

    ####################################################################################################################################
