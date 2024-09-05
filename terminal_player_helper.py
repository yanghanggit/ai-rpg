from entitas import Entity  # type: ignore
from player.player_proxy import PlayerProxy
from rpg_game.rpg_game import RPGGame
from extended_systems.files_def import StageArchiveFile, PropFile
from typing import Dict, List
from gameplay_systems.components import ActorComponent, AppearanceComponent
from loguru import logger
import gameplay_systems.cn_builtin_prompt as builtin_prompt
from gameplay_systems.check_self_helper import CheckSelfHelper


##################################################################################################################
def get_player_entity_stage_props(
    game_name: RPGGame, player_entity: Entity
) -> List[PropFile]:
    stage_entity = game_name._entitas_context.safe_get_stage_entity(player_entity)
    if stage_entity is None:
        return []
    stage_name = game_name._entitas_context.safe_get_entity_name(stage_entity)
    return game_name._entitas_context._file_system.get_files(PropFile, stage_name)


##################################################################################################################
def get_player_entity_stage_narrate_content(
    game_name: RPGGame, player_entity: Entity
) -> str:

    stage_entity = game_name._entitas_context.safe_get_stage_entity(player_entity)
    if stage_entity is None:
        return ""

    actor_name = game_name._entitas_context.safe_get_entity_name(player_entity)
    stage_name = game_name._entitas_context.safe_get_entity_name(stage_entity)

    if game_name._entitas_context._file_system.has_file(
        StageArchiveFile, actor_name, stage_name
    ):

        stage_archive = game_name._entitas_context._file_system.get_file(
            StageArchiveFile, actor_name, stage_name
        )

        if stage_archive is not None:
            return stage_archive._stage_narrate

    return ""


##################################################################################################################
def get_player_entity_stage_actor_info(
    game_name: RPGGame, player_entity: Entity
) -> Dict[str, str]:
    stage_entity = game_name._entitas_context.safe_get_stage_entity(player_entity)
    if stage_entity is None:
        return {}

    actor_entities = game_name._entitas_context.get_actors_in_stage(stage_entity)
    ret: Dict[str, str] = {}
    for actor_entity in actor_entities:
        actor_comp = actor_entity.get(ActorComponent)
        appearance_comp = actor_entity.get(AppearanceComponent)
        ret.setdefault(actor_comp.name, appearance_comp.appearance)

    return ret


##################################################################################################################
def handle_player_input_watch(game_name: RPGGame, player_proxy: PlayerProxy) -> None:
    player_entity = game_name._entitas_context.get_player_entity(player_proxy._name)
    if player_entity is None:
        return

    stage_narrate_content = get_player_entity_stage_narrate_content(
        game_name, player_entity
    )

    actors_info: Dict[str, str] = get_player_entity_stage_actor_info(
        game_name, player_entity
    )

    actors_info_prompts = [
        f"""{actor_name}: {appearance}"""
        for actor_name, appearance in actors_info.items()
    ]

    props_in_stage = get_player_entity_stage_props(game_name, player_entity)
    props_in_stage_prompts = [
        builtin_prompt.make_prop_prompt(
            prop, description_prompt=False, appearance_prompt=True, attr_prompt=False
        )
        for prop in props_in_stage
    ]

    stage_entity = game_name._entitas_context.safe_get_stage_entity(player_entity)
    assert stage_entity is not None
    stage_name = game_name._entitas_context.safe_get_entity_name(stage_entity)

    controlled_actor_name = game_name._entitas_context.safe_get_entity_name(
        player_entity
    )

    message = f"""# {player_proxy._name} | {controlled_actor_name} 获取场景信息

## 场景描述: {stage_name}
{stage_narrate_content}

## 场景内角色
{"\n".join(actors_info_prompts)}

## 场景内道具
{"\n".join(props_in_stage_prompts)}"""

    while True:
        logger.info(message)
        input(f"按任意键继续")
        break


##################################################################################################################
def handle_player_input_check(game_name: RPGGame, player_proxy: PlayerProxy) -> None:
    player_entity = game_name._entitas_context.get_player_entity(player_proxy._name)
    if player_entity is None:
        return

    stage_entity = game_name._entitas_context.safe_get_stage_entity(player_entity)
    assert stage_entity is not None
    stage_name = game_name._entitas_context.safe_get_entity_name(stage_entity)

    controlled_actor_name = game_name._entitas_context.safe_get_entity_name(
        player_entity
    )

    check_self = CheckSelfHelper(game_name._entitas_context, player_entity)
    health = check_self.health * 100

    actor_props_prompt = builtin_prompt.make_props_prompt_list_for_actor_plan(
        check_self._categorized_prop_files
    )

    message = f"""# {player_proxy._name} | {controlled_actor_name} 自身检查

## 你当前所在的场景：{stage_name}

## 你的健康状态
{f"生命值: {health:.2f}%"}

## 你当前持有的道具
{len(actor_props_prompt) > 0 and "\n".join(actor_props_prompt) or "- 无任何道具。"}

"""

    while True:
        logger.info(message)
        input(f"按任意键继续")
        break


##################################################################################################################
