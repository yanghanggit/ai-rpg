from entitas import Entity  # type: ignore
from game.rpg_game_context import RPGGameContext
from typing import List
from loguru import logger
from extended_systems.prop_file import PropFile
import format_string.complex_prop_name
from components.components import ActorComponent, SkillComponent, DestroyComponent


################################################################################################################################################
def parse_skill_accessory_prop_files(
    context: RPGGameContext, skill_entity: Entity, actor_entity: Entity
) -> List[tuple[PropFile, int]]:

    assert skill_entity.has(SkillComponent)
    assert actor_entity.has(ActorComponent)
    if not skill_entity.has(SkillComponent) or not actor_entity.has(ActorComponent):
        return []

    skill_comp = skill_entity.get(SkillComponent)
    actor_comp = actor_entity.get(ActorComponent)
    assert skill_comp.name == actor_comp.name
    if skill_comp.name != actor_comp.name:
        return []

    #
    ret: List[tuple[PropFile, int]] = []
    for complex_prop_name in skill_comp.skill_accessory_props:

        if not format_string.complex_prop_name.is_complex_prop_name(complex_prop_name):
            logger.error(f"Invalid prop name and count format: {complex_prop_name}")
            continue

        prop_name, consume_count = (
            format_string.complex_prop_name._parse_prop_name_and_count(
                complex_prop_name
            )
        )

        prop_file = context.file_system.get_file(PropFile, actor_comp.name, prop_name)
        if prop_file is None:
            continue

        ret.append((prop_file, consume_count))

    return ret


################################################################################################################################################
def retrieve_skill_accessory_files(
    context: RPGGameContext, skill_entity: Entity, actor_entity: Entity
) -> List[PropFile]:
    assert skill_entity.has(SkillComponent)
    assert actor_entity.has(ActorComponent)
    temp = parse_skill_accessory_prop_files(context, skill_entity, actor_entity)
    return [prop_file for prop_file, _ in temp]


################################################################################################################################################
def parse_skill_prop_files(
    context: RPGGameContext, skill_entity: Entity, actor_entity: Entity
) -> List[PropFile]:

    assert skill_entity.has(SkillComponent)
    assert actor_entity.has(ActorComponent)
    if not skill_entity.has(SkillComponent) or not actor_entity.has(ActorComponent):
        return []

    skill_comp = skill_entity.get(SkillComponent)
    actor_comp = actor_entity.get(ActorComponent)
    assert skill_comp.name == actor_comp.name
    if skill_comp.name != actor_comp.name:
        return []

    skill_file = context.file_system.get_file(
        PropFile, skill_comp.name, skill_comp.skill_name
    )
    if skill_file is None or not skill_file.is_skill:
        return []

    return [skill_file]


################################################################################################################################################


def destroy_skill_entity(skill_entity: Entity) -> None:
    assert skill_entity.has(SkillComponent)
    skill_comp = skill_entity.get(SkillComponent)
    logger.debug(f"Destroying skill entity: {skill_comp.name}, {skill_comp.skill_name}")
    skill_entity.replace(DestroyComponent, "")


################################################################################################################################################
