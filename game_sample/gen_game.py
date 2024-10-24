import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
import pandas as pd
from loguru import logger
from pandas.core.frame import DataFrame
import json

import game_sample.configuration as configuration
from game_sample.gen_funcs import (
    gen_actors_data_base,
    gen_stages_data_base,
    gen_prop_data_base,
    build_actor_relationships,
    build_stage_relationship,
    build_relationship_between_actors_and_props,
    gen_world_system_data_base,
)
from game_sample.excel_data_prop import ExcelDataProp
from game_sample.excel_data_world_system import ExcelDataWorldSystem
from game_sample.excel_data_stage import ExcelDataStage
from game_sample.game_editor import ExcelEditorGame
from typing import List, Dict, Any, Set
from game_sample.excel_data_actor import ExcelDataActor
from game_sample.gen_sys_prompt_templates import gen_sys_prompt_templates
from rpg_game.rpg_game_config import GAME_NAMES
import shutil
import rpg_game.rpg_game_config as rpg_game_config


############################################################################################################
def create_game_editor(
    sheet_name_as_game_name: str,
    actor_data_base: Dict[str, ExcelDataActor],
    prop_data_base: Dict[str, ExcelDataProp],
    stage_data_base: Dict[str, ExcelDataStage],
    world_system_data_base: Dict[str, ExcelDataWorldSystem],
) -> ExcelEditorGame:
    ####测试的一个世界编辑
    data_frame: DataFrame = pd.read_excel(
        configuration.GAME_SAMPLE_EXCEL_FILE_PATH,
        sheet_name=sheet_name_as_game_name,
        engine="openpyxl",
    )
    ###费2遍事，就是试试转换成json好使不，其实可以不用直接dataframe做也行
    json_data: str = data_frame.to_json(orient="records", force_ascii=False)
    list_data: List[Any] = json.loads(json_data)
    return ExcelEditorGame(
        sheet_name_as_game_name,
        "0.0.1",
        list_data,
        actor_data_base,
        prop_data_base,
        stage_data_base,
        world_system_data_base,
    )


############################################################################################################
def main(game_names: Set[str]) -> None:

    actor_sheet: DataFrame = pd.read_excel(
        configuration.GAME_SAMPLE_EXCEL_FILE_PATH,
        sheet_name=configuration.ACTOR_SHEET_NAME,
        engine="openpyxl",
    )
    stage_sheet: DataFrame = pd.read_excel(
        configuration.GAME_SAMPLE_EXCEL_FILE_PATH,
        sheet_name=configuration.STAGE_SHEET_NAME,
        engine="openpyxl",
    )
    prop_sheet: DataFrame = pd.read_excel(
        configuration.GAME_SAMPLE_EXCEL_FILE_PATH,
        sheet_name=configuration.PROP_SHEET_NAME,
        engine="openpyxl",
    )
    world_system_sheet: DataFrame = pd.read_excel(
        configuration.GAME_SAMPLE_EXCEL_FILE_PATH,
        sheet_name=configuration.WORLD_SYSTEM_SHEET_NAME,
        engine="openpyxl",
    )

    #
    actor_data_base: Dict[str, ExcelDataActor] = {}
    stage_data_base: Dict[str, ExcelDataStage] = {}
    prop_data_base: Dict[str, ExcelDataProp] = {}
    world_system_data_base: Dict[str, ExcelDataWorldSystem] = {}

    # 准备基础数据
    gen_sys_prompt_templates()

    # 分析必要数据
    gen_actors_data_base(actor_sheet, actor_data_base)
    gen_stages_data_base(stage_sheet, stage_data_base)
    gen_prop_data_base(prop_sheet, prop_data_base)
    gen_world_system_data_base(world_system_sheet, world_system_data_base)

    # 尝试分析之间的关系并做一定的自我检查，这里是例子，实际应用中，可以根据需求做更多的检查
    build_actor_relationships(actor_data_base)
    build_stage_relationship(stage_data_base, actor_data_base)
    build_relationship_between_actors_and_props(prop_data_base, actor_data_base)

    gen_games = game_names.copy()

    # 测试这个世界编辑
    if len(game_names) == 0:
        sheet_name_as_game_name = input(
            "输入要创建的World的名字(必须对应excel中的sheet名):"
        )
        if sheet_name_as_game_name != "":
            gen_games.add(sheet_name_as_game_name)

    # 创建GameEditor
    for sheet_name_as_game_name in gen_games:
        game_editor = create_game_editor(
            str(sheet_name_as_game_name),
            actor_data_base,
            prop_data_base,
            stage_data_base,
            world_system_data_base,
        )
        assert game_editor is not None, "创建GameEditor失败"
        if game_editor is not None:

            if game_editor.write(configuration.OUT_PUT_GEN_GAMES_DIR) > 0:
                logger.warning(f"game_editor.write: {sheet_name_as_game_name}")

            if game_editor.write_agents(configuration.OUT_PUT_GEN_GAMES_DIR) > 0:
                logger.warning(f"game_editor.write_agents: {sheet_name_as_game_name}")

    root_gen_games_dir = rpg_game_config.GEN_GAMES_DIR
    if root_gen_games_dir.exists():
        shutil.rmtree(root_gen_games_dir)
    shutil.copytree(
        configuration.OUT_PUT_GEN_GAMES_DIR, root_gen_games_dir, dirs_exist_ok=True
    )


############################################################################################################
if __name__ == "__main__":
    main(set(GAME_NAMES))
