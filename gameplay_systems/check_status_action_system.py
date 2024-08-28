from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from gameplay_systems.action_components import CheckStatusAction, DeadAction
from gameplay_systems.components import RPGAttributesComponent, ActorComponent
from typing import List, override
from file_system.files_def import PropFile
import gameplay_systems.cn_builtin_prompt as builtin_prompt
from rpg_game.rpg_game import RPGGame


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class CheckStatusActionHelper:

    def __init__(self, context: RPGEntitasContext):

        self._context: RPGEntitasContext = context
        self._prop_files_as_weapon_clothes_non_consumable_item: List[PropFile] = []
        self._maxhp: int = 0
        self._hp: int = 0
        self._prop_files_as_special: List[PropFile] = []

    def clear(self) -> None:
        self._prop_files_as_weapon_clothes_non_consumable_item.clear()
        self._maxhp = 0
        self._hp = 0
        self._prop_files_as_special.clear()

    def check_props(self, entity: Entity) -> None:
        safe_name = self._context.safe_get_entity_name(entity)
        prop_files = self._context._file_system.get_files(PropFile, safe_name)
        for prop_file in prop_files:
            if (
                prop_file.is_weapon
                or prop_file.is_clothes
                or prop_file.is_non_consumable_item
            ):
                self._prop_files_as_weapon_clothes_non_consumable_item.append(prop_file)
            elif prop_file.is_special:
                self._prop_files_as_special.append(prop_file)

    def check_health(self, entity: Entity) -> None:
        if not entity.has(RPGAttributesComponent):
            return
        rpg_attr_comp = entity.get(RPGAttributesComponent)
        self._maxhp = rpg_attr_comp.maxhp
        self._hp = rpg_attr_comp.hp

    def check_status(self, entity: Entity) -> None:
        # 先清空
        self.clear()
        # 检查道具
        self.check_props(entity)
        # 检查生命值
        self.check_health(entity)

    @property
    def health(self) -> float:
        return self._hp / self._maxhp


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class CheckStatusActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame):
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(CheckStatusAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(CheckStatusAction)
            and entity.has(ActorComponent)
            and not entity.has(DeadAction)
        )

    ####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.check_status(entity)

    ####################################################################################################################################
    # 临时写成这样，就是检查自己有哪些道具
    def check_status(self, entity: Entity) -> None:
        safe_name = self._context.safe_get_entity_name(entity)
        #
        helper = CheckStatusActionHelper(self._context)
        helper.check_status(entity)

        # 只有自己
        self._context.add_agent_context_message(
            set({entity}),
            builtin_prompt.make_check_status_action_prompt(
                safe_name,
                helper._prop_files_as_weapon_clothes_non_consumable_item,
                helper.health,
                helper._prop_files_as_special,
            ),
        )


####################################################################################################################################
