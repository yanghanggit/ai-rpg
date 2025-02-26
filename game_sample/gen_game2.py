# from enum import IntEnum, StrEnum, unique
# import sys
# from pathlib import Path

# root_dir = Path(__file__).resolve().parent.parent
# sys.path.append(str(root_dir))
# import pandas
# from loguru import logger
# from pandas.core.frame import DataFrame
# from typing import List, Dict, Any, final, cast, Optional
# import format_string.ints_string
# from rpg_models.tcg_models import (
#     WorldRoot,
#     WorldDataBase,
#     ActorPrototype,
#     StagePrototype,
#     # PropPrototype,
#     WorldSystemPrototype,
#     PropObject,
#     ActorInstance,
#     StageInstance,
#     WorldSystemInstance,
#     PropObject,
# )
# import game.tcg_game_config


# @unique
# class StageProperty(StrEnum):
#     NAME = "name"
#     CODE_NAME = "code_name"
#     ACTOR_PROFILE = "stage_profile"
#     CONVERSATIONAL_STYLE = "conversational_style"


# @unique
# class ActorProperty(StrEnum):
#     NAME = "name"
#     CODE_NAME = "code_name"
#     ACTOR_PROFILE = "actor_profile"
#     CONVERSATIONAL_STYLE = "conversational_style"
#     BASE_FORM = "base_form"


# @unique
# class PropProperty(StrEnum):
#     NAME = "name"
#     CODE_NAME = "code_name"
#     TYPE = "type"
#     DETAILS = "details"
#     APPEARANCE = "appearance"
#     INSIGHT = "insight"


# @unique
# class WorldSystemProperty(StrEnum):
#     NAME = "name"
#     CODE_NAME = "code_name"
#     WORLD_SYSTEM_PROFILE = "world_system_profile"


# @unique
# class EditorProperty(StrEnum):
#     NAME = "name"
#     TYPE = "type"
#     DESCRIPTION = "description"
#     KICK_OFF_MESSAGE = "kick_off_message"
#     STAGE_GRAPH = "stage_graph"
#     ACTORS_ON_STAGE = "actors_on_stage"
#     ACTOR_PROPS = "actor_props"
#     ATTRIBUTES = "attributes"


# @unique
# class Attributes(IntEnum):
#     MAX = 20


# @final
# class ActorData:
#     def __init__(self, data: Any) -> None:
#         assert data is not None
#         self._data = data

#     @property
#     def name(self) -> str:
#         return str(self._data[ActorProperty.NAME])

#     @property
#     def code_name(self) -> str:
#         return str(self._data[ActorProperty.CODE_NAME])

#     @property
#     def actor_profile(self) -> str:
#         return str(self._data[ActorProperty.ACTOR_PROFILE])

#     @property
#     def conversational_style(self) -> str:
#         if pandas.isna(self._data[ActorProperty.CONVERSATIONAL_STYLE]):
#             return ""
#         return str(self._data[ActorProperty.CONVERSATIONAL_STYLE])

#     @property
#     def base_form(self) -> str:
#         return str(self._data[ActorProperty.BASE_FORM])


# @final
# class StageData:
#     def __init__(self, data: Any) -> None:
#         assert data is not None
#         self._data = data

#     @property
#     def name(self) -> str:
#         return str(self._data[StageProperty.NAME])

#     @property
#     def code_name(self) -> str:
#         return str(self._data[StageProperty.CODE_NAME])

#     @property
#     def stage_profile(self) -> str:
#         return str(self._data[StageProperty.ACTOR_PROFILE])

#     @property
#     def conversational_style(self) -> str:
#         if pandas.isna(self._data[StageProperty.CONVERSATIONAL_STYLE]):
#             return ""
#         return str(self._data[StageProperty.CONVERSATIONAL_STYLE])


# @final
# class PropData:
#     def __init__(self, data: Any) -> None:
#         assert data is not None
#         self._data = data

