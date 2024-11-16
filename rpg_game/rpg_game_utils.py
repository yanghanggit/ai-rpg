from entitas import Entity  # type: ignore
from typing import Optional, Any, cast, List, Dict
from loguru import logger
from rpg_game.rpg_game_resource import RPGGameResource
from rpg_game.rpg_game import RPGGame
from rpg_game.rpg_entitas_context import RPGEntitasContext
from extended_systems.file_system import FileSystem
from typing import Optional
from my_agent.lang_serve_agent_system import LangServeAgentSystem
from extended_systems.query_component_system import QueryComponentSystem
from chaos_engineering.chaos_engineering_system import IChaosEngineering
from chaos_engineering.empty_engineering_system import EmptyChaosEngineeringSystem
from game_sample.game_sample_chaos_engineering_system import (
    GameSampleChaosEngineeringSystem,
)
from pathlib import Path
import json
from rpg_game.terminal_game import TerminalGame
from rpg_game.web_game import WebGame
from player.player_proxy import PlayerProxy
from extended_systems.archive_file import ActorArchiveFile, StageArchiveFile
from extended_systems.prop_file import PropFile
from my_components.components import (
    ActorComponent,
    PlayerComponent,
    PlanningAllowedComponent,
    KickOffContentComponent,
    KickOffFlagComponent,
)
from gameplay_systems.actor_entity_utils import ActorStatusEvaluator
import gameplay_systems.actor_planning_execution_system
from player.player_command import (
    PlayerGoTo,
    PlayerAnnounce,
    PlayerSpeak,
    PlayerWhisper,
    PlayerSteal,
    PlayerGiveProp,
    PlayerSkill,
    PlayerEquip,
    PlayerKill,
)
import datetime
import shutil
import zipfile
from my_models.event_models import AgentEvent
from my_models.player_models import (
    WatchActionModel,
    CheckActionModel,
    RetrieveActorArchivesModel,
    RetrieveStageArchivesActionModel,
)


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
) -> Optional[RPGGameResource]:

    assert game_resource_file_path.exists()
    game_data = _load_game_resource_file(game_resource_file_path, check_version)
    if game_data is None:
        return None

    return RPGGameResource(game_resource_file_path.stem, game_data, game_runtime_dir)


#######################################################################################################################################
def load_game_resource(
    load_archive_zip_path: Path, game_runtime_dir: Path, check_version: str
) -> Optional[RPGGameResource]:

    assert load_archive_zip_path.exists()

    game_name = load_archive_zip_path.stem
    logger.info(f"加载游戏资源 = {game_name}, path = {load_archive_zip_path}")

    with zipfile.ZipFile(load_archive_zip_path, "r") as zip_ref:
        extract_dir = load_archive_zip_path.parent / game_name
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        zip_ref.extractall(extract_dir)

    game_archive_file_path = extract_dir / RPGGameResource.generate_runtime_file_name(
        game_name
    )
    if not game_archive_file_path.exists():
        assert False, f"找不到游戏资源文件 = {game_archive_file_path}"
        return None

    game_data = _load_game_resource_file(game_archive_file_path, check_version)
    if game_data is None:
        return None

    load_game_resource = RPGGameResource(game_name, game_data, game_runtime_dir)
    load_game_resource.load(extract_dir, game_archive_file_path)
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
        FileSystem(),
        LangServeAgentSystem(),
        QueryComponentSystem(),
        chaos_engineering_system,
    )

    return context


#######################################################################################################################################
def create_terminal_rpg_game(game_resource: RPGGameResource) -> Optional[TerminalGame]:

    rpg_context = _create_entitas_context(
        GameSampleChaosEngineeringSystem("terminal_rpg_game_chaos")
    )

    rpg_game = TerminalGame(game_resource._game_name, rpg_context)
    rpg_game.build(game_resource)
    return rpg_game


#######################################################################################################################################
def create_web_rpg_game(game_resource: RPGGameResource) -> Optional[WebGame]:

    rpg_context = _create_entitas_context(
        GameSampleChaosEngineeringSystem("web_rpg_game_chaos")
    )

    rpg_game = WebGame(game_resource._game_name, rpg_context)
    rpg_game.build(game_resource)
    return rpg_game


#######################################################################################################################################
def get_props_in_stage(game_name: RPGGame, player_entity: Entity) -> List[PropFile]:
    stage_entity = game_name.context.safe_get_stage_entity(player_entity)
    if stage_entity is None:
        return []
    stage_name = game_name.context.safe_get_entity_name(stage_entity)
    return game_name.context.file_system.get_files(PropFile, stage_name)


