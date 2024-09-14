from entitas import Entity  # type: ignore
from typing import Optional, Any, cast, List, Dict
from loguru import logger
from my_data.game_resource import GameResource
from rpg_game.rpg_game import RPGGame
from rpg_game.rpg_entitas_context import RPGEntitasContext
from extended_systems.file_system import FileSystem
from extended_systems.kick_off_message_system import KickOffMessageSystem
from typing import Optional
from my_agent.lang_serve_agent_system import LangServeAgentSystem
from extended_systems.code_name_component_system import CodeNameComponentSystem
from chaos_engineering.chaos_engineering_system import IChaosEngineering
from chaos_engineering.empty_engineering_system import EmptyChaosEngineeringSystem
from game_sample.game_sample_chaos_engineering_system import (
    GameSampleChaosEngineeringSystem,
)
from pathlib import Path
import json
import shutil
from rpg_game.terminal_game import TerminalGame
from rpg_game.web_game import WebGame
from extended_systems.guid_generator import GUIDGenerator
import gameplay_systems.cn_builtin_prompt as builtin_prompt

from player.player_proxy import PlayerProxy
from extended_systems.files_def import StageArchiveFile, PropFile
from gameplay_systems.components import (
    ActorComponent,
    AppearanceComponent,
    PlayerComponent,
)
from gameplay_systems.check_self_helper import CheckSelfHelper
from player.player_command import (
    PlayerGoTo,
    PlayerBroadcast,
    PlayerSpeak,
    PlayerWhisper,
    PlayerPickUpProp,
    PlayerSteal,
    PlayerGiveProp,
    PlayerBehavior,
    PlayerEquip,
    PlayerKill,
)
import datetime

# todo
GAME_SAMPLE_RUNTIME_DIR = Path("game_sample/gen_runtimes")


#######################################################################################################################################
def _load_game_resource_file(file_path: Path, version: str) -> Any:

    if not file_path.exists():
        return None

    content = file_path.read_text(encoding="utf-8")
    if content is None:
        return None

    data = json.loads(content)
    if data is None:
        return None

    version = cast(str, data["version"])
    if version != version:
        return None

    return data


#######################################################################################################################################
def _create_game_resource(game_name: str, version: str) -> Optional[GameResource]:

    root_runtime_dir = GAME_SAMPLE_RUNTIME_DIR
    root_runtime_dir.mkdir(parents=True, exist_ok=True)

    game_resource_file_path = root_runtime_dir / f"{game_name}.json"
    if not game_resource_file_path.exists():
        return None

    game_data = _load_game_resource_file(game_resource_file_path, version)
    if game_data is None:
        return None

    runtime_file_dir = root_runtime_dir / game_name
    return GameResource(game_name, game_data, runtime_file_dir)


#######################################################################################################################################
# def _create_rpg_game(
#     game_name: str,
#     chaos_engineering: Optional[IChaosEngineering],
#     rpg_game_client_type: GameClientType,
# ) -> Optional[RPGGame]:

#     # 依赖注入的特殊系统
#     file_system = FileSystem(
#         "FileSystem Because it involves IO operations, an independent system is more convenient."
#     )
#     memory_system = KickOffMessageSystem(
#         "KickOffMessageSystem Because it involves IO operations, an independent system is more convenient."
#     )
#     agent_connect_system = LangServeAgentSystem(
#         "LangServeAgentSystem Because it involves net operations, an independent system is more convenient."
#     )
#     code_name_component_system = CodeNameComponentSystem(
#         "CodeNameComponentSystem, Build components by codename for special purposes"
#     )
#     guid_generator = GUIDGenerator("GUIDGenerator")

#     ### 混沌工程系统
#     if chaos_engineering is not None:
#         chaos_engineering_system = chaos_engineering
#     else:
#         chaos_engineering_system = EmptyChaosEngineeringSystem("empty_chaos")

#     # 创建上下文
#     context = RPGEntitasContext(
#         file_system,
#         memory_system,
#         agent_connect_system,
#         code_name_component_system,
#         chaos_engineering_system,
#         guid_generator,
#     )

#     match rpg_game_client_type:
#         case GameClientType.WEB:
#             return WebGame(game_name, context)
#         case GameClientType.TERMINAL:
#             return TerminalGame(game_name, context)
#         case _:
#             assert False, "Not implemented."

#     return None


#######################################################################################################################################
def _create_entitas_context(
    option_chaos_engineering: Optional[IChaosEngineering],
) -> RPGEntitasContext:

    chaos_engineering_system: IChaosEngineering = EmptyChaosEngineeringSystem(
        "empty_chaos"
    )
    if option_chaos_engineering is not None:
        chaos_engineering_system = option_chaos_engineering

    # 创建上下文
    context = RPGEntitasContext(
        FileSystem(
            "FileSystem Because it involves IO operations, an independent system is more convenient."
        ),
        KickOffMessageSystem(
            "KickOffMessageSystem Because it involves IO operations, an independent system is more convenient."
        ),
        LangServeAgentSystem(
            "LangServeAgentSystem Because it involves net operations, an independent system is more convenient."
        ),
        CodeNameComponentSystem(
            "CodeNameComponentSystem, Build components by codename for special purposes"
        ),
        chaos_engineering_system,
        GUIDGenerator("GUIDGenerator"),
    )

    return context


#######################################################################################################################################
# def create_rpg_game(
#     game_name: str, version: str, game_client_type: GameClientType
# ) -> Optional[RPGGame]:

#     game_resource = create_game_resource(game_name, version)
#     if game_resource is None:
#         logger.error("create_world_data_builder 失败。")
#         return None