#     @property
#     def name(self) -> str:
#         return str(self._data[PropProperty.NAME])

#     @property
#     def code_name(self) -> str:
#         return str(self._data[PropProperty.CODE_NAME])

#     @property
#     def type(self) -> str:
#         return str(self._data[PropProperty.TYPE])

#     @property
#     def details(self) -> str:
#         return str(self._data[PropProperty.DETAILS])

#     @property
#     def appearance(self) -> str:
#         return str(self._data[PropProperty.APPEARANCE])

#     @property
#     def insight(self) -> str:
#         return str(self._data[PropProperty.INSIGHT])


# @final
# class WorldSystemData:
#     def __init__(self, data: Any) -> None:
#         assert data is not None
#         self._data = data

#     @property
#     def name(self) -> str:
#         return str(self._data[WorldSystemProperty.NAME])

#     @property
#     def code_name(self) -> str:
#         return str(self._data[WorldSystemProperty.CODE_NAME])

#     @property
#     def world_system_profile(self) -> str:
#         return str(self._data[WorldSystemProperty.WORLD_SYSTEM_PROFILE])


# @final
# class DataBase:

#     def __init__(self) -> None:

#         self._actor_data_base: Dict[str, ActorData] = {}
#         self._stage_data_base: Dict[str, StageData] = {}
#         self._prop_data_base: Dict[str, PropData] = {}
#         self._world_system_data_base: Dict[str, WorldSystemData] = {}

#     def build_actor_data_base(self, sheet: DataFrame) -> None:
#         for index, row in sheet.iterrows():
#             if pandas.isna(row[ActorProperty.NAME]):
#                 continue
#             actor = ActorData(row)
#             self._actor_data_base[actor.name] = actor

#     def build_stage_data_base(self, sheet: DataFrame) -> None:
#         for index, row in sheet.iterrows():
#             if pandas.isna(row[StageProperty.NAME]):
#                 continue
#             stage = StageData(row)
#             self._stage_data_base[stage.name] = stage

#     def build_prop_data_base(self, sheet: DataFrame) -> None:
#         for index, row in sheet.iterrows():
#             if pandas.isna(row[PropProperty.NAME]):
#                 continue
#             prop = PropData(row)
#             self._prop_data_base[prop.name] = prop

#     def build_world_system_data_base(self, sheet: DataFrame) -> None:
#         for index, row in sheet.iterrows():
#             if pandas.isna(row[WorldSystemProperty.NAME]):
#                 continue
#             world_system = WorldSystemData(row)
#             self._world_system_data_base[world_system.name] = world_system


# @unique
# class EditorDataType(StrEnum):
#     NONE = "None"
#     WORLD_SYSTEM = "WorldSystem"
#     PLAYER = "Player"
#     ACTOR = "Actor"
#     STAGE = "Stage"
#     EPOCH_SCRIPT = "EpochScript"
#     PROP = "Prop"


# class EditorData:
#     def __init__(self, data: Any) -> None:
#         assert data is not None
#         self._data = data

#     @property
#     def name(self) -> str:
#         return str(self._data[EditorProperty.NAME])

#     @property
#     def type(self) -> EditorDataType:
#         if pandas.isna(self._data[EditorProperty.TYPE]):
#             assert False, f"GameType is empty: {self.name}"
#             return EditorDataType.NONE

#         return EditorDataType(self._data[EditorProperty.TYPE])

#     @property
#     def description(self) -> str:
#         return str(self._data[EditorProperty.DESCRIPTION])

#     @property
#     def kick_off_message(self) -> str:
#         if pandas.isna(self._data[EditorProperty.KICK_OFF_MESSAGE]):
#             return ""
#         return str(self._data[EditorProperty.KICK_OFF_MESSAGE])

#     @property
#     def stage_graph(self) -> List[str]:
#         if pandas.isna(self._data[EditorProperty.STAGE_GRAPH]):
#             return []
#         data = cast(str, self._data[EditorProperty.STAGE_GRAPH])
#         return data.split(";")

