from typing import Any, Optional, Union
from loguru import logger
import json

class Condition:
    def __init__(self, name: str, type: str, prop_name: str) -> None:
        self.name = name
        self.type = type
        self.prop_name = prop_name


class Prop:
    def __init__(self, name: str, codename: str, description: str, is_unique: bool) -> None:
        self.name = name
        self.codename = codename
        self.description = description
        self.is_unique = is_unique

class NPC:
    def __init__(self, name: str, codename: str, url: str, memory: str, props: set[Prop] = set()) -> None:
        self.name = name
        self.codename = codename
        self.url = url
        self.memory = memory
        self.props: set[Prop] = props


class Stage:
    def __init__(self, name: str, codename: str, description: str, url: str, memory: str, entry_conditions: list[Condition], exit_conditions: list[Condition], npcs: list[NPC], props: set[Prop]) -> None:
        self.name = name
        self.codename = codename
        self.description = description
        self.url = url
        self.memory = memory
        self.entry_conditions: list[Condition] = entry_conditions
        self.exit_conditions: list[Condition] = exit_conditions
        self.npcs: list[NPC] = npcs
        self.props: set[Prop] = props

class WorldDataBuilder:
    def __init__(self) -> None:
        # version必须与生成的world.json文件中的version一致
        self.version = 'ewan'
        self.data: dict[str, Any] = dict()
        self.admin_npc_builder = AdminNpcBuilder()
        self.player_npc_builder = PlayerNpcBuilder()
        self.npc_buidler = NpcBuilder()
        self.stage_builder = StageBuilder()

    def check_version_valid(self, world_data_path: str) -> bool:
        try:
            with open(world_data_path, 'r') as file:
                data: dict[str, Any] = json.load(file)
                self.data = data
                world_data_version: str = data['version']
            
        except FileNotFoundError:
            logger.exception(f"File {world_data_path} not found.")
            return False
        
        if self.version == world_data_version:
            return True
        else:
            logger.error(f'游戏数据(World.json)与Builder版本不匹配，请检查。')
            return False

    def build(self) -> None:
        self.admin_npc_builder.build(self.data)
        self.player_npc_builder.build(self.data)
        self.npc_buidler.build(self.data)
        self.stage_builder.build(self.data)

class StageBuilder:
    def __init__(self) -> None:
        self.data: Optional[dict[str, Any]] = None
        self.stages: list[Stage] = []

    def __str__(self) -> str:
        return f"StageBuilder: {self.data}"       

    #
    def build(self, json_data: dict[str, Any]) -> None:
        self.data = json_data.get("stages")
        if self.data is not None:
            for stage_data_content in self.data:
                if isinstance(stage_data_content, dict):
                    stage_data = stage_data_content.get("stage")
                    if isinstance(stage_data, dict):
                        stage_name = stage_data.get("name")
                        stage_code_name = stage_data.get("codename")
                        stage_description = stage_data.get("description")
                        stage_url = stage_data.get("url")
                        stage_memory = stage_data.get("memory")
                        entry_conditions_data_in_stage = stage_data.get("entry_conditions")
                        exit_conditions_data_in_stage = stage_data.get("exit_conditions")
                        npcs_data_in_stage = stage_data.get("npcs")
                        props_data_in_stage = stage_data.get("props")
                    if stage_name is not None and stage_code_name is not None and stage_description is not None and stage_url is not None and stage_memory is not None and entry_conditions_data_in_stage is not None and exit_conditions_data_in_stage is not None and npcs_data_in_stage is not None and props_data_in_stage is not None:
                        entry_conditions_in_stage: list[Condition] = []
                        for entry_condition_data in entry_conditions_data_in_stage:
                            if isinstance(entry_condition_data, dict):
                                entry_condition_name = entry_condition_data.get("name")
                                entry_condition_type = entry_condition_data.get("type")
                                entry_condition_prop_name = entry_condition_data.get("propname")
                            if entry_condition_name is not None and entry_condition_type is not None and entry_condition_prop_name is not None:
                                entry_condition: Condition = Condition(entry_condition_name, entry_condition_type, entry_condition_prop_name)
                                entry_conditions_in_stage.append(entry_condition)
                            else:
                                logger.warning(f"StageBuilder: entry condition data is incomplete: {entry_condition_data}")
                        
                        exit_conditions_in_stage: list[Condition] = []
                        for exit_condition_data in exit_conditions_data_in_stage:
                            if isinstance(exit_condition_data, dict):
                                exit_condition_name = exit_condition_data.get("name")
                                exit_condition_type = exit_condition_data.get("type")
                                exit_condition_prop_name = exit_condition_data.get("propname")
                            if exit_condition_name is not None and exit_condition_type is not None and exit_condition_prop_name is not None:
                                exit_condition = Condition(exit_condition_name, exit_condition_type, exit_condition_prop_name)
                                exit_conditions_in_stage.append(exit_condition)
                            else:
                                logger.warning(f"StageBuilder: exit condition data is incomplete: {exit_condition_data}")
       
                        stage = Stage(stage_name, stage_code_name, stage_description, stage_url, stage_memory, entry_conditions_in_stage, exit_conditions_in_stage, npcs_data_in_stage, props_data_in_stage)
                        self.stages.append(stage)
               

