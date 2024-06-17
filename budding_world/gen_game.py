import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
import pandas as pd
from loguru import logger
from pandas.core.frame import DataFrame
import json
from budding_world.configuration import WORLD_EDITOR_DIR, GAME_NAME, OUTPUT_RUNTIMES_DIR
from budding_world.gen_funcs import (gen_all_actors, gen_all_stages, gen_all_props, analyze_actor_relationship, 
                                analyze_stage_relationship, analyze_relationship_between_actors_and_props, gen_all_world_system)
from budding_world.excel_data import ExcelDataActor, ExcelDataStage, ExcelDataProp, ExcelDataWorldSystem
from budding_world.game_editor import ExcelEditorGame
from typing import List, Dict, Any
 
############################################################################################################
def create_world_editor(sheet_name_as_world_name: str, 
                        actor_data_base: Dict[str, ExcelDataActor],
                        prop_data_base: Dict[str, ExcelDataProp],
                        stage_data_base: Dict[str, ExcelDataStage],
                        world_system_data_base: Dict[str, ExcelDataWorldSystem]) -> ExcelEditorGame:
    ####测试的一个世界编辑
    data_frame: DataFrame = pd.read_excel(f"{GAME_NAME}/{WORLD_EDITOR_DIR}/{GAME_NAME}.xlsx", sheet_name = sheet_name_as_world_name, engine='openpyxl')
    ###费2遍事，就是试试转换成json好使不，其实可以不用直接dataframe做也行
    _2json: str = data_frame.to_json(orient='records', force_ascii=False)
    _2list: List[Any] = json.loads(_2json)
    return ExcelEditorGame(sheet_name_as_world_name, _2list, actor_data_base, prop_data_base, stage_data_base, world_system_data_base)
############################################################################################################
def main() -> None:
    #
    actor_sheet: DataFrame = pd.read_excel(f"{GAME_NAME}/{WORLD_EDITOR_DIR}/{GAME_NAME}.xlsx", sheet_name='Actor', engine='openpyxl')
    stage_sheet: DataFrame = pd.read_excel(f"{GAME_NAME}/{WORLD_EDITOR_DIR}/{GAME_NAME}.xlsx", sheet_name='Stage', engine='openpyxl')
    prop_sheet: DataFrame = pd.read_excel(f"{GAME_NAME}/{WORLD_EDITOR_DIR}/{GAME_NAME}.xlsx", sheet_name='Prop', engine='openpyxl')
    world_system_sheet: DataFrame = pd.read_excel(f"{GAME_NAME}/{WORLD_EDITOR_DIR}/{GAME_NAME}.xlsx", sheet_name='WorldSystem', engine='openpyxl')

    #
    actor_data_base: Dict[str, ExcelDataActor] = {}
    stage_data_base: Dict[str, ExcelDataStage] = {}
    prop_data_base: Dict[str, ExcelDataProp] = {}
    world_system_data_base: Dict[str, ExcelDataWorldSystem] = {}
    
    #分析必要数据
    gen_all_actors(actor_sheet, actor_data_base)
    gen_all_stages(stage_sheet, stage_data_base)
    gen_all_props(prop_sheet, prop_data_base)
    gen_all_world_system(world_system_sheet, world_system_data_base)
    
    #尝试分析之间的关系并做一定的自我检查，这里是例子，实际应用中，可以根据需求做更多的检查
    analyze_actor_relationship(actor_data_base)
    analyze_stage_relationship(stage_data_base, actor_data_base)
    analyze_relationship_between_actors_and_props(prop_data_base, actor_data_base)
    
    #测试这个世界编辑
    sheet_name_as_world_name = input("输入要创建的World的名字(必须对应excel中的sheet名):")
    if sheet_name_as_world_name == "":
        sheet_name_as_world_name = "World3"
        logger.warning(f"使用默认的World名称: {sheet_name_as_world_name}")

    world = create_world_editor(str(sheet_name_as_world_name), actor_data_base, prop_data_base, stage_data_base, world_system_data_base)
    if world is not None:
        world.write(f"{GAME_NAME}/{OUTPUT_RUNTIMES_DIR}/")
############################################################################################################
if __name__ == "__main__":
    main()
