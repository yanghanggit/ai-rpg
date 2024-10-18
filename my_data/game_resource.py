from typing import Any, List, Optional, Dict, cast
from my_data.model_def import (
    ActorProxyModel,
    StageProxyModel,
    WorldSystemProxyModel,
    GameModel,
    EntityProfileModel,
)
from my_data.data_base import DataBase
from pathlib import Path
import json
from loguru import logger
from extended_systems.files_def import ActorArchiveFile, StageArchiveFile


class GameResource:

    @staticmethod
    def generate_runtime_file_name(game_name: str) -> str:
        return f"""{game_name}_runtime.json"""

    def __init__(self, name: str, data: Any, game_runtime_dir: Path) -> None:

        # 资源的名字也是游戏的名字
        self._game_name: str = name

        # 运行时路径保存
        self._runtime_dir: Path = game_runtime_dir
        assert self._runtime_dir.exists()

        # 核心数据
        self._model = GameModel.model_validate_json(
            json.dumps(data, ensure_ascii=False)
        )

        # 数据单独处理
        self._data_base = DataBase(self._model.database)

        # 运行时模型，用于后续的存储时候用。
        self._runtime_model = self._model.model_copy()

        #
        self._load_dir: Optional[Path] = None
        self._load_chat_history_dict: Dict[str, List[Dict[str, str]]] = {}
        self._load_entity_profile_dict: Dict[str, EntityProfileModel] = {}
        self._load_actor_archive_dict: Dict[str, List[ActorArchiveFile]] = {}
        self._load_stage_archive_dict: Dict[str, List[StageArchiveFile]] = {}

    ###############################################################################################################################################
    @property
    def version(self) -> str:
        return self._model.version

    ###############################################################################################################################################
    @property
    def about_game(self) -> str:
        return self._model.about_game

    ###############################################################################################################################################
    @property
    def world_systems_proxy(self) -> List[WorldSystemProxyModel]:
        return self._model.world_systems

    ###############################################################################################################################################
    @property
    def players_proxy(self) -> List[ActorProxyModel]:
        return self._model.players

    ###############################################################################################################################################
    @property
    def actors_proxy(self) -> List[ActorProxyModel]:
        return self._model.actors

    ###############################################################################################################################################
    @property
    def stages_proxy(self) -> List[StageProxyModel]:
        return self._model.stages

    ###############################################################################################################################################
    def load(self, load_dir: Path) -> None:
        assert self._load_dir is None
        self._load_dir = load_dir
        assert self._load_dir.exists()

        logger.info(f"load = {load_dir}")

        self._load_world_systems()
        self._load_players()
        self._load_actors()
        self._load_stages()

        logger.info(f"load = {load_dir} done.")

    ###############################################################################################################################################
    def _load_world_systems(self) -> None:

        assert self._load_dir is not None and self._load_dir.exists()

        for world_system in self.world_systems_proxy:

            self._load_chat_history_dict[world_system.name] = self._load_chat_history(
                world_system.name, self._load_dir
            )

    ###############################################################################################################################################
    def _load_players(self) -> None:

        assert self._load_dir is not None and self._load_dir.exists()

        for player in self.players_proxy:

            self._load_chat_history_dict[player.name] = self._load_chat_history(
                player.name, self._load_dir
            )

            self._load_entity_profile_dict[player.name] = self._load_entity_profile(
                player.name, self._load_dir
            )

            self._load_actor_archive_dict[player.name] = self._load_actor_archive_file(
                player.name, self._load_dir
            )

            self._load_stage_archive_dict[player.name] = self._load_stage_archive_file(
                player.name, self._load_dir
            )

    ###############################################################################################################################################
    def _load_actors(self) -> None:

        assert self._load_dir is not None and self._load_dir.exists()

        for actor in self.actors_proxy:

            self._load_chat_history_dict[actor.name] = self._load_chat_history(
                actor.name, self._load_dir
            )

            self._load_entity_profile_dict[actor.name] = self._load_entity_profile(
                actor.name, self._load_dir
            )

            self._load_actor_archive_dict[actor.name] = self._load_actor_archive_file(
                actor.name, self._load_dir
            )

            self._load_stage_archive_dict[actor.name] = self._load_stage_archive_file(
                actor.name, self._load_dir
            )

    ###############################################################################################################################################
    def _load_stages(self) -> None:

        assert self._load_dir is not None and self._load_dir.exists()

        for stage in self.stages_proxy:

            self._load_chat_history_dict[stage.name] = self._load_chat_history(
                stage.name, self._load_dir
            )

            self._load_entity_profile_dict[stage.name] = self._load_entity_profile(
                stage.name, self._load_dir
            )

            self._load_actor_archive_dict[stage.name] = self._load_actor_archive_file(
                stage.name, self._load_dir
            )

            self._load_stage_archive_dict[stage.name] = self._load_stage_archive_file(
                stage.name, self._load_dir
            )

    ###############################################################################################################################################
    def _load_chat_history(self, name: str, load_dir: Path) -> List[Dict[str, str]]:

        chat_history_file_path = load_dir / f"{name}/chat_history.json"
        if not chat_history_file_path.exists():
            return []

        content = chat_history_file_path.read_text(encoding="utf-8")
        if content is None:
            return []

        data = json.loads(content)
        if data is None:
            return []

        return cast(List[Dict[str, str]], data)

    ###############################################################################################################################################
    def _load_entity_profile(self, name: str, load_dir: Path) -> EntityProfileModel:

        entity_profile_file_path = load_dir / f"{name}/entity.json"
        if not entity_profile_file_path.exists():
            return EntityProfileModel(name="", components=[])

        content = entity_profile_file_path.read_text(encoding="utf-8")
        if content is None:
            return EntityProfileModel(name="", components=[])

        data = json.loads(content)
        if data is None:
            return EntityProfileModel(name="", components=[])

        return EntityProfileModel.model_validate_json(
            json.dumps(data, ensure_ascii=False)
        )

    ###############################################################################################################################################
    def _load_actor_archive_file(
        self, name: str, load_dir: Path
    ) -> List[ActorArchiveFile]:
        return []

    ###############################################################################################################################################
    def _load_stage_archive_file(
        self, name: str, load_dir: Path
    ) -> List[StageArchiveFile]:

        stage_archives_dir = load_dir / f"{name}/stage_archives"
        if not stage_archives_dir.exists():
            return []

        ret: List[StageArchiveFile] = []

        # 获得 stage_archives_dir 这个dir 下的所有后缀为.json的文件。并输入到一个列表里
        stage_archive_files = list(stage_archives_dir.glob("*.json"))
        for stage_archive_file in stage_archive_files:
            content = stage_archive_file.read_text(encoding="utf-8")
            if content is None:
                continue

            data = json.loads(content)
            if data is None:
                continue

            name = stage_archive_file.stem
            new_file = StageArchiveFile(name=name, owner_name=name, stage_name=name)
            new_file.deserialization(content)
            ret.append(new_file)

        return ret

    ###############################################################################################################################################