#     @property
#     def actors_on_stage(self) -> List[str]:
#         if pandas.isna(self._data[EditorProperty.ACTORS_ON_STAGE]):
#             return []
#         data = cast(str, self._data[EditorProperty.ACTORS_ON_STAGE])
#         return data.split(";")

#     @property
#     def actor_props(self) -> List[str]:
#         if pandas.isna(self._data[EditorProperty.ACTOR_PROPS]):
#             return []
#         data = cast(str, self._data[EditorProperty.ACTOR_PROPS])
#         return data.split(";")

#     @property
#     def attributes(self) -> List[int]:
#         assert self._data is not None
#         data = cast(str, self._data[EditorProperty.ATTRIBUTES])
#         assert ";" in data, f"raw_string_val: {data} is not valid."
#         values = format_string.ints_string.convert_string_to_ints(data, ";")
#         if len(values) < Attributes.MAX:
#             values.extend([0] * (Attributes.MAX - len(values)))
#         return values


# @final
# class ConfigEditor(EditorData):
#     def __init__(self, data: Any) -> None:
#         super().__init__(data)


# @final
# class WorldSystemEditor(EditorData):
#     def __init__(self, data: Any, world_system_data: WorldSystemData) -> None:
#         super().__init__(data)
#         self._world_system_data = world_system_data


# class ActorEditor(EditorData):
#     def __init__(self, data: Any, actor_data: ActorData) -> None:
#         super().__init__(data)
#         self._actor_data = actor_data


# @final
# class PlayerEditor(ActorEditor):
#     pass


# @final
# class StageEditor(EditorData):
#     def __init__(self, data: Any, stage_data: StageData) -> None:
#         super().__init__(data)
#         self._stage_data = stage_data


# @final
# class PropEditor(EditorData):
#     def __init__(self, data: Any, prop_data: PropData) -> None:
#         super().__init__(data)
#         self._prop_data = prop_data


# @final
# class GameEditor:

#     def __init__(
#         self, sheet_data: Any, game_name: str, version: str, data_base: DataBase
#     ) -> None:

#         self._sheet_data = sheet_data
#         self._game_name = game_name
#         self._version = version
#         self._data_base = data_base

#         # 缓存数据用。
#         self._cache_world_systems: Optional[List[WorldSystemEditor]] = None
#         self._cache_players: Optional[List[PlayerEditor]] = None
#         self._cache_actors: Optional[List[ActorEditor]] = None
#         self._cache_stages: Optional[List[StageEditor]] = None
#         self._cache_props: Optional[List[PropEditor]] = None
#         self._cache_configs: Optional[List[ConfigEditor]] = None

#         #
#         self._index_as_guid = 1000
#         self._world_root = WorldRoot()

#     ############################################################################################################
#     @property
#     def world_systems(self) -> List[WorldSystemEditor]:

#         if self._cache_world_systems is None:
#             self._cache_world_systems = []

#             for index, item in self._sheet_data.iterrows():
#                 if pandas.isna(item[EditorProperty.NAME]):
#                     continue

#                 if item[EditorProperty.TYPE] != EditorDataType.WORLD_SYSTEM:
#                     continue

#                 if (
#                     item[EditorProperty.NAME]
#                     not in self._data_base._world_system_data_base
#                 ):
#                     assert (
#                         False
#                     ), f"Invalid WorldSystem name: {item[EditorProperty.NAME]}"
#                     continue

#                 self._cache_world_systems.append(
#                     WorldSystemEditor(
#                         item,
#                         self._data_base._world_system_data_base[
#                             item[EditorProperty.NAME]
#                         ],
#                     )
#                 )

#         return self._cache_world_systems

#     ############################################################################################################
#     @property
#     def players(self) -> List[PlayerEditor]:

#         if self._cache_players is None:
#             self._cache_players = []
#             for index, item in self._sheet_data.iterrows():
#                 if pandas.isna(item[EditorProperty.NAME]):
#                     continue

