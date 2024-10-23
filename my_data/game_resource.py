from typing import Any, List, Optional, Dict
from my_data.model_def import (
    ActorProxyModel,
    StageProxyModel,
    WorldSystemProxyModel,
    GameModel,
    EntityProfileModel,
    StageArchiveFileModel,
    ActorArchiveFileModel,
    AgentChatHistoryDumpModel,
    PlayerProxyModel,
)
from my_data.data_base import DataBase
from pathlib import Path
import json
from loguru import logger


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

        # load 相关的数据结构
        self._load_dir: Optional[Path] = None
        self._load_zip_file_path: Optional[Path] = None
        self._load_chat_history_dict: Dict[str, AgentChatHistoryDumpModel] = {}
        self._load_entity_profile_dict: Dict[str, EntityProfileModel] = {}
        self._load_actor_archive_dict: Dict[str, List[ActorArchiveFileModel]] = {}
        self._load_stage_archive_dict: Dict[str, List[StageArchiveFileModel]] = {}
        self._load_player_proxy_dict: Dict[str, PlayerProxyModel] = {}

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
    def save_round(self) -> int:
        return self._model.save_round

    ###############################################################################################################################################
    @property
    def world_systems_proxy(self) -> List[WorldSystemProxyModel]:
        return self._model.world_systems

    ###############################################################################################################################################
    @property
    def players_actor_proxy(self) -> List[ActorProxyModel]:
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
    @property
    def is_load(self) -> bool:
        return self._load_dir is not None

    ###############################################################################################################################################
    def get_entity_profile(self, name: str) -> Optional[EntityProfileModel]:
        return self._load_entity_profile_dict.get(name, None)

    ###############################################################################################################################################
    def get_chat_history(self, name: str) -> Optional[AgentChatHistoryDumpModel]:
        return self._load_chat_history_dict.get(name, None)

    ###############################################################################################################################################
    def get_actor_archives(self, name: str) -> List[ActorArchiveFileModel]:
        return self._load_actor_archive_dict.get(name, [])

    ###############################################################################################################################################
    def get_stage_archives(self, name: str) -> List[StageArchiveFileModel]:
        return self._load_stage_archive_dict.get(name, [])

    ###############################################################################################################################################
    def get_player_proxy(self, name: str) -> Optional[PlayerProxyModel]:
        return self._load_player_proxy_dict.get(name, None)

    ###############################################################################################################################################
    def load(self, load_dir: Path, load_zip_file_path: Path) -> None:
        assert self._load_dir is None

        self._load_dir = load_dir
        self._load_zip_file_path = load_zip_file_path

        assert self._load_dir.exists()
        assert load_zip_file_path.exists()

        logger.info(f"load = {load_dir}")

        self._load_world_systems()
        self._load_player_actors()
        self._load_actors()
        self._load_stages()
        self._load_player_proxy()

        logger.info(f"load = {load_dir} done.")

    ###############################################################################################################################################
    def _load_world_systems(self) -> None:

        assert self._load_dir is not None and self._load_dir.exists()

        for world_system in self.world_systems_proxy:

            # 载入聊天记录
            chat_history_dump_model = self._load_chat_history(
                world_system.name, self._load_dir
            )
            if chat_history_dump_model is not None:
                self._load_chat_history_dict[world_system.name] = (
                    chat_history_dump_model
                )

    ###############################################################################################################################################
    def _load_player_actors(self) -> None:

        assert self._load_dir is not None and self._load_dir.exists()

        for player_actor_proxy in self.players_actor_proxy:

            # 载入聊天记录
            chat_history_dump_model = self._load_chat_history(
                player_actor_proxy.name, self._load_dir
            )
            if chat_history_dump_model is not None:
                self._load_chat_history_dict[player_actor_proxy.name] = (
                    chat_history_dump_model
                )

            # 载入实体的profile
            entity_profile = self._load_entity_profile(
                player_actor_proxy.name, self._load_dir
            )
            if entity_profile is not None:
                self._load_entity_profile_dict[player_actor_proxy.name] = entity_profile

            # 载入actor的存档
            self._load_actor_archive_dict[player_actor_proxy.name] = (
                self._load_actor_archive_file(player_actor_proxy.name, self._load_dir)
            )

            # 载入stage的存档
            self._load_stage_archive_dict[player_actor_proxy.name] = (
                self._load_stage_archive_file(player_actor_proxy.name, self._load_dir)
            )

    ###############################################################################################################################################
    def _load_actors(self) -> None:

        assert self._load_dir is not None and self._load_dir.exists()

        for actor_proxy in self.actors_proxy:

            # 载入聊天记录
            chat_history_dump_model = self._load_chat_history(
                actor_proxy.name, self._load_dir
            )

            if chat_history_dump_model is not None:
                self._load_chat_history_dict[actor_proxy.name] = chat_history_dump_model

            # 载入实体的profile
            entity_profile = self._load_entity_profile(actor_proxy.name, self._load_dir)
            if entity_profile is not None:
                self._load_entity_profile_dict[actor_proxy.name] = entity_profile

            # 载入actor的存档
            self._load_actor_archive_dict[actor_proxy.name] = (
                self._load_actor_archive_file(actor_proxy.name, self._load_dir)
            )

            # 载入stage的存档
            self._load_stage_archive_dict[actor_proxy.name] = (
                self._load_stage_archive_file(actor_proxy.name, self._load_dir)
            )

    ###############################################################################################################################################
    def _load_stages(self) -> None:

        assert self._load_dir is not None and self._load_dir.exists()

        for stage_proxy in self.stages_proxy:

            # 载入聊天记录
            chat_history_dump_model = self._load_chat_history(
                stage_proxy.name, self._load_dir
            )
            if chat_history_dump_model is not None:
                self._load_chat_history_dict[stage_proxy.name] = chat_history_dump_model

            # 载入实体的profile
            entity_profile = self._load_entity_profile(stage_proxy.name, self._load_dir)
            if entity_profile is not None:
                self._load_entity_profile_dict[stage_proxy.name] = entity_profile

            # 载入actor的存档
            self._load_actor_archive_dict[stage_proxy.name] = (
                self._load_actor_archive_file(stage_proxy.name, self._load_dir)
            )

            # 载入stage的存档
            self._load_stage_archive_dict[stage_proxy.name] = (
                self._load_stage_archive_file(stage_proxy.name, self._load_dir)
            )

    ###############################################################################################################################################
    def _load_chat_history(
        self, name: str, load_dir: Path
    ) -> Optional[AgentChatHistoryDumpModel]:

        chat_history_file_path = load_dir / f"{name}/chat_history.json"
        if not chat_history_file_path.exists():
            return None

        content = chat_history_file_path.read_text(encoding="utf-8")
        if content is None:
            return None

        return AgentChatHistoryDumpModel.model_validate_json(content)

    ###############################################################################################################################################
    def _load_entity_profile(
        self, name: str, load_dir: Path
    ) -> Optional[EntityProfileModel]:

        entity_profile_file_path = load_dir / f"{name}/entity.json"
        if not entity_profile_file_path.exists():
            return None

        content = entity_profile_file_path.read_text(encoding="utf-8")
        if content is None:
            return None

        data = json.loads(content)
        if data is None:
            return None

        return EntityProfileModel.model_validate_json(
            json.dumps(data, ensure_ascii=False)
        )

    ###############################################################################################################################################
    def _load_stage_archive_file(
        self, name: str, load_dir: Path
    ) -> List[StageArchiveFileModel]:

        stage_archives_dir = load_dir / f"{name}/stage_archives"
        if not stage_archives_dir.exists():
            return []

        ret: List[StageArchiveFileModel] = []

        # 获得 stage_archives_dir 这个dir 下的所有后缀为.json的文件。并输入到一个列表里
        stage_archive_files = list(stage_archives_dir.glob("*.json"))
        for stage_archive_file in stage_archive_files:
            content = stage_archive_file.read_text(encoding="utf-8")
            if content is None:
                continue

            new_model = StageArchiveFileModel.model_validate_json(content)
            ret.append(new_model)

        return ret

    ###############################################################################################################################################
    def _load_actor_archive_file(
        self, name: str, load_dir: Path
    ) -> List[ActorArchiveFileModel]:

        actor_archives_dir = load_dir / f"{name}/actor_archives"
        if not actor_archives_dir.exists():
            return []

        ret: List[ActorArchiveFileModel] = []
        actor_archive_files = list(actor_archives_dir.glob("*.json"))
        for actor_archive_file in actor_archive_files:
            content = actor_archive_file.read_text(encoding="utf-8")
            if content is None:
                continue

            new_model = ActorArchiveFileModel.model_validate_json(content)
            ret.append(new_model)

        return []

    ###############################################################################################################################################
    def resolve_player_proxy_save_file_path(self, player_name: str) -> Path:
        assert self._runtime_dir.exists()
        dir = self._runtime_dir / "players"
        dir.mkdir(parents=True, exist_ok=True)
        return dir / f"""{player_name}.json"""

    ###############################################################################################################################################
    def _load_player_proxy(self) -> None:

        assert self._load_dir is not None and self._load_dir.exists()

        self._load_player_proxy_dict.clear()

        players_dir = self._load_dir / f"players"
        if not players_dir.exists():
            return

        player_proxy_files = list(players_dir.glob("*.json"))
        for player_proxy_file in player_proxy_files:
            content = player_proxy_file.read_text(encoding="utf-8")
            if content is None:
                continue

            model = PlayerProxyModel.model_validate_json(content)
            self._load_player_proxy_dict[model.name] = model

    ###############################################################################################################################################
