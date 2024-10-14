from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from gameplay_systems.action_components import (
    StealPropAction,
    DeadAction,
)
from gameplay_systems.components import (
    ActorComponent,
    RPGCurrentWeaponComponent,
    RPGCurrentClothesComponent,
)
import gameplay_systems.conversation_helper
from typing import override
import extended_systems.file_system_helper
from extended_systems.files_def import PropFile
import my_format_string.target_and_message_format_string
from rpg_game.rpg_game import RPGGame
from loguru import logger

####################################################################################################################################


def _generate_steal_prompt(
    from_name: str, target_name: str, prop_name: str, action_result: bool
) -> str:
    if not action_result:
        return f"# {from_name} 试图从 {target_name} 盗取 {prop_name}, 但是失败了。"
    return f"""# {from_name} 从 {target_name} 成功盗取了 {prop_name}。
# 导致结果
- {target_name} 现在不再拥有 {prop_name}。
- {from_name} 现在拥有了 {prop_name}。"""


####################################################################################################################################


class StealActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame):
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(StealPropAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(StealPropAction)
            and entity.has(ActorComponent)
            and not entity.has(DeadAction)
        )

    ####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.handle(entity)

    ####################################################################################################################################
    def handle(self, entity: Entity) -> None:

        steal_action: StealPropAction = entity.get(StealPropAction)
        target_and_message = (
            my_format_string.target_and_message_format_string.target_and_message_values(
                steal_action.values
            )
        )

        for tp in target_and_message:

            if (
                gameplay_systems.conversation_helper.validate_conversation(
                    self._context, entity, tp[0]
                )
                != gameplay_systems.conversation_helper.ConversationError.VALID
            ):
                # 不能交谈就是不能偷
                continue

            target_entity = self._context.get_entity_by_name(tp[0])
            if target_entity is None:
                continue

            action_result = self.do_steal(entity, target_entity, tp[1])
            self._context.broadcast_event(
                set({entity, target_entity}),
                _generate_steal_prompt(
                    self._context.safe_get_entity_name(entity),
                    tp[0],
                    tp[1],
                    action_result,
                ),
            )

    ####################################################################################################################################
    def do_steal(
        self, entity: Entity, target_entity: Entity, target_prop_name: str
    ) -> bool:

        target_actor_name = self._context.safe_get_entity_name(target_entity)
        prop_file = self._context._file_system.get_file(
            PropFile, target_actor_name, target_prop_name
        )

        if prop_file is None:
            logger.info(
                f"steal prop {target_prop_name} from {target_actor_name} failed"
            )
            return False

        if not self.can_be_stolen(target_entity, prop_file):
            return False

        extended_systems.file_system_helper.give_prop_file(
            self._context._file_system,
            target_actor_name,
            self._context.safe_get_entity_name(entity),
            target_prop_name,
        )

        return True

    ####################################################################################################################################
    def can_be_stolen(self, target_entity: Entity, prop_file: PropFile) -> bool:

        if not prop_file.can_exchange:
            return False

        if target_entity.has(RPGCurrentWeaponComponent):
            current_weapon_comp = target_entity.get(RPGCurrentWeaponComponent)
            if current_weapon_comp.propname == prop_file.name:
                return False

        if target_entity.has(RPGCurrentClothesComponent):
            current_armor_comp = target_entity.get(RPGCurrentClothesComponent)
            if current_armor_comp.propname == prop_file.name:
                return False

        return True


####################################################################################################################################
