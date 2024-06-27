import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
import pandas as pd
from loguru import logger
from pandas.core.frame import DataFrame
from typing import Dict
from game_sample.excel_data import ExcelDataActor, ExcelDataStage, ExcelDataProp, ExcelDataWorldSystem
from pathlib import Path
from game_sample.utils import read_system_prompt_md, read_agentpy_template
from game_sample.configuration import GAME_NAME

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
                                row["agentpy_template"],
                                row["body"])
        #
        system_prompt_path = Path(GAME_NAME) / excel_actor._sys_prompt_template_path
        assert system_prompt_path.exists(), f"File not found: {system_prompt_path}"
        excel_actor.gen_sys_prompt(read_system_prompt_md(system_prompt_path))
        excel_actor.write_sys_prompt()
        #
        agentpy_template_path = Path(GAME_NAME) / excel_actor._agentpy_template_path
        assert agentpy_template_path.exists(), f"File not found: {agentpy_template_path}"
        excel_actor.gen_agentpy(read_agentpy_template(agentpy_template_path))
        excel_actor.write_agentpy()
        #
        output[excel_actor._name] = excel_actor
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
        #
        system_prompt_path = Path(GAME_NAME) / excel_stage._sys_prompt_template_path
        assert system_prompt_path.exists(), f"File not found: {system_prompt_path}"
        excel_stage.gen_sys_prompt(read_system_prompt_md(system_prompt_path))
        excel_stage.write_sys_prompt()
        #
        agentpy_template_path = Path(GAME_NAME) / excel_stage._agentpy_template_path
        assert agentpy_template_path.exists(), f"File not found: {agentpy_template_path}"
        excel_stage.gen_agentpy(read_agentpy_template(agentpy_template_path))
        excel_stage.write_agentpy()    
        #
        output[excel_stage._name] = excel_stage 
############################################################################################################
def gen_all_world_system(sheet: DataFrame, output: Dict[str, ExcelDataWorldSystem]) -> None:
    ## 读取Excel文件
    for index, row in sheet.iterrows():
        if pd.isna(row["name"]):
            continue
        excel_world_system = ExcelDataWorldSystem(row["name"], 
                                    row["codename"], 
                                    row["description"], 
                                    int(row["PORT"]), 
                                    row["API"], 
                                    row["RAG"], 
                                    row["sys_prompt_template"],
                                    row["agentpy_template"])
        #
        system_prompt_path = Path(GAME_NAME) / excel_world_system._sys_prompt_template_path
        assert system_prompt_path.exists(), f"File not found: {system_prompt_path}"
        excel_world_system.gen_sys_prompt(read_system_prompt_md(system_prompt_path))
        excel_world_system.write_sys_prompt()
        #
        agentpy_template_path = Path(GAME_NAME) / excel_world_system._agentpy_template_path
        assert agentpy_template_path.exists(), f"File not found: {agentpy_template_path}"
        excel_world_system.gen_agentpy(read_agentpy_template(agentpy_template_path))
        excel_world_system.write_agentpy()    
        #
        output[excel_world_system._name] = excel_world_system
############################################################################################################
def gen_all_props(sheet: DataFrame, output: Dict[str, ExcelDataProp]) -> None:
    ## 读取Excel文件
    for index, row in sheet.iterrows():
        if pd.isna(row["name"]):
            continue
        excelprop = ExcelDataProp(  row["name"],
                                    row["codename"],
                                    row["isunique"],
                                    row["description"],
                                    row["RAG"],
                                    row["type"],
                                    row["attributes"],
                                    row["appearance"])
        output[excelprop._name] = excelprop
############################################################################################################
def analyze_actor_relationship(analyze_data: Dict[str, ExcelDataActor]) -> None:
    #先构建
    for _me in analyze_data.values():
        _me._actor_archives.clear()
        for _other in analyze_data.values():
            _me.add_actor_archive(_other._name)

    #再检查
    for _me in analyze_data.values():
        for _other in analyze_data.values():
            if _me.check_actor_archive(_other._name) and not _other.check_actor_archive(_me._name):
                logger.warning(f"{_me._name} mentioned {_other._name}, but {_other._name} did not mention {_me._name}")
############################################################################################################
def analyze_stage_relationship(analyze_stage_data: Dict[str, ExcelDataStage], analyze_actor_data: Dict[str, ExcelDataActor]) -> None:
    for stagename, stagedata in analyze_stage_data.items():
        for actor in analyze_actor_data.values():
            actor._stage_archives.clear()
            actor.add_stage_archive(stagename)
################################################################################################################
def analyze_relationship_between_actors_and_props(analyze_props_data: Dict[str, ExcelDataProp], analyze_actor_data: Dict[str, ExcelDataActor]) -> None:
    #先构建
    for _me in analyze_actor_data.values():
        _me._prop_archives.clear()
        for _others_prop in analyze_props_data.values():
            _me.add_prop_archive(_others_prop._name)
    #再检查
    for _me in analyze_actor_data.values():
        if len(_me._prop_archives) > 0:
            logger.warning(f"{_me._name}: {_me._prop_archives}")
################################################################################################################
def serialization_prop(prop: ExcelDataProp) -> Dict[str, str]:
    output: Dict[str, str] = {}
    output["name"] = prop._name
    output["codename"] = prop._codename
    output["description"] = prop._description
    output["isunique"] = prop._isunique
    output["type"] = prop._type
    output["attributes"] = prop._attributes
    output["appearance"] = prop._appearance
    return output       
################################################################################################################
def proxy_prop(prop: ExcelDataProp) -> Dict[str, str]:
    output: Dict[str, str] = {}
    output['name'] = prop._name
    return output       
################################################################################################################