#     rpg_game = _create_rpg_game(
#         game_name,
#         GameSampleChaosEngineeringSystem("MyChaosEngineeringSystem"),
#         game_client_type,
#     )

#     if rpg_game is None:
#         logger.error("_create_rpg_game 失败。")
#         return None

#     # 执行创建游戏的所有动作
#     rpg_game.build(game_resource)
#     return rpg_game


#######################################################################################################################################
def create_terminal_rpg_game(game_name: str, version: str) -> Optional[RPGGame]:

    game_resource = _create_game_resource(game_name, version)
    if game_resource is None:
        logger.error(f"create_terminal_rpg_game 创建{game_name} 失败。")
        return None

    rpg_context = _create_entitas_context(
        GameSampleChaosEngineeringSystem("terminal_rpg_game_chaos")
    )

    rpg_game = TerminalGame(game_name, rpg_context)
    rpg_game.build(game_resource)
    return rpg_game


#######################################################################################################################################
def create_web_rpg_game(game_name: str, version: str) -> Optional[RPGGame]:
    game_resource = _create_game_resource(game_name, version)
    if game_resource is None:
        logger.error(f"create_web_rpg_game 创建{game_name} 失败。")
        return None

    rpg_context = _create_entitas_context(
        GameSampleChaosEngineeringSystem("web_rpg_game_chaos")
    )

    rpg_game = WebGame(game_name, rpg_context)
    rpg_game.build(game_resource)
    return rpg_game


#######################################################################################################################################
# todo
# def test_save(game_name: str) -> None:

#     copy2_path = GAME_SAMPLE_RUNTIME_DIR / f"{game_name}"
#     if not copy2_path.exists():
#         logger.error("未找到存档，请检查存档是否存在。")
#         return None

#     start_json_file = GAME_SAMPLE_RUNTIME_DIR / f"{game_name}.json"
#     if not start_json_file.exists():
#         logger.error("未找到存档，请检查存档是否存在。")
#         return None

#     # 拷贝运行时文件夹到另一个地方
#     to_save_path = GAME_SAMPLE_RUNTIME_DIR / f"{game_name}_save"
#     to_save_path.mkdir(parents=True, exist_ok=True)
#     shutil.copytree(copy2_path, to_save_path, dirs_exist_ok=True)

#     # 拷贝原始的运行文件
#     target_file = to_save_path / f"{game_name}.json"
#     if target_file.exists():
#         target_file.unlink()
#     shutil.copy(start_json_file, to_save_path / f"{game_name}.json")

#     if not target_file.exists():
#         logger.error(f"File not found: {target_file}")
#         return None

#     logger.info(f"Save to: {to_save_path}")
#     txt = target_file.read_text(encoding="utf-8")
#     obj = json.loads(txt)
#     return None


#######################################################################################################################################


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
def save_game(game_name: RPGGame, player_proxy: PlayerProxy) -> None:
    logger.warning(f"保存游戏 = {game_name._name}, player_proxy = {player_proxy._name}")


##################################################################################################################
def add_player_command(
    rpg_game: RPGGame, player_proxy: PlayerProxy, usr_input: str
) -> bool:

    if "/goto" in usr_input:
        player_proxy.add_command(PlayerGoTo("/goto", usr_input))

    elif "/broadcast" in usr_input:
        player_proxy.add_command(PlayerBroadcast("/broadcast", usr_input))

    elif "/speak" in usr_input:
        player_proxy.add_command(PlayerSpeak("/speak", usr_input))

    elif "/whisper" in usr_input:
        player_proxy.add_command(PlayerWhisper("/whisper", usr_input))

    elif "/pickup" in usr_input:
        player_proxy.add_command(PlayerPickUpProp("/pickup", usr_input))

    elif "/steal" in usr_input:
        player_proxy.add_command(PlayerSteal("/steal", usr_input))

    elif "/give" in usr_input:
        player_proxy.add_command(PlayerGiveProp("/give", usr_input))

    elif "/behavior" in usr_input:
        player_proxy.add_command(PlayerBehavior("/behavior", usr_input))

    elif "/equip" in usr_input:
        player_proxy.add_command(PlayerEquip("/equip", usr_input))

    elif "/kill" in usr_input:
        player_proxy.add_command(PlayerKill("/kill", usr_input))

    else:
        logger.error(f"无法识别的命令 = {usr_input}")
        return False

    return True


###############################################################################################################################################
def player_login(
    rpg_game: RPGGame, player_proxy: PlayerProxy, player_controlled_actor_name: str
) -> None:
    logger.debug("player_login")
    actor_entity = rpg_game._entitas_context.get_actor_entity(
        player_controlled_actor_name
    )
    if actor_entity is None or not actor_entity.has(PlayerComponent):
        logger.error(f"没有找到角色 = {player_controlled_actor_name}")
        return

    # 更改算作登陆成功
    actor_entity.replace(PlayerComponent, player_proxy._name)
    player_proxy._controlled_actor_name = player_controlled_actor_name

    player_proxy.add_system_message(rpg_game.about_game)

    # todo 添加登陆新的信息到客户端消息中
    time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    player_proxy.add_system_message(
        f"login: {player_proxy._name}, time = {time}, 控制角色 = {player_controlled_actor_name}"
    )
    kick_off_messages = rpg_game._entitas_context._kick_off_message_system.get_message(
        player_controlled_actor_name
    )
    if len(kick_off_messages) == 0 or len(kick_off_messages) > 1:
        return
    player_proxy.add_login_message(
        player_controlled_actor_name, kick_off_messages[0].content
    )


##################################################################################################################