#                 if item[EditorProperty.TYPE] != EditorDataType.PLAYER:
#                     continue

#                 if item[EditorProperty.NAME] not in self._data_base._actor_data_base:
#                     assert False, f"Invalid Player name: {item[EditorProperty.NAME]}"
#                     continue

#                 self._cache_players.append(
#                     PlayerEditor(
#                         item,
#                         self._data_base._actor_data_base[item[EditorProperty.NAME]],
#                     )
#                 )

#         return self._cache_players

#     ############################################################################################################
#     @property
#     def actors(self) -> List[ActorEditor]:

#         if self._cache_actors is None:
#             self._cache_actors = []
#             for index, item in self._sheet_data.iterrows():
#                 if pandas.isna(item[EditorProperty.NAME]):
#                     continue

#                 if item[EditorProperty.TYPE] != EditorDataType.ACTOR:
#                     continue

#                 if item[EditorProperty.NAME] not in self._data_base._actor_data_base:
#                     assert False, f"Invalid Actor name: {item[EditorProperty.NAME]}"
#                     continue

#                 self._cache_actors.append(
#                     ActorEditor(
#                         item,
#                         self._data_base._actor_data_base[item[EditorProperty.NAME]],
#                     )
#                 )

#         return self._cache_actors

#     ############################################################################################################
#     @property
#     def stages(self) -> List[StageEditor]:
#         if self._cache_stages is None:
#             self._cache_stages = []
#             for index, item in self._sheet_data.iterrows():
#                 if pandas.isna(item[EditorProperty.NAME]):
#                     continue

#                 if item[EditorProperty.TYPE] != EditorDataType.STAGE:
#                     continue

#                 if item[EditorProperty.NAME] not in self._data_base._stage_data_base:
#                     assert False, f"Invalid Stage name: {item[EditorProperty.NAME]}"
#                     continue

#                 self._cache_stages.append(
#                     StageEditor(
#                         item,
#                         self._data_base._stage_data_base[item[EditorProperty.NAME]],
#                     )
#                 )

#         return self._cache_stages

#     ############################################################################################################
#     @property
#     def props(self) -> List[PropEditor]:
#         if self._cache_props is None:
#             self._cache_props = []
#             for index, item in self._sheet_data.iterrows():
#                 if pandas.isna(item[EditorProperty.NAME]):
#                     continue

#                 if item[EditorProperty.TYPE] != EditorDataType.PROP:
#                     continue

#                 if item[EditorProperty.NAME] not in self._data_base._prop_data_base:
#                     assert False, f"Invalid Prop name: {item[EditorProperty.NAME]}"
#                     continue

#                 self._cache_props.append(
#                     PropEditor(
#                         item,
#                         self._data_base._prop_data_base[item[EditorProperty.NAME]],
#                     )
#                 )

#         return self._cache_props

#     ############################################################################################################
#     @property
#     def configs(self) -> List[ConfigEditor]:
#         if self._cache_configs is None:
#             self._cache_configs = []
#             for index, item in self._sheet_data.iterrows():
#                 if pandas.isna(item[EditorProperty.NAME]):
#                     continue

#                 if item[EditorProperty.TYPE] != EditorDataType.EPOCH_SCRIPT:
#                     continue

#                 self._cache_configs.append(ConfigEditor(item))

#         return self._cache_configs

#     ############################################################################################################
#     def build(self) -> None:

#         self._world_root = WorldRoot()
#         self._world_root.name = self._game_name
#         self._world_root.version = self._version
#         if len(self.configs) > 0:
#             self._world_root.epoch_script = self.configs[0].description

#         # step 1: 构建数据
#         self._build_world_data_base()

#         # step 2: 构建实例
#         self._build_world_root_instances()

