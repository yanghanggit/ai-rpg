import os
from typing import Optional
from loguru import logger
from auxiliary.builders import GameBuilder
from rpg_game import RPGGame 
from auxiliary.extended_context import ExtendedContext
from auxiliary.file_system import FileSystem
from auxiliary.memory_system import MemorySystem
from typing import Optional
from auxiliary.agent_connect_system import AgentConnectSystem
from auxiliary.code_name_component_system import CodeNameComponentSystem
from auxiliary.chaos_engineering_system import EmptyChaosEngineeringSystem, IChaosEngineering
from auxiliary.data_base_system import DataBaseSystem
from budding_world.chaos_budding_world import ChaosBuddingWorld

#######################################################################################################################################
### （临时的）写死创建budding_world
def _read_and_build_game_data(gamename: str, data_base_system: DataBaseSystem) -> Optional[GameBuilder]:
    version = 'ewan'
    runtimedir = f"./budding_world/gen_runtimes/"
    game_data_path: str = f"{runtimedir}{gamename}.json"
    if not os.path.exists(game_data_path):
        logger.error("未找到存档，请检查存档是否存在。")
        return None

    game_builder: Optional[GameBuilder] = GameBuilder(gamename, version, runtimedir, data_base_system)
    if game_builder is None:
        logger.error("WorldDataBuilder初始化失败。")
        return None
    
    if not game_builder.loadfile(game_data_path, True):
        logger.error("World.json版本不匹配，请检查版本号。")
        return None
    
    game_builder.build()
    return game_builder
#######################################################################################################################################
## 创建RPG Game
def _create_rpg_game(worldname: str, chaosengineering: Optional[IChaosEngineering], data_base_system: DataBaseSystem) -> RPGGame:

    # 依赖注入的特殊系统
    file_system = FileSystem("file_system， Because it involves IO operations, an independent system is more convenient.")
    memory_system = MemorySystem("memorey_system， Because it involves IO operations, an independent system is more convenient.")
    agent_connect_system = AgentConnectSystem("agent_connect_system， Because it involves net operations, an independent system is more convenient.")
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
    rpggame = RPGGame(worldname, context)
    return rpggame
#######################################################################################################################################
## 创建RPG Game + 读取数据
def create_rpg_game(gamename: str) -> Optional[RPGGame]:
    # 通过依赖注入的方式创建数据系统
    data_base_system = DataBaseSystem("test!!! data_base_system，it is a system that stores all the origin data from the settings.")
    game_builder = _read_and_build_game_data(gamename, data_base_system)
    if game_builder is None:
        logger.error("create_world_data_builder 失败。")
        return None
    
    # 创建游戏 + 专门的混沌工程系统
    chaos_engineering_system = ChaosBuddingWorld("ChaosBuddingWorld")
    rpggame = _create_rpg_game(gamename, chaos_engineering_system, game_builder.data_base_system)
    if rpggame is None:
        logger.error("_create_rpg_game 失败。")
        return None
    
    # 执行创建游戏的所有动作
    rpggame.create_game(game_builder)
    return rpggame
#######################################################################################################################################