import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
import pandas as pd
from loguru import logger
from pandas.core.frame import DataFrame
from typing import Dict, List
from game_sample.prop_data import ExcelDataProp
from game_sample.world_system_data import ExcelDataWorldSystem
from game_sample.stage_data import ExcelDataStage
from pathlib import Path
import game_sample.utils
from game_sample.actor_data import ExcelDataActor
from game_sample.game_editor import ExcelEditorGame
import game_sample.configuration as configuration
from my_models.config_models import AllGamesConfigModel, GameConfigModel


############################################################################################################
def gen_actors_data_base(sheet: DataFrame, output: Dict[str, ExcelDataActor]) -> None:
    ## 读取Excel文件
    for index, row in sheet.iterrows():
        if pd.isna(row["name"]):
            continue

        excel_actor = ExcelDataActor(row)
        #
        system_prompt_path = (
            configuration.GAME_SAMPLE_DIR / excel_actor.sys_prompt_template_path
        )
        assert system_prompt_path.exists(), f"File not found: {system_prompt_path}"
        excel_actor.gen_sys_prompt(game_sample.utils.read_text_file(system_prompt_path))
        excel_actor.write_sys_prompt()
        #
        agentpy_template_path = (
            configuration.GAME_SAMPLE_DIR / excel_actor.agentpy_template_path
        )
        assert (
            agentpy_template_path.exists()
        ), f"File not found: {agentpy_template_path}"
        excel_actor.gen_agentpy(game_sample.utils.read_text_file(agentpy_template_path))
        excel_actor.write_agentpy()
        #
        output[excel_actor.name] = excel_actor


############################################################################################################
def gen_stages_data_base(sheet: DataFrame, output: Dict[str, ExcelDataStage]) -> None:
    ## 读取Excel文件
    for index, row in sheet.iterrows():
        if pd.isna(row["name"]):
            continue

        excel_stage = ExcelDataStage(row)
        #
        system_prompt_path = (
            configuration.GAME_SAMPLE_DIR / excel_stage.sys_prompt_template_path
        )
        assert system_prompt_path.exists(), f"File not found: {system_prompt_path}"
        excel_stage.gen_sys_prompt(game_sample.utils.read_text_file(system_prompt_path))
        excel_stage.write_sys_prompt()
        #
        agentpy_template_path = (
            configuration.GAME_SAMPLE_DIR / excel_stage.agentpy_template_path
        )
        assert (
            agentpy_template_path.exists()
        ), f"File not found: {agentpy_template_path}"
        excel_stage.gen_agentpy(game_sample.utils.read_text_file(agentpy_template_path))
        excel_stage.write_agentpy()
        #
        output[excel_stage.name] = excel_stage


############################################################################################################
def gen_world_system_data_base(
    sheet: DataFrame, output: Dict[str, ExcelDataWorldSystem]
) -> None:
    ## 读取Excel文件
    for index, row in sheet.iterrows():
        if pd.isna(row["name"]):
            continue

        excel_world_system = ExcelDataWorldSystem(row)
        #
        system_prompt_path = (
            configuration.GAME_SAMPLE_DIR / excel_world_system.sys_prompt_template_path
        )
        assert system_prompt_path.exists(), f"File not found: {system_prompt_path}"
        excel_world_system.gen_sys_prompt(
            game_sample.utils.read_text_file(system_prompt_path)
        )
        excel_world_system.write_sys_prompt()
        #
        agentpy_template_path = (
            configuration.GAME_SAMPLE_DIR / excel_world_system.agentpy_template_path
        )
        assert (
            agentpy_template_path.exists()
        ), f"File not found: {agentpy_template_path}"
        excel_world_system.gen_agentpy(
            game_sample.utils.read_text_file(agentpy_template_path)
        )
        excel_world_system.write_agentpy()
        #
        output[excel_world_system.name] = excel_world_system


############################################################################################################
def gen_prop_data_base(sheet: DataFrame, output: Dict[str, ExcelDataProp]) -> None:
    ## 读取Excel文件
    for index, row in sheet.iterrows():
        if pd.isna(row["name"]):
            continue
        excelprop = ExcelDataProp(row)
        output[excelprop.name] = excelprop


############################################################################################################
def build_actor_relationships(analyze_data: Dict[str, ExcelDataActor]) -> None:
    # 先构建
    for _me in analyze_data.values():
        _me._actor_archives.clear()
        for _other in analyze_data.values():
            _me.add_actor_archive(_other.name)

    # 再检查
    for _me in analyze_data.values():
        for _other in analyze_data.values():
            if _me.has_actor_in_archives(
                _other.name
            ) and not _other.has_actor_in_archives(_me.name):
                logger.warning(
                    f"{_me.name} mentioned {_other.name}, but {_other.name} did not mention {_me.name}"
                )


############################################################################################################
def build_stage_relationship(
    analyze_stage_data: Dict[str, ExcelDataStage],
    analyze_actor_data: Dict[str, ExcelDataActor],
) -> None:
    for stage_name, stage_data in analyze_stage_data.items():
        for actor in analyze_actor_data.values():
            actor._stage_archives.clear()
            actor.add_stage_archive(stage_name)


################################################################################################################
def build_relationship_between_actors_and_props(
    analyze_props_data: Dict[str, ExcelDataProp],
    analyze_actor_data: Dict[str, ExcelDataActor],
) -> None:
    # 先构建
    for _me in analyze_actor_data.values():
        _me._prop_archives.clear()
        for _others_prop in analyze_props_data.values():
            _me.add_prop_archive(_others_prop.name)
    # 再检查
    for _me in analyze_actor_data.values():
        if len(_me._prop_archives) > 0:
            logger.warning(f"{_me.name}: {_me._prop_archives}")


################################################################################################################
def gen_games_config(gen_games: List[ExcelEditorGame]) -> AllGamesConfigModel:

    ret: AllGamesConfigModel = AllGamesConfigModel()

    for game_editor in gen_games:

        one_game_config = GameConfigModel()
        one_game_config.game_name = game_editor._name
        one_game_config.about_game = game_editor.about_game

        for player in game_editor.editor_players:
            one_game_config.players.setdefault(player.name, "")

        ret.game_configs.append(one_game_config)

    return ret


################################################################################################################