#     ############################################################################################################
#     def _link_actor_props(
#         self, actor_instance: ActorInstance, actor_editor: ActorEditor
#     ) -> None:
#         pass
#         # for prop1 in actor_editor.actor_props:
#         #     for prop2 in self.props:
#         #         if prop1 == prop2.name:
#         #             guid = self._gen_guid()
#         #             prop_instance = PropInstance(
#         #                 name=self.make_complex_name(prop2.name, guid),
#         #                 guid=guid,
#         #                 count=1,
#         #                 attributes=prop2.attributes,
#         #             )
#         #             actor_instance.props.append(prop_instance)

#     ############################################################################################################
#     def _link_stage_props(
#         self, stage_instance: StageInstance, stage_editor: StageEditor
#     ) -> None:
#         pass
#         # for prop1 in stage_editor.actor_props:
#         #     for prop2 in self.props:
#         #         if prop1 == prop2.name:
#         #             guid = self._gen_guid()
#         #             prop_instance = PropInstance(
#         #                 name=self.make_complex_name(prop2.name, guid),
#         #                 guid=guid,
#         #                 count=1,
#         #                 attributes=prop2.attributes,
#         #             )
#         #             stage_instance.props.append(prop_instance)

#     ############################################################################################################
#     def _build_world_root_instances(self) -> None:
#         for world_system in self.world_systems:
#             guid0 = self._gen_guid()
#             world_system_instance = WorldSystemInstance(
#                 name=self.make_complex_name(world_system.name, guid0),
#                 guid=guid0,
#                 kick_off_message=world_system.kick_off_message,
#             )
#             self._world_root.world_systems.append(world_system_instance)

#         for player_editor in self.players:

#             guid1 = self._gen_guid()
#             actor_instance = ActorInstance(
#                 name=self.make_complex_name(player_editor.name, guid1),
#                 guid=guid1,
#                 kick_off_message=player_editor.kick_off_message,
#                 props=[],
#                 attributes=player_editor.attributes,
#             )

#             self._link_actor_props(actor_instance, player_editor)
#             self._world_root.players.append(actor_instance)

#         for actor_editor in self.actors:
#             guid2 = self._gen_guid()
#             actor_instance = ActorInstance(
#                 name=self.make_complex_name(actor_editor.name, guid2),
#                 guid=guid2,
#                 kick_off_message=actor_editor.kick_off_message,
#                 props=[],
#                 attributes=actor_editor.attributes,
#             )
#             self._link_actor_props(actor_instance, actor_editor)
#             self._world_root.actors.append(actor_instance)

#         for stage_editor in self.stages:
#             guid3 = self._gen_guid()
#             stage_instance = StageInstance(
#                 name=self.make_complex_name(stage_editor.name, guid3),
#                 guid=guid3,
#                 actors=[],
#                 kick_off_message=stage_editor.kick_off_message,
#                 props=[],
#                 attributes=stage_editor.attributes,
#                 next=stage_editor.stage_graph,
#             )
#             self._link_stage_props(stage_instance, stage_editor)
#             self._link_stage_actors(stage_instance, stage_editor)
#             self._world_root.stages.append(stage_instance)

#     ############################################################################################################
#     def _link_stage_actors(
#         self, stage_instance: StageInstance, stage_editor: StageEditor
#     ) -> None:
#         for actor1 in stage_editor.actors_on_stage:
#             for actor2 in self._world_root.players + self._world_root.actors:
#                 logger.warning(
#                     f"actor1: {actor1}, actor2: {actor2.name}, 其实是想的不全面的后续的怪物还是要group"
#                 )
#                 if actor1 in actor2.name:
#                     stage_instance.actors.append(actor2.name)

#     ############################################################################################################
#     def write(self) -> None:
#         try:
#             write_path = game.tcg_game_config.GEN_WORLD_DIR / f"{self._game_name}.json"
#             write_path.write_text(self._world_root.model_dump_json(), encoding="utf-8")
#         except Exception as e:
#             logger.error(f"An error occurred: {e}")

