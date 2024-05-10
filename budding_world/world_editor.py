import sys
from pathlib import Path
# 将项目根目录添加到sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
import os
from loguru import logger
import json
from typing import List, Dict, Any
from budding_world.excel_data import ExcelDataNPC, ExcelDataStage, ExcelDataProp
from budding_world.npc_editor import ExcelEditorNPC
from budding_world.stage_editor import ExcelEditorStage


################################################################################################################
class ExcelEditorWorld:
    def __init__(self, worldname: str, data: List[Any], npc_data_base: Dict[str, ExcelDataNPC], prop_data_base: Dict[str, ExcelDataProp], stage_data_base: Dict[str, ExcelDataStage]) -> None:
        # 根数据
        self.name: str = worldname
        self.data: List[Any] = data
        self.npc_data_base = npc_data_base
        self.prop_data_base = prop_data_base
        self.stage_data_base = stage_data_base

        #笨一点，先留着吧。。。
        self.raw_worldnpcs: List[Any] = []
        self.raw_playernpcs: List[Any] = []
        self.raw_npcs: List[Any] = []
        self.raw_stages: List[Any] = []
        #真正的构建数据
        self.editor_worldnpcs: List[ExcelEditorNPC] = []
        self.editor_playernpcs: List[ExcelEditorNPC] = []
        self.editor_npcs: List[ExcelEditorNPC] = []
        self.editor_stages: List[ExcelEditorStage] = []
        ##把数据分类
        self.categorizedata()
        ##根据分类各种处理。。。
        self.create_editor_worldnpcs()
        self.create_editor_playernpcs()
        self.create_editor_npcs()
        self.create_editor_stages()

    #先将数据分类
    def categorizedata(self) -> None:
        for item in self.data:
            if item["type"] == "World":
                self.raw_worldnpcs.append(item)
            elif item["type"] == "Player":
                self.raw_playernpcs.append(item)
            elif item["type"] == "NPC":
                self.raw_npcs.append(item)
            elif item["type"] == "Stage":
                self.raw_stages.append(item)

    def create_editor_worldnpcs(self) -> None:
        for item in self.raw_worldnpcs:
            editor_npc = ExcelEditorNPC(item, self.npc_data_base, self.prop_data_base)
            self.editor_worldnpcs.append(editor_npc)
            logger.info(editor_npc)

    def create_editor_playernpcs(self) -> None:
        for item in self.raw_playernpcs:
            editor_npc = ExcelEditorNPC(item, self.npc_data_base, self.prop_data_base)
            self.editor_playernpcs.append(editor_npc)
            logger.info(editor_npc)
       
    def create_editor_npcs(self) -> None:
        for item in self.raw_npcs:
            editor_npc = ExcelEditorNPC(item, self.npc_data_base, self.prop_data_base)
            self.editor_npcs.append(editor_npc)
            logger.info(editor_npc)

    def create_editor_stages(self) -> None:
        for item in self.raw_stages:
            editor_stage = ExcelEditorStage(item, self.npc_data_base, self.prop_data_base, self.stage_data_base)
            self.editor_stages.append(editor_stage)
            logger.info(editor_stage)

    def __str__(self) -> str:
        return f"ExcelEditorWorld({self.name})"

    #最后生成JSON
    def serialization(self) -> Dict[str, Any]:
        logger.warning("Building world..., 需要检查，例如NPC里出现了，但是场景中没有出现，那就是错误。一顿关联，最后生成JSON文件")
        dict: Dict[str, Any] = {}
        dict["worldnpcs"] = [editor_npc.serialization() for editor_npc in self.editor_worldnpcs]
        dict["playernpcs"] = [editor_npc.serialization() for editor_npc in self.editor_playernpcs]
        dict["npcs"] = [editor_npc.serialization() for editor_npc in self.editor_npcs]
        dict["stages"] = [editor_stage.serialization() for editor_stage in self.editor_stages]
        version_sign = input("请输入版本号:")
        if version_sign == "":
            version_sign = "ewan"
            logger.warning(f"使用默认的版本号: {version_sign}")
        dict["version"] = version_sign
        return dict
    
    def write(self, directory: str) -> bool:
        builddata = self.serialization()    
        logger.warning(builddata)
        builddata_json = json.dumps(builddata, indent=4, ensure_ascii = False)
        try:
            filename = f"{self.name}.json"
            path = os.path.join(directory, filename)
            # 确保目录存在
            os.makedirs(directory, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as file:
                file.write(builddata_json)
                return True
        except Exception as e:
            logger.error(f"An error occurred: {e}") 
        return False


