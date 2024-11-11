import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
import pandas as pd
from loguru import logger
from pandas.core.frame import DataFrame
import json

import game_sample.configuration as configuration
import game_sample.gen_funcs as gen_funcs
from game_sample.prop_data import ExcelDataProp
from game_sample.world_system_data import ExcelDataWorldSystem
from game_sample.stage_data import ExcelDataStage
from game_sample.game_editor import ExcelEditorGame
from typing import List, Dict, Any
from game_sample.actor_data import ExcelDataActor
from game_sample.gen_sys_prompt_templates import gen_sys_prompt_templates
import shutil
import rpg_game.rpg_game_config as rpg_game_config
import game_sample.utils as utils


############################################################################################################
def create_game_editor(
    sheet_name_as_game_name: str,
    version: str,
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
        version,
        list_data,
        actor_data_base,
        prop_data_base,
        stage_data_base,
        world_system_data_base,
    )


############################################################################################################
def main(game_names: List[str]) -> None:

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
    gen_funcs.gen_actors_data_base(actor_sheet, actor_data_base)
    gen_funcs.gen_stages_data_base(stage_sheet, stage_data_base)
    gen_funcs.gen_prop_data_base(prop_sheet, prop_data_base)
    gen_funcs.gen_world_system_data_base(world_system_sheet, world_system_data_base)

    # 尝试分析之间的关系并做一定的自我检查，这里是例子，实际应用中，可以根据需求做更多的检查
    gen_funcs.build_actor_relationships(actor_data_base)
    gen_funcs.build_stage_relationship(stage_data_base, actor_data_base)
    gen_funcs.build_relationship_between_actors_and_props(
        prop_data_base, actor_data_base
    )

    gen_games = game_names.copy()

    # 测试这个世界编辑
    if len(game_names) == 0:
        input_target_game_name = input(
            "输入要创建的World的名字(必须对应excel中的sheet名):"
        )
        if input_target_game_name != "":
            gen_games.append(input_target_game_name)

    ret_gen_games: List[ExcelEditorGame] = []

    # 创建GameEditor
    for input_target_game_name in gen_games:
        game_editor = create_game_editor(
            str(input_target_game_name),
            rpg_game_config.CHECK_GAME_RESOURCE_VERSION,
            actor_data_base,
            prop_data_base,
            stage_data_base,
            world_system_data_base,
        )
        assert game_editor is not None, "创建GameEditor失败"
        if game_editor is not None:

            ret_gen_games.append(game_editor)

            if game_editor.write(configuration.GAME_SAMPLE_OUT_PUT_GAME_DIR) > 0:
                logger.warning(f"game_editor.write: {input_target_game_name}")

            if (
                game_editor.write_agents_config(
                    configuration.GAME_SAMPLE_OUT_PUT_GAME_DIR
                )
                > 0
            ):
                logger.warning(f"game_editor.write_agents: {input_target_game_name}")

    # 生成games_config
    all_games_config_model = gen_funcs.gen_games_config(ret_gen_games)
    if all_games_config_model is not None:
        utils.write_text_file(
            configuration.GAME_SAMPLE_OUT_PUT_GAME_DIR,
            f"config.json",
            all_games_config_model.model_dump_json(),
        )

    # game最后拷贝到项目根部
    if rpg_game_config.ROOT_GEN_GAMES_DIR.exists():
        shutil.rmtree(rpg_game_config.ROOT_GEN_GAMES_DIR)

    shutil.copytree(
        configuration.GAME_SAMPLE_OUT_PUT_GAME_DIR,
        rpg_game_config.ROOT_GEN_GAMES_DIR,
        dirs_exist_ok=True,
    )

    # agentpy最后拷贝到项目根部
    final_gen_agents_path = (
        rpg_game_config.ROOT_GEN_AGENTS_DIR
        / rpg_game_config.CHECK_GAME_RESOURCE_VERSION
    )
    if final_gen_agents_path.exists():
        shutil.rmtree(final_gen_agents_path)
    final_gen_agents_path.mkdir(parents=True, exist_ok=True)

    shutil.copytree(
        configuration.GAME_SAMPLE_OUT_PUT_AGENT_DIR,
        final_gen_agents_path,
        dirs_exist_ok=True,
    )


############################################################################################################
if __name__ == "__main__":
    main(["World1", "World2", "World3"])
