from entitas import Entity  # type: ignore
from typing import Optional, Any, cast, List, Dict
from loguru import logger
from my_data.game_resource import GameResource
from rpg_game.rpg_game import RPGGame
from rpg_game.rpg_entitas_context import RPGEntitasContext
from extended_systems.file_system import FileSystem
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
from rpg_game.terminal_game import TerminalGame
from rpg_game.web_game import WebGame
import gameplay_systems.public_builtin_prompt as public_builtin_prompt

from player.player_proxy import PlayerProxy
from extended_systems.files_def import StageArchiveFile, PropFile
from gameplay_systems.components import (
    ActorComponent,
    AppearanceComponent,
    PlayerComponent,
    PlanningAllowedComponent,
    KickOffComponent,
)
from gameplay_systems.check_self_helper import SelfChecker
import gameplay_systems.actor_planning_execution_system
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
from rpg_game.rpg_game_config import RPGGameConfig
import shutil
import zipfile


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
        logger.error(f"版本不匹配，期望版本 = {version}, 实际版本 = {version}")
        return None

    return data


#######################################################################################################################################
def create_game_resource(
    game_resource_file_path: Path, game_runtime_dir: Path, check_version: str
) -> Optional[GameResource]:

    assert game_resource_file_path.exists()
    game_data = _load_game_resource_file(game_resource_file_path, check_version)
    if game_data is None:
        return None

    return GameResource(game_resource_file_path.stem, game_data, game_runtime_dir)


#######################################################################################################################################
def load_game_resource(
    load_archive_zip_path: Path, game_runtime_dir: Path, check_version: str
) -> Optional[GameResource]:

    assert load_archive_zip_path.exists()

    game_name = load_archive_zip_path.stem
    logger.info(f"加载游戏资源 = {game_name}, path = {load_archive_zip_path}")

    with zipfile.ZipFile(load_archive_zip_path, "r") as zip_ref:
        extract_dir = load_archive_zip_path.parent / game_name
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        zip_ref.extractall(extract_dir)

    game_archive_file_path = extract_dir / GameResource.generate_runtime_file_name(
        game_name
    )
    if not game_archive_file_path.exists():
        assert False, f"找不到游戏资源文件 = {game_archive_file_path}"
        return None

    game_data = _load_game_resource_file(game_archive_file_path, check_version)
    if game_data is None:
        return None

    load_game_resource = GameResource(game_name, game_data, game_runtime_dir)
    load_game_resource.load(extract_dir)
    return load_game_resource


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
        LangServeAgentSystem(
            "LangServeAgentSystem Because it involves net operations, an independent system is more convenient."
        ),
        CodeNameComponentSystem(
            "CodeNameComponentSystem, Build components by codename for special purposes"
        ),
        chaos_engineering_system,
    )

    return context


#######################################################################################################################################
def create_terminal_rpg_game(game_resource: GameResource) -> Optional[TerminalGame]:

    rpg_context = _create_entitas_context(
        GameSampleChaosEngineeringSystem("terminal_rpg_game_chaos")
    )

    rpg_game = TerminalGame(game_resource._game_name, rpg_context)
    rpg_game.build(game_resource)
    return rpg_game


#######################################################################################################################################
def create_web_rpg_game(game_resource: GameResource) -> Optional[WebGame]:

    rpg_context = _create_entitas_context(
        GameSampleChaosEngineeringSystem("web_rpg_game_chaos")
    )

    rpg_game = WebGame(game_resource._game_name, rpg_context)
    rpg_game.build(game_resource)
    return rpg_game


#######################################################################################################################################
def get_props_in_stage(game_name: RPGGame, player_entity: Entity) -> List[PropFile]:
    stage_entity = game_name._entitas_context.safe_get_stage_entity(player_entity)
    if stage_entity is None:
        return []
    stage_name = game_name._entitas_context.safe_get_entity_name(stage_entity)
    return game_name._entitas_context._file_system.get_files(PropFile, stage_name)