class NpcBuilder:
    def __init__(self) -> None:
        self.data: Optional[dict[str, Any]] = None
        self.npcs: list[NPC] = []

    def __str__(self) -> str:
        return f"NpcBuilder: {self.data}"       

    #
    def build(self, json_data: dict[str, Any]) -> None:
        self.data = json_data.get("npcs")
        if self.data is not None:
            for npc_data_content in self.data:
                npc_data = npc_data_content.get("npc")
                npc_name = npc_data.get("name")
                npc_code_name = npc_data.get("codename")
                npc_url = npc_data.get("url")
                npc_memory = npc_data.get("memory")
                
                npc_props_data = npc_data_content.get("props")
                npc_props = set()
                for prop_data in npc_props_data:
                    prop_name = prop_data.get("name")
                    prop_code_name = prop_data.get("codename")
                    prop_description = prop_data.get("description")
                    prop_is_unique = prop_data.get("isunique")
                    if npc_name is not None and prop_name is not None and prop_code_name is not None and prop_description is not None and prop_is_unique is not None:
                        prop = Prop(prop_name, prop_code_name, prop_description, prop_is_unique)
                        npc_props.add(prop)
                    else:
                        logger.warning(f"NpcBuilder: prop data is incomplete: {prop_data}")
                npc = NPC(npc_name, npc_code_name, npc_url, npc_memory, npc_props)
                self.npcs.append(npc)


class PlayerNpcBuilder:
    def __init__(self) -> None:
        self.data: Optional[dict[str, Any]] = None
        self.npcs: list[NPC] = []

    def __str__(self) -> str:
        return f"PlayerNpcBuilder: {self.data}"       

    #
    def build(self, json_data: dict[str, Any]) -> None:
        self.data = json_data.get("playernpcs")
        if self.data is not None:
            npc_data = self.data[0]['npc']
            npc_name = npc_data.get("name")
            npc_code_name = npc_data.get("codename")
            npc_url = npc_data.get("url")
            npc_memory = npc_data.get("memory")

            npc_props_data = self.data[0]['props']
            npc_props = set()
            for prop_data in npc_props_data:
                prop_name = prop_data.get("name")
                prop_code_name = prop_data.get("codename")
                prop_description = prop_data.get("description")
                prop_is_unique = prop_data.get("isunique")
                if npc_name is not None and prop_name is not None and prop_code_name is not None and prop_description is not None and prop_is_unique is not None:
                    prop = Prop(prop_name, prop_code_name, prop_description, prop_is_unique)
                    npc_props.add(prop)
                else:
                    logger.warning(f"PlayerNpcBuilder: prop data is incomplete: {prop_data}")
            npc = NPC(npc_name, npc_code_name, npc_url, npc_memory, npc_props)
            self.npcs.append(npc)

        
class AdminNpcBuilder:
    def __init__(self) -> None:
        self.data: Optional[dict[str, Any]] = None
        self.npcs: list[NPC] = []
        self.props: list[Prop] = []

    def __str__(self) -> str:
        return f"AdminNpcBuilder: {self.data}"       

    #
    def build(self, json_data: dict[str, Any]) -> None:
        self.data = json_data.get("adminnpcs")
        if self.data is not None:
            npc_data = self.data[0]['npc']
            npc_name = npc_data.get("name")
            npc_code_name = npc_data.get("codename")
            npc_url = npc_data.get("url")
            npc_memory = npc_data.get("memory")
            
            npc_props_data = self.data[0]['props']
            npc_props = set()
            for prop_data in npc_props_data:
                prop_name = prop_data.get("name")
                prop_code_name = prop_data.get("codename")
                prop_description = prop_data.get("description")
                prop_is_unique = prop_data.get("isunique")
                if npc_name is not None and prop_name is not None and prop_code_name is not None and prop_description is not None and prop_is_unique is not None:
                    prop = Prop(prop_name, prop_code_name, prop_description, prop_is_unique)
                    npc_props.add(prop)
                else:
                    logger.warning(f"AdminNpcBuilder: prop data is incomplete: {prop_data}")
            npc = NPC(npc_name, npc_code_name, npc_url, npc_memory, npc_props)
            self.npcs.append(npc)




        