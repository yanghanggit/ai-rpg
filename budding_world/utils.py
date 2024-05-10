import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
import pandas as pd
import os
from loguru import logger
from pandas.core.frame import DataFrame
from typing import Dict
from budding_world.configuration import RAG_FILE
from budding_world.excel_data import ExcelDataNPC, ExcelDataStage, ExcelDataProp


############################################################################################################
def readmd(file_path: str) -> str:
    try:
        file_path = os.getcwd() + file_path
        with open(file_path, 'r', encoding='utf-8') as file:
            md_content = file.read()
            if isinstance(md_content, str):
                return md_content
            else:
                logger.error(f"Failed to read the file:{md_content}")
                return ""
    except FileNotFoundError:
        return f"File not found: {file_path}"
    except Exception as e:
        return f"An error occurred: {e}"
############################################################################################################
def readpy(file_path: str) -> str:
    try:
        file_path = os.getcwd() + file_path
        with  open(file_path, 'r', encoding='utf-8') as file:
            pystr = file.read()
            if isinstance(pystr, str):
                return pystr
            else:
                logger.error(f"Failed to read the file:{pystr}")
                return ""

    except FileNotFoundError:
        return f"File not found: {file_path}"
    except Exception as e:
        return f"An error occurred: {e}"
############################################################################################################




############################################################################################################
def gen_all_npcs(sheet: DataFrame, sys_prompt_template_path: str, agent_template_path: str, output: Dict[str, ExcelDataNPC]) -> None:
    ## 读取Excel文件
    for index, row in sheet.iterrows():
        if pd.isna(row["name"]):
            continue
        excelnpc = ExcelDataNPC(row["name"], row["codename"], row["description"], row["history"], row["GPT_MODEL"], int(row["PORT"]), row["API"], RAG_FILE, row["attributes"])
        if not excelnpc.isvalid():
            #print(f"Invalid row: {excelnpc}")
            continue
        excelnpc.gen_sys_prompt(sys_prompt_template_path)
        excelnpc.write_sys_prompt()
        excelnpc.gen_agentpy(agent_template_path)
        excelnpc.write_agentpy()
        output[excelnpc.name] = excelnpc
############################################################################################################
def gen_all_stages(sheet: DataFrame, sys_prompt_template_path: str, agent_template_path: str, output: Dict[str, ExcelDataStage]) -> None:
    ## 读取Excel文件
    for index, row in sheet.iterrows():
        if pd.isna(row["name"]):
            continue
        excelstage = ExcelDataStage(row["name"], row["codename"], row["description"], row["GPT_MODEL"], int(row["PORT"]), row["API"], RAG_FILE, row["attributes"])
        if not excelstage.isvalid():
            #print(f"Invalid row: {excelstage}")
            continue
        excelstage.gen_sys_prompt(sys_prompt_template_path)
        excelstage.write_sys_prompt()
        excelstage.gen_agentpy(agent_template_path)
        excelstage.write_agentpy()    
        output[excelstage.name] = excelstage 
############################################################################################################
def gen_all_props(sheet: DataFrame, output: Dict[str, ExcelDataProp]) -> None:
    ## 读取Excel文件
    for index, row in sheet.iterrows():
        if pd.isna(row["name"]):
            continue
        excelprop = ExcelDataProp(row["name"], row["codename"], row["isunique"], row["description"], RAG_FILE)
        if not excelprop.isvalid():
            #(f"Invalid row: {excelprop}")
            continue
        output[excelprop.name] = excelprop
############################################################################################################
def analyze_npc_relationship(analyze_data: Dict[str, ExcelDataNPC]) -> None:
    #先构建
    for npc in analyze_data.values():
        npc.mentioned_npcs.clear()
        for other_npc in analyze_data.values():
            npc.add_mentioned_npc(other_npc.name)

    #再检查
    for npc in analyze_data.values():
        for other_npc in analyze_data.values():
            if npc.check_mentioned_npc(other_npc.name) and not other_npc.check_mentioned_npc(npc.name):
                logger.warning(f"{npc.name} mentioned {other_npc.name}, but {other_npc.name} did not mention {npc.name}")
############################################################################################################
def analyze_stage_relationship(analyze_stage_data: Dict[str, ExcelDataStage], analyze_npc_data: Dict[str, ExcelDataNPC]) -> None:
    for stagename, stagedata in analyze_stage_data.items():
        for npc in analyze_npc_data.values():
            npc.mentioned_stages.clear()
            npc.add_mentioned_stage(stagename)
################################################################################################################
def analyze_relationship_between_npcs_and_props(analyze_props_data: Dict[str, ExcelDataProp], analyze_npc_data: Dict[str, ExcelDataNPC]) -> None:
    #先构建
    for npc in analyze_npc_data.values():
        npc.mentioned_props.clear()
        for other_prop in analyze_props_data.values():
            npc.add_mentioned_prop(other_prop.name)
    #再检查
    for npc in analyze_npc_data.values():
        if len(npc.mentioned_props) > 0:
            logger.warning(f"{npc.name}: {npc.mentioned_props}")
################################################################################################################
def serialization_prop(prop: ExcelDataProp) -> Dict[str, str]:
    dict: Dict[str, str] = {}
    dict['name'] = prop.name
    dict['codename'] = prop.codename
    dict['description'] = prop.description
    dict['isunique'] = prop.isunique
    return dict       
################################################################################################################