#######################################################################################################################################
def get_stage_narrate_content(game_name: RPGGame, player_entity: Entity) -> str:

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
            return stage_archive.stage_narrate

    return ""


#######################################################################################################################################
def get_info_of_actors_in_stage(
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


#######################################################################################################################################
def gen_player_watch_message(game_name: RPGGame, player_proxy: PlayerProxy) -> str:
    player_entity = game_name._entitas_context.get_player_entity(player_proxy._name)
    if player_entity is None:
        return ""

    stage_narrate_content = get_stage_narrate_content(game_name, player_entity)

    actors_info: Dict[str, str] = get_info_of_actors_in_stage(game_name, player_entity)

    actors_info_prompts = [
        f"""{actor_name}: {appearance}"""
        for actor_name, appearance in actors_info.items()
    ]

    props_in_stage = get_props_in_stage(game_name, player_entity)
    props_in_stage_prompts = [
        public_builtin_prompt.generate_prop_prompt(
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

    return message


#######################################################################################################################################
def gen_player_check_message(game_name: RPGGame, player_proxy: PlayerProxy) -> str:
    player_entity = game_name._entitas_context.get_player_entity(player_proxy._name)
    if player_entity is None:
        return ""

    stage_entity = game_name._entitas_context.safe_get_stage_entity(player_entity)
    assert stage_entity is not None
    stage_name = game_name._entitas_context.safe_get_entity_name(stage_entity)

    controlled_actor_name = game_name._entitas_context.safe_get_entity_name(
        player_entity
    )

    check_self = SelfChecker(game_name._entitas_context, player_entity)
    health = check_self.health * 100

    actor_props_prompt = (
        gameplay_systems.actor_planning_execution_system._generate_actor_props_prompts(
            check_self._category_prop_files
        )
    )

    message = f"""# {player_proxy._name} | {controlled_actor_name} 自身检查

## 你当前所在的场景：{stage_name}

## 你的健康状态
{f"生命值: {health:.2f}%"}

## 你当前持有的道具
{len(actor_props_prompt) > 0 and "\n".join(actor_props_prompt) or "- 无任何道具。"}

"""

    return message


#######################################################################################################################################
def save_game(rpg_game: RPGGame) -> None:

    assert rpg_game._game_resource is not None

    logger.info(
        f"保存游戏 = {rpg_game._name}, _runtime_dir = {rpg_game._game_resource._runtime_dir}"
    )

    zip_file_path = shutil.make_archive(
        rpg_game._name, "zip", rpg_game._game_resource._runtime_dir
    )

    archive_dir = Path(RPGGameConfig.GAME_ARCHIVE_DIR)
    archive_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(zip_file_path, archive_dir / f"{rpg_game._name}.zip")

    logger.info(f"游戏已保存到 {archive_dir / f'{rpg_game._name}.zip'}")


#######################################################################################################################################
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


#######################################################################################################################################
def player_join(
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
    player_proxy._ctrl_actor_name = player_controlled_actor_name

    player_proxy.add_system_message(rpg_game.about_game)

    # todo 添加登陆新的信息到客户端消息中
    time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    player_proxy.add_system_message(
        f"login: {player_proxy._name}, time = {time}, 控制角色 = {player_controlled_actor_name}"
    )

    kick_off_comp = actor_entity.get(KickOffComponent)
    player_proxy.add_login_message(player_controlled_actor_name, kick_off_comp.content)


#######################################################################################################################################
def get_player_ctrl_actor_names(rpg_game: RPGGame) -> List[str]:

    actor_entities = rpg_game._entitas_context.get_player_entities()
    ret: List[str] = []
    for actor_entity in actor_entities:
        actor_comp = actor_entity.get(ActorComponent)
        ret.append(actor_comp.name)

    return ret


#######################################################################################################################################
def is_player_turn(rpg_game: RPGGame, player_proxy: PlayerProxy) -> bool:
    player_entity = rpg_game._entitas_context.get_player_entity(player_proxy._name)
    if player_entity is None:
        return False

    return player_entity.has(PlanningAllowedComponent)
