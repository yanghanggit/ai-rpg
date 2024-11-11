from entitas import Entity  # type: ignore
from my_components.action_components import (
    SkillAccessoryAction,
    SkillInvocationAction,
    SkillAction,
    SkillTargetAction,
    SkillWorldHarmonyInspectorAction,
)

from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import List, Set
from loguru import logger
from extended_systems.prop_file import PropFile
import my_format_string.editor_prop_info_string


################################################################################################################################################
def parse_skill_accessory_prop_info_from_action(
    context: RPGEntitasContext, entity: Entity
) -> List[tuple[PropFile, int]]:
    if not entity.has(SkillAccessoryAction):
        return []

    safe_name = context.safe_get_entity_name(entity)
    prop_action = entity.get(SkillAccessoryAction)
    ret: List[tuple[PropFile, int]] = []
    for format_string in prop_action.values:

        if not my_format_string.editor_prop_info_string.check_prop_name_and_count_format(
            format_string
        ):
            logger.error(f"Invalid prop name and count format: {format_string}")
            continue

        prop_name, count = (
            my_format_string.editor_prop_info_string._extract_prop_name_and_count(
                format_string
            )
        )

        prop_file = context._file_system.get_file(PropFile, safe_name, prop_name)
        if prop_file is None:
            continue

        ret.append((prop_file, count))

    return ret


################################################################################################################################################
def list_skill_accessory_prop_files_from_action(
    context: RPGEntitasContext, entity: Entity
) -> List[PropFile]:
    temp = parse_skill_accessory_prop_info_from_action(context, entity)
    return [prop_file for prop_file, _ in temp]


################################################################################################################################################
def parse_skill_invocation_action_command(entity: Entity) -> str:
    skill_invocation_action = entity.get(SkillInvocationAction)
    if skill_invocation_action is None or len(skill_invocation_action.values) == 0:
        return ""
    return skill_invocation_action.values[0]


################################################################################################################################################
def parse_skill_prop_files_from_action(
    context: RPGEntitasContext, entity: Entity
) -> List[PropFile]:

    skill_action = entity.get(SkillAction)
    if skill_action is None:
        return []

    ret: List[PropFile] = []
    safe_name = context.safe_get_entity_name(entity)
    for skill_name in skill_action.values:

        skill_file = context._file_system.get_file(PropFile, safe_name, skill_name)
        if skill_file is None or not skill_file.is_skill:
            continue

        ret.append(skill_file)

    return ret


################################################################################################################################################
def parse_skill_target_from_action(
    context: RPGEntitasContext, entity: Entity
) -> Set[Entity]:

    skill_target_action = entity.get(SkillTargetAction)
    if skill_target_action is None:
        return set()

    targets = set()
    for target_name in skill_target_action.values:
        target = context.get_entity_by_name(target_name)
        if target is not None:
            targets.add(target)

    return targets


################################################################################################################################################
def add_skill_world_harmony_inspector_action(
    context: RPGEntitasContext,
    entity: Entity,
    inspector_tag: str,
    inspector_content: str,
) -> None:

    safe_name = context.safe_get_entity_name(entity)
    entity.replace(
        SkillWorldHarmonyInspectorAction,
        safe_name,
        [inspector_tag, inspector_content],
    )


################################################################################################################################################
def parse_skill_world_harmony_inspector_action(entity: Entity) -> tuple[str, str]:

    skill_world_harmony_inspector_action = entity.get(SkillWorldHarmonyInspectorAction)
    if skill_world_harmony_inspector_action is None:
        return "", ""

    return (
        skill_world_harmony_inspector_action.values[0],
        skill_world_harmony_inspector_action.values[1],
    )


################################################################################################################################################
def has_skill_system_action(entity: Entity) -> bool:
    return (
        entity.has(SkillInvocationAction)
        or entity.has(SkillAction)
        or entity.has(SkillTargetAction)
        or entity.has(SkillAccessoryAction)
        or entity.has(SkillWorldHarmonyInspectorAction)
    )


################################################################################################################################################
def clear_skill_system_actions(entity: Entity) -> None:
    if entity.has(SkillInvocationAction):
        entity.remove(SkillInvocationAction)
    if entity.has(SkillAction):
        entity.remove(SkillAction)
    if entity.has(SkillTargetAction):
        entity.remove(SkillTargetAction)
    if entity.has(SkillAccessoryAction):
        entity.remove(SkillAccessoryAction)
    if entity.has(SkillWorldHarmonyInspectorAction):
        entity.remove(SkillWorldHarmonyInspectorAction)


################################################################################################################################################
