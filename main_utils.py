import os
from typing import Optional
from loguru import logger
from auxiliary.builders import WorldDataBuilder
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

def user_input_pre_command(input_val: str, split_str: str)-> str:
    if split_str in input_val:
        return input_val.split(split_str)[1].strip()
    return input_val


### 临时的，写死创建budding_world
def read_world_data(worldname: str, data_base_system: DataBaseSystem) -> Optional[WorldDataBuilder]:
    #先写死！！！！
    version = 'ewan'
    runtimedir = f"./budding_world/gen_runtimes/"
    worlddata: str = f"{runtimedir}{worldname}.json"
    if not os.path.exists(worlddata):
        logger.error("未找到存档，请检查存档是否存在。")
        return None

    worldbuilder: Optional[WorldDataBuilder] = WorldDataBuilder(worldname, version, runtimedir, data_base_system)
    if worldbuilder is None:
        logger.error("WorldDataBuilder初始化失败。")
        return None
    
    if not worldbuilder.check_version_valid(worlddata):
        logger.error("World.json版本不匹配，请检查版本号。")
        return None
    
    worldbuilder.build()
    return worldbuilder

##
def create_rpg_game(worldname: str, chaosengineering: Optional[IChaosEngineering], data_base_system: DataBaseSystem) -> RPGGame:

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


##
def create_rpg_game_then_build(worldname:str) -> Optional[RPGGame]:
    # 读取世界资源文件
    #worldname = "World2"#input("请输入要进入的世界名称(必须与自动化创建的名字一致):")
    # 通过依赖注入的方式创建数据系统
    data_base_system = DataBaseSystem("test!!! data_base_system，it is a system that stores all the origin data from the settings.")
    worlddata = read_world_data(worldname, data_base_system)
    if worlddata is None:
        logger.error("create_world_data_builder 失败。")
        return None
    
    # 创建游戏 + 专门的混沌工程系统
    chaos_engineering_system = ChaosBuddingWorld("ChaosBuddingWorld")
    #chaos_engineering_system = None
    rpggame = create_rpg_game(worldname, chaos_engineering_system, worlddata.data_base_system)
    if rpggame is None:
        logger.error("create_rpg_game 失败。")
        return None
    
    # 创建世界
    rpggame.createworld(worlddata)
    return rpggame

