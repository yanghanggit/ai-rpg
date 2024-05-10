import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
import pandas as pd
from loguru import logger
from pandas.core.frame import DataFrame
import json
from budding_world.configuration import WORLD_EDITOR_DIR, GAME_NAME, TEMPLATE_DIR, GPT_AGENT_TEMPLATE_FILE, NPC_SYS_PROMPT_TEMPLATE_FILE, STAGE_SYS_PROMPT_TEMPLATE_FILE, OUTPUT_RUNTIMES_DIR
from budding_world.utils import (readmd, readpy, gen_all_npcs, gen_all_stages, gen_all_props, analyze_npc_relationship, 
                                     analyze_stage_relationship, analyze_relationship_between_npcs_and_props)
from budding_world.excel_data import ExcelDataNPC, ExcelDataStage, ExcelDataProp
from budding_world.world_editor import ExcelEditorWorld
from typing import List, Dict, Any
 
############################################################################################################
def create_world_editor(sheet_name_as_world_name: str, 
                        npc_data_base: Dict[str, ExcelDataNPC],
                        prop_data_base: Dict[str, ExcelDataProp],
                        stage_data_base: Dict[str, ExcelDataStage]) -> ExcelEditorWorld:
    ####测试的一个世界编辑
    data_frame: DataFrame = pd.read_excel(f"{GAME_NAME}/{WORLD_EDITOR_DIR}/{GAME_NAME}.xlsx", sheet_name = sheet_name_as_world_name, engine='openpyxl')
    ###费2遍事，就是试试转换成json好使不，其实可以不用直接dataframe做也行
    _2json: str = data_frame.to_json(orient='records', force_ascii=False)
    _2list: List[Any] = json.loads(_2json)
    return ExcelEditorWorld(sheet_name_as_world_name, _2list, npc_data_base, prop_data_base, stage_data_base)
############################################################################################################
def main() -> None:

    #
    npc_sys_prompt_template_content: str = readmd(f"/{GAME_NAME}/{TEMPLATE_DIR}/{NPC_SYS_PROMPT_TEMPLATE_FILE}")
    stage_sys_prompt_template_content: str = readmd(f"/{GAME_NAME}/{TEMPLATE_DIR}/{STAGE_SYS_PROMPT_TEMPLATE_FILE}")
    gpt_agent_template_content: str = readpy(f"/{GAME_NAME}/{TEMPLATE_DIR}/{GPT_AGENT_TEMPLATE_FILE}")

    #
    npc_sheet: DataFrame = pd.read_excel(f"{GAME_NAME}/{WORLD_EDITOR_DIR}/{GAME_NAME}.xlsx", sheet_name='NPC', engine='openpyxl')
    stage_sheet: DataFrame = pd.read_excel(f"{GAME_NAME}/{WORLD_EDITOR_DIR}/{GAME_NAME}.xlsx", sheet_name='Stage', engine='openpyxl')
    prop_sheet: DataFrame = pd.read_excel(f"{GAME_NAME}/{WORLD_EDITOR_DIR}/{GAME_NAME}.xlsx", sheet_name='Prop', engine='openpyxl')

    #
    npc_data_base: Dict[str, ExcelDataNPC] = {}
    stage_data_base: Dict[str, ExcelDataStage] = {}
    prop_data_base: Dict[str, ExcelDataProp] = {}
    
    #分析必要数据
    gen_all_npcs(npc_sheet, npc_sys_prompt_template_content, gpt_agent_template_content, npc_data_base)
    gen_all_stages(stage_sheet, stage_sys_prompt_template_content, gpt_agent_template_content, stage_data_base)
    gen_all_props(prop_sheet, prop_data_base)
    
    #尝试分析之间的关系并做一定的自我检查，这里是例子，实际应用中，可以根据需求做更多的检查
    analyze_npc_relationship(npc_data_base)
    analyze_stage_relationship(stage_data_base, npc_data_base)
    analyze_relationship_between_npcs_and_props(prop_data_base, npc_data_base)
    
    #测试这个世界编辑
    sheet_name_as_world_name = input("输入要创建的World的名字(必须对应excel中的sheet名):")
    if sheet_name_as_world_name == "":
        sheet_name_as_world_name = "World2"
        logger.warning(f"使用默认的World名称: {sheet_name_as_world_name}")

    world = create_world_editor(str(sheet_name_as_world_name), npc_data_base, prop_data_base, stage_data_base)
    if world is not None:
        world.write(f"{GAME_NAME}/{OUTPUT_RUNTIMES_DIR}/")
############################################################################################################
if __name__ == "__main__":
    main()