#     ############################################################################################################
#     def _gen_guid(self) -> int:
#         self._index_as_guid += 1
#         return self._index_as_guid

#     ############################################################################################################
#     def make_complex_name(self, name: str, guid: int) -> str:
#         return f"{name}%{guid}"

#     ############################################################################################################
#     def _build_world_data_base(self) -> WorldDataBase:

#         for actor in self.players + self.actors:
#             actor_prototype = ActorPrototype(
#                 name=actor.name,
#                 code_name=actor._actor_data.code_name,
#                 system_message=actor._actor_data.actor_profile,
#                 appearance=actor._actor_data.base_form,
#             )

#             self._world_root.data_base.actors[actor_prototype.name] = actor_prototype

#         for stage in self.stages:
#             pass

#             # stage_prototype = StagePrototype(
#             #     name=stage.name,
#             #     code_name=stage._stage_data.code_name,
#             #     system_message=stage._stage_data.stage_profile,
#             # )
#             # self._world_root.data_base.stages[stage_prototype.name] = stage_prototype

#         # for prop in self.props:
#         #     prop_prototype = PropPrototype(
#         #         name=prop.name,
#         #         code_name=prop._prop_data.code_name,
#         #         details=prop._prop_data.details,
#         #         type=prop._prop_data.type,
#         #         appearance=prop._prop_data.appearance,
#         #         insight=prop._prop_data.insight,
#         #     )
#         #     self._world_root.data_base.props[prop_prototype.name] = prop_prototype

#         for world_system in self.world_systems:
#             world_system_prototype = WorldSystemPrototype(
#                 name=world_system.name,
#                 code_name=world_system._world_system_data.code_name,
#                 system_message=world_system._world_system_data.world_system_profile,
#             )

#             self._world_root.data_base.world_systems[world_system_prototype.name] = (
#                 world_system_prototype
#             )

#         return self._world_root.data_base


# ############################################################################################################
# def main(game_names: List[str]) -> None:

#     # Excel文件路径
#     excel_path = Path(f"game_sample/excel/")
#     excel_path.mkdir(parents=True, exist_ok=True)
#     tcg_game_xlsx_path: Path = excel_path / "tcg_game.xlsx"
#     assert tcg_game_xlsx_path.exists(), f"找不到Excel文件: {tcg_game_xlsx_path}"

#     actor_sheet: DataFrame = pandas.read_excel(
#         tcg_game_xlsx_path,
#         sheet_name="Actor",
#         engine="openpyxl",
#     )
#     stage_sheet: DataFrame = pandas.read_excel(
#         tcg_game_xlsx_path,
#         sheet_name="Stage",
#         engine="openpyxl",
#     )
#     prop_sheet: DataFrame = pandas.read_excel(
#         tcg_game_xlsx_path,
#         sheet_name="Prop",
#         engine="openpyxl",
#     )
#     world_system_sheet: DataFrame = pandas.read_excel(
#         tcg_game_xlsx_path,
#         sheet_name="WorldSystem",
#         engine="openpyxl",
#     )

#     # 构建一个数据库
#     data_bases = DataBase()
#     data_bases.build_actor_data_base(actor_sheet)
#     data_bases.build_stage_data_base(stage_sheet)
#     data_bases.build_prop_data_base(prop_sheet)
#     data_bases.build_world_system_data_base(world_system_sheet)

#     for game_name in game_names:

#         #
#         game_sheet: DataFrame = pandas.read_excel(
#             tcg_game_xlsx_path,
#             sheet_name=game_name,
#             engine="openpyxl",
#         )

#         if game_sheet is None:
#             logger.warning(f"找不到sheet: {game_name}")
#             continue

#         game_editor = GameEditor(
#             sheet_data=game_sheet,
#             game_name=game_name,
#             version="0.0.1",
#             data_base=data_bases,
#         )
#         game_editor.build()
#         game_editor.write()


# ############################################################################################################
# if __name__ == "__main__":
#     main(["Game2"])