#######################################################################################################################################
def get_stage_narrate_content_from_stage_archive_file(
    game_name: RPGGame, player_entity: Entity
) -> str:

    stage_entity = game_name.context.safe_get_stage_entity(player_entity)
    if stage_entity is None:
        return ""

    actor_name = game_name.context.safe_get_entity_name(player_entity)
    stage_name = game_name.context.safe_get_entity_name(stage_entity)

    if game_name.context.file_system.has_file(StageArchiveFile, actor_name, stage_name):

        stage_archive = game_name.context.file_system.get_file(
            StageArchiveFile, actor_name, stage_name
        )

        if stage_archive is not None:
            return stage_archive.stage_narrate

    return ""


#######################################################################################################################################
def gen_player_watch_action_model(
    game_name: RPGGame, player_proxy: PlayerProxy
) -> Optional[WatchActionModel]:
    player_entity = game_name.context.get_player_entity(player_proxy.name)
    if player_entity is None:
        return None

    stage_narrate_content = get_stage_narrate_content_from_stage_archive_file(
        game_name, player_entity
    )

    ## 场景内的角色信息获取
    actors_info: Dict[str, str] = game_name.context.retrieve_stage_actor_appearance(
        player_entity
    )
    actors_info.pop(game_name.context.safe_get_entity_name(player_entity))

    actors_info_prompts = [
        f"""{actor_name}: {appearance}"""
        for actor_name, appearance in actors_info.items()
    ]

    if len(actors_info_prompts) == 0:
        actors_info_prompts.append("- 场景内无其他角色。")

    # 场景名称
    stage_entity = game_name.context.safe_get_stage_entity(player_entity)
    assert stage_entity is not None
    stage_name = game_name.context.safe_get_entity_name(stage_entity)

    # 最终返回
    message = f"""# {player_proxy.name} | {player_proxy.actor_name} 获取场景信息

## 场景描述: {stage_name}
{stage_narrate_content}

## 场景内角色
{"\n".join(actors_info_prompts)}"""

    return WatchActionModel(content=message)


#######################################################################################################################################
def gen_player_check_action_model(
    game_name: RPGGame, player_proxy: PlayerProxy
) -> Optional[CheckActionModel]:
    player_entity = game_name.context.get_player_entity(player_proxy.name)
    if player_entity is None:
        return None

    #
    actor_status_evaluator = ActorStatusEvaluator(game_name.context, player_entity)

    # 生命值
    health = actor_status_evaluator.health * 100

    # 道具信息
    actor_props_prompt = (
        gameplay_systems.actor_planning_execution_system._generate_props_prompt(
            actor_status_evaluator._category_prop_files
        )
    )

    if len(actor_props_prompt) == 0:
        actor_props_prompt.append("无任何道具。")

    # 最终返回
    message = f"""# {player_proxy.name} | {player_proxy.actor_name}

## 所在的场景：{actor_status_evaluator.stage_name}

## 健康状态
{f"生命值: {health:.2f}%"}

## 持有的道具
{"\n".join(actor_props_prompt)}

## 你的外貌
{actor_status_evaluator.appearance}"""

    return CheckActionModel(content=message)


#######################################################################################################################################
def gen_player_retrieve_actor_archives_action_model(
    game_name: RPGGame, player_proxy: PlayerProxy
) -> Optional[RetrieveActorArchivesModel]:

    player_entity = game_name.context.get_player_entity(player_proxy.name)
    if player_entity is None:
        return None

    file_owner_name = game_name.context.safe_get_entity_name(player_entity)
    archive_files = game_name.context.file_system.get_files(
        ActorArchiveFile, file_owner_name
    )

    ret: RetrieveActorArchivesModel = RetrieveActorArchivesModel(
        message="这是角色档案！！！！", archives=[]
    )

    for archive_file in archive_files:
        ret.archives.append(archive_file._model)

    return ret


#######################################################################################################################################
def gen_player_retrieve_stage_archives_action_model(
    game_name: RPGGame, player_proxy: PlayerProxy
) -> Optional[RetrieveStageArchivesActionModel]:

    player_entity = game_name.context.get_player_entity(player_proxy.name)
    if player_entity is None:
        return None

    file_owner_name = game_name.context.safe_get_entity_name(player_entity)
    archive_files = game_name.context.file_system.get_files(
        StageArchiveFile, file_owner_name
    )

    ret: RetrieveStageArchivesActionModel = RetrieveStageArchivesActionModel(
        message="这是场景档案！！！！", archives=[]
    )

    for archive_file in archive_files:
        ret.archives.append(archive_file._model)

    return ret


#######################################################################################################################################
def save_game(rpg_game: RPGGame, archive_dir: Path, format: str = "zip") -> None:

    assert rpg_game._game_resource is not None

    logger.info(
        f"保存游戏 = {rpg_game._name}, _runtime_dir = {rpg_game._game_resource._runtime_dir}"
    )

    zip_file_path = shutil.make_archive(
        rpg_game._name, format, rpg_game._game_resource._runtime_dir
    )

    # archive_dir = Path(save_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)
    assert archive_dir.exists()

    shutil.move(zip_file_path, archive_dir / f"{rpg_game._name}.zip")
    logger.info(f"游戏已保存到 {archive_dir / f'{rpg_game._name}.zip'}")


