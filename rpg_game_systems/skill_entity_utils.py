"""
本文件主要是一些与 SkillEntity 相关的工具函数
"""

from entitas import Entity  # type: ignore
from game.rpg_game_context import RPGGameContext
from typing import List
from loguru import logger
from extended_systems.prop_file import PropFile
import format_string.complex_prop_name
from components.components import (
    ActorComponent,
    SkillComponent,
    DestroyFlagComponent,
    WeaponComponent,
)
from rpg_models.file_models import PropSkillUsageMode


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
def retrieve_skill_accessory_prop_files(
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
    skill_entity.replace(DestroyFlagComponent, "")


################################################################################################################################################
def validate_direct_skill(
    context: RPGGameContext, skill_entity: Entity, actor_entity: Entity
) -> bool:

    assert skill_entity.has(SkillComponent)
    assert actor_entity.has(ActorComponent)

    #
    skill_comp = skill_entity.get(SkillComponent)
    assert skill_comp.skill_name != ""

    skill_accessory_prop_files = parse_skill_accessory_prop_files(
        context, skill_entity, actor_entity
    )

    # 无任何技能附属道具，就是直接技能
    if len(skill_accessory_prop_files) == 0:
        return True

    # 有多个技能附属道具，就不是直接技能
    if len(skill_accessory_prop_files) > 1:
        return False

    # 有一个技能附属道具，但不是武器，就不是直接技能
    single_accessory_prop_file, _ = skill_accessory_prop_files[0]
    if not single_accessory_prop_file.is_weapon:
        return False

    # 有一个技能附属道具，且是武器，但是有insight信息，就不是直接技能
    if single_accessory_prop_file.insight != "":
        return False

    # 有一个技能附属道具，且是武器，但不是当前使用的武器，就不是直接技能
    weapon_comp = actor_entity.get(WeaponComponent)
    if weapon_comp is None:
        return False

    # 有一个技能附属道具，且是武器，且是当前使用的武器，就是直接技能
    if weapon_comp.prop_name != single_accessory_prop_file.name:
        return False

    return True


################################################################################################################################################
def format_direct_skill_inspector_content(
    context: RPGGameContext, skill_entity: Entity
) -> str:

    assert skill_entity.has(SkillComponent)

    skill_comp = skill_entity.get(SkillComponent)
    skill_prop_file = context.file_system.get_file(
        PropFile, skill_comp.name, skill_comp.skill_name
    )
    assert skill_prop_file is not None, "skill_prop_file is None."
    if skill_prop_file is None:
        logger.error(f"skill_prop_file {skill_comp.skill_name} not found.")
        return ""

    skill_appearance = str(skill_prop_file.appearance)

    assert (
        PropSkillUsageMode.CASTER_TAG in skill_appearance
    ), "技能表现中没有技能施放者标签"
    if PropSkillUsageMode.CASTER_TAG in skill_appearance:
        skill_appearance = skill_appearance.replace(
            PropSkillUsageMode.CASTER_TAG, skill_comp.name
        )

    assert (
        PropSkillUsageMode.SINGLE_TARGET_TAG in skill_appearance
        or PropSkillUsageMode.MULTI_TARGETS_TAG in skill_appearance
    ), "技能表现中没有目标标签"
    if PropSkillUsageMode.SINGLE_TARGET_TAG in skill_appearance:
        skill_appearance = skill_appearance.replace(
            PropSkillUsageMode.SINGLE_TARGET_TAG, ",".join(skill_comp.targets)
        )
    if PropSkillUsageMode.MULTI_TARGETS_TAG in skill_appearance:
        skill_appearance = skill_appearance.replace(
            PropSkillUsageMode.MULTI_TARGETS_TAG, ",".join(skill_comp.targets)
        )

    return skill_appearance


################################################################################################################################################
