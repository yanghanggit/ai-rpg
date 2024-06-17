from typing import Optional, Any
from loguru import logger
from auxiliary.game_builders import GameBuilder
from rpg_game import RPGGame 
from auxiliary.extended_context import ExtendedContext
from auxiliary.file_system import FileSystem
from auxiliary.kick_off_memory_system import KickOffMemorySystem
from typing import Optional
from auxiliary.lang_serve_agent_system import LangServeAgentSystem
from auxiliary.code_name_component_system import CodeNameComponentSystem
from auxiliary.chaos_engineering_system import EmptyChaosEngineeringSystem, IChaosEngineering
from auxiliary.data_base_system import DataBaseSystem
from budding_world.chaos_budding_world import ChaosBuddingWorld
from pathlib import Path
import json
#######################################################################################################################################
def load_game_file(game_build_file_path: Path, version: str) -> Any:
    if not game_build_file_path.exists():
        logger.error("未找到存档，请检查存档是否存在。")
        return None
    try:
        _content = game_build_file_path.read_text(encoding="utf-8")
        assert _content is not None, f"File is empty: {game_build_file_path}"
        _json = json.loads(_content)
        if _json is None:
            logger.error(f"File {game_build_file_path} is empty.")
            return None
        _version: str = _json['version']
        if _version != version:
            logger.error(f'游戏数据(World.json)与Builder版本不匹配，请检查。')
            return None
        return _json
    except FileNotFoundError:
        assert False, f"File not found: {game_build_file_path}"
        return None
#######################################################################################################################################
### （临时的）写死创建budding_world
def load_then_build_game_data(gamename: str, data_base_system: DataBaseSystem) -> Optional[GameBuilder]:
    version = 'ewan'

    root_runtime_dir = Path("budding_world/gen_runtimes")
    root_runtime_dir.mkdir(parents=True, exist_ok=True)

    game_build_file_path = root_runtime_dir / f"{gamename}.json"
    if not game_build_file_path.exists():
        logger.error("未找到存档，请检查存档是否存在。")
        return None

    game_data = load_game_file(game_build_file_path, version)
    if game_data is None:
        logger.error("load_game_file 失败。")
        return None

    #todo?
    runtimedir = f"./budding_world/gen_runtimes/"
    runtime_file_dir = root_runtime_dir / gamename
    return GameBuilder(gamename, game_data, runtimedir, data_base_system, runtime_file_dir).build()
#######################################################################################################################################
## 创建RPG Game
def create_rpg_game(worldname: str, chaosengineering: Optional[IChaosEngineering], data_base_system: DataBaseSystem) -> RPGGame:

    # 依赖注入的特殊系统
    file_system = FileSystem("file_system， Because it involves IO operations, an independent system is more convenient.")
    memory_system = KickOffMemorySystem("memorey_system， Because it involves IO operations, an independent system is more convenient.")
    agent_connect_system = LangServeAgentSystem("agent_connect_system， Because it involves net operations, an independent system is more convenient.")
    code_name_component_system = CodeNameComponentSystem("Build components by codename for special purposes")
    
    ### 混沌工程系统
    if chaosengineering is not None:
        chaos_engineering_system = chaosengineering
    else:
        chaos_engineering_system = EmptyChaosEngineeringSystem("empty_chaos")

    # 创建上下文
    context = ExtendedContext(file_system, 
                              memory_system, 
                              agent_connect_system, 
                              code_name_component_system,  
                              data_base_system,
                              chaos_engineering_system,
                              False,
                              10000000)

    # 创建游戏
    return RPGGame(worldname, context)
#######################################################################################################################################
## 创建RPG Game + 读取数据
def load_then_create_rpg_game(gamename: str) -> Optional[RPGGame]:
    # 通过依赖注入的方式创建数据系统
    data_base_system = DataBaseSystem("test!!! data_base_system，it is a system that stores all the origin data from the settings.")
    game_builder = load_then_build_game_data(gamename, data_base_system)
    if game_builder is None:
        logger.error("create_world_data_builder 失败。")
        return None
    
    # 创建游戏 + 专门的混沌工程系统
    chaos_engineering_system = ChaosBuddingWorld("ChaosBuddingWorld")
    rpggame = create_rpg_game(gamename, chaos_engineering_system, game_builder.data_base_system)
    if rpggame is None:
        logger.error("_create_rpg_game 失败。")
        return None
    
    # 执行创建游戏的所有动作
    return rpggame.create_game(game_builder)
#######################################################################################################################################