#######################################################################################################################################
def add_player_command(
    rpg_game: RPGGame, player_proxy: PlayerProxy, usr_input: str
) -> bool:

    if "/goto" in usr_input:
        player_proxy.add_command(PlayerGoTo("/goto", usr_input))

    elif "/announce" in usr_input:
        player_proxy.add_command(PlayerAnnounce("/announce", usr_input))

    elif "/speak" in usr_input:
        player_proxy.add_command(PlayerSpeak("/speak", usr_input))

    elif "/whisper" in usr_input:
        player_proxy.add_command(PlayerWhisper("/whisper", usr_input))

    # elif "/pickup" in usr_input:
    #     player_proxy.add_command(PlayerPickUpProp("/pickup", usr_input))

    elif "/steal" in usr_input:
        player_proxy.add_command(PlayerSteal("/steal", usr_input))

    elif "/give" in usr_input:
        player_proxy.add_command(PlayerGiveProp("/give", usr_input))

    elif "/skill" in usr_input:
        player_proxy.add_command(PlayerSkill("/skill", usr_input))

    elif "/equip" in usr_input:
        player_proxy.add_command(PlayerEquip("/equip", usr_input))

    elif "/kill" in usr_input:
        player_proxy.add_command(PlayerKill("/kill", usr_input))

    else:
        logger.error(f"无法识别的命令 = {usr_input}")
        return False

    return True


#######################################################################################################################################
def player_play_new_game(
    rpg_game: RPGGame, player_proxy: PlayerProxy, player_actor_name: str
) -> None:

    player_entity = rpg_game.context.get_actor_entity(player_actor_name)
    if player_entity is None or not player_entity.has(PlayerComponent):
        logger.error(f"没有找到角色 = {player_actor_name}")
        return

    # 更改算作登陆成功
    player_entity.replace(PlayerComponent, player_proxy.name)
    player_proxy.set_actor(player_actor_name)

    # 添加游戏介绍
    player_proxy.add_system_message(AgentEvent(message=rpg_game.about_game))

    # log 信息
    time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(
        f"time = {time}, 玩家登陆游戏 = {player_proxy.name}, 控制角色 = {player_actor_name}"
    )

    # 配置的启动故事，因为player的kickoff只能在这里
    kick_off_comp = player_entity.get(KickOffContentComponent)
    player_proxy.cache_kickoff_message(
        player_actor_name,
        AgentEvent(message=kick_off_comp.content),
    )

    # 做kickoff标记 完成
    assert not player_entity.has(KickOffFlagComponent)
    player_entity.replace(KickOffFlagComponent, player_proxy.actor_name)


#######################################################################################################################################
def player_play_again(rpg_game: RPGGame, player_name: str) -> Optional[PlayerProxy]:

    player_proxy = rpg_game.get_player(player_name)
    if player_proxy is None:
        assert False, f"没有找到玩家 = {player_name}"
        return None

    time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(
        f"time = {time}, 玩家登陆游戏 = {player_proxy.name}, 控制角色 = {player_proxy.actor_name}"
    )

    player_proxy.cache_kickoff_message(
        player_proxy.actor_name,
        AgentEvent(message=f"再次游戏: {rpg_game._name}。"),
    )

    # 因为是load的，到了这里肯定有！！！
    player_entity = rpg_game.context.get_actor_entity(player_proxy.actor_name)
    assert player_entity is not None
    assert player_entity.has(KickOffFlagComponent)

    return player_proxy


#######################################################################################################################################
def get_player_actor(rpg_game: RPGGame) -> List[str]:

    actor_entities = rpg_game.context.get_player_entities()
    ret: List[str] = []
    for actor_entity in actor_entities:
        actor_comp = actor_entity.get(ActorComponent)
        ret.append(actor_comp.name)

    return ret


#######################################################################################################################################
def get_turn_player_actors(rpg_game: RPGGame) -> List[str]:

    ret: List[str] = []

    players = rpg_game.context.get_player_entities()
    for player in players:
        if player.has(PlanningAllowedComponent):
            ret.append(player.get(PlanningAllowedComponent).name)

    return ret


#######################################################################################################################################
def is_player_turn(rpg_game: RPGGame, player_proxy: PlayerProxy) -> bool:
    player_entity = rpg_game.context.get_player_entity(player_proxy.name)
    if player_entity is None:
        return False

    return player_entity.has(PlanningAllowedComponent)


#######################################################################################################################################
