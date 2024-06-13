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
from budding_world.excel_data import ExcelDataActor, ExcelDataStage, ExcelDataProp


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
def gen_all_actors(sheet: DataFrame, output: Dict[str, ExcelDataActor]) -> None:
    ## 读取Excel文件
    for index, row in sheet.iterrows():
        if pd.isna(row["name"]):
            continue

        #
        excel_actor = ExcelDataActor(row["name"], 
                                row["codename"], 
                                row["description"], 
                                row['conversation_example'],
                                #row["GPT_MODEL"], 
                                int(row["PORT"]), 
                                row["API"], 
                                row["RAG"], 
                                row["sys_prompt_template"],
                                row["agentpy_template"])
        

        excel_actor.gen_sys_prompt(readmd(excel_actor._sys_prompt_template_path))
        excel_actor.write_sys_prompt()
        excel_actor.gen_agentpy(readpy(excel_actor._agentpy_template_path))
        excel_actor.write_agentpy()
        output[excel_actor.name] = excel_actor
############################################################################################################
def gen_all_stages(sheet: DataFrame, output: Dict[str, ExcelDataStage]) -> None:
    ## 读取Excel文件
    for index, row in sheet.iterrows():
        if pd.isna(row["name"]):
            continue
        excel_stage = ExcelDataStage(row["name"], 
                                    row["codename"], 
                                    row["description"], 
                                    #row["GPT_MODEL"], 
                                    int(row["PORT"]), 
                                    row["API"], 
                                    row["RAG"], 
                                    row["sys_prompt_template"],
                                    row["agentpy_template"])

        excel_stage.gen_sys_prompt(readmd(excel_stage._sys_prompt_template_path))
        excel_stage.write_sys_prompt()
        excel_stage.gen_agentpy(readpy(excel_stage._agentpy_template_path))
        excel_stage.write_agentpy()    
        output[excel_stage.name] = excel_stage 
############################################################################################################
def gen_all_props(sheet: DataFrame, output: Dict[str, ExcelDataProp]) -> None:
    ## 读取Excel文件
    for index, row in sheet.iterrows():
        if pd.isna(row["name"]):
            continue
        excelprop = ExcelDataProp(row["name"], row["codename"], row["isunique"], row["description"], row["RAG"], row["type"], str(row["attributes"]))
        output[excelprop.name] = excelprop
############################################################################################################
def analyze_actor_relationship(analyze_data: Dict[str, ExcelDataActor]) -> None:
    #先构建
    for _me in analyze_data.values():
        _me.mentioned_actors.clear()
        for _other in analyze_data.values():
            _me.add_mentioned_actor(_other.name)

    #再检查
    for _me in analyze_data.values():
        for _other in analyze_data.values():
            if _me.check_mentioned_actor(_other.name) and not _other.check_mentioned_actor(_me.name):
                logger.warning(f"{_me.name} mentioned {_other.name}, but {_other.name} did not mention {_me.name}")
############################################################################################################
def analyze_stage_relationship(analyze_stage_data: Dict[str, ExcelDataStage], analyze_actor_data: Dict[str, ExcelDataActor]) -> None:
    for stagename, stagedata in analyze_stage_data.items():
        for actor in analyze_actor_data.values():
            actor.mentioned_stages.clear()
            actor.add_mentioned_stage(stagename)
################################################################################################################
def analyze_relationship_between_actors_and_props(analyze_props_data: Dict[str, ExcelDataProp], analyze_actor_data: Dict[str, ExcelDataActor]) -> None:
    #先构建
    for _me in analyze_actor_data.values():
        _me.mentioned_props.clear()
        for _others_prop in analyze_props_data.values():
            _me.add_mentioned_prop(_others_prop.name)
    #再检查
    for _me in analyze_actor_data.values():
        if len(_me.mentioned_props) > 0:
            logger.warning(f"{_me.name}: {_me.mentioned_props}")
################################################################################################################
def serialization_prop(prop: ExcelDataProp) -> Dict[str, str]:
    output: Dict[str, str] = {}
    output['name'] = prop.name
    output['codename'] = prop.codename
    output['description'] = prop.description
    output['isunique'] = prop.isunique
    output['type'] = prop.type
    output['attributes'] = prop.raw_attributes
    return output       
################################################################################################################
def proxy_prop(prop: ExcelDataProp) -> Dict[str, str]:
    output: Dict[str, str] = {}
    output['name'] = prop.name
    return output       
################################################################################################################