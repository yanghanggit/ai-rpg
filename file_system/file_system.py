from loguru import logger
from typing import Dict, List, Optional
from file_system.files_def import PropFile, ActorArchiveFile, StageArchiveFile, StatusProfileFile, StageActorsMapFile
from pathlib import Path

class FileSystem:

    def __init__(self, name: str) -> None:
        # 名字
        self._name: str = name
        # 运行时路径
        self._runtime_dir: Optional[Path] = None
        # 拥有的道具
        self._prop_files: Dict[str, List[PropFile]] = {}
        # 知晓的Actor
        self._actor_archives: Dict[str, List[ActorArchiveFile]] = {}
        # 知晓的Stage
        self._stage_archives: Dict[str, List[StageArchiveFile]] = {}
        # 角色的属性的记录
        self._status_profile: Dict[str, StatusProfileFile] = {}
        # 场景的角色的映射关系，全局唯一，空的
        self._stage_actors_map: StageActorsMapFile = StageActorsMapFile({})
################################################################################################################
    ### 必须设置根部的执行路行
    def set_runtime_dir(self, runtime_dir: Path) -> None:
        assert runtime_dir is not None
        self._runtime_dir = runtime_dir
        self._runtime_dir.mkdir(parents=True, exist_ok=True)
        assert runtime_dir.exists()
        assert self._runtime_dir.is_dir(), f"Directory is not a directory: {self._runtime_dir}"
################################################################################################################
################################################################################################################
################################################################################################################
################################################################################################################
    def prop_file_path(self, owner_name: str, file_name: str) -> Path:
        assert self._runtime_dir is not None
        dir = self._runtime_dir / f"{owner_name}/props"
        dir.mkdir(parents = True, exist_ok = True)
        return dir / f"{file_name}.json"
################################################################################################################
    ## 写一个道具的文件
    def write_prop_file(self, prop_file: PropFile) -> int:
        prop_file_path = self.prop_file_path(prop_file._owner_name, prop_file._name)
        return prop_file.write(prop_file_path)
################################################################################################################
    ## 添加一个道具文件
    def add_prop_file(self, prop_file: PropFile, need_write: bool = True) -> None:
        self._prop_files.setdefault(prop_file._owner_name, []).append(prop_file)
        if need_write:
            self.write_prop_file(prop_file)
################################################################################################################
    def get_prop_files(self, owner_name: str) -> List[PropFile]:
        return self._prop_files.get(owner_name, [])
################################################################################################################
    def get_prop_file(self, owner_name: str, prop_name: str) -> Optional[PropFile]:
        prop_files = self.get_prop_files(owner_name)
        for file in prop_files:
            if file._name == prop_name:
                return file
        return None
################################################################################################################
    def has_prop_file(self, owner_name: str, prop_name: str) -> bool:
        return self.get_prop_file(owner_name, prop_name) is not None
################################################################################################################
    def give_prop_file(self, from_owner: str, to_owner: str, prop_name: str) -> None:
        find_owners_file = self.get_prop_file(from_owner, prop_name)
        if find_owners_file is None:
            logger.error(f"{from_owner}没有{prop_name}这个道具。")
            return
        # 文件得从管理数据结构中移除掉
        self._prop_files[from_owner].remove(find_owners_file)
        # 文件得从文件系统中删除掉
        self.prop_file_path(from_owner, prop_name).unlink()
        # 文件重新写入
        self.add_prop_file(PropFile(prop_name, to_owner, find_owners_file._prop_model, find_owners_file._count))
################################################################################################################
################################################################################################################
################################################################################################################
################################################################################################################
    def actor_archive_path(self, owner_name: str, file_name: str) -> Path:
        assert self._runtime_dir is not None
        dir = self._runtime_dir / f"{owner_name}/actors_archive"
        dir.mkdir(parents = True, exist_ok = True)
        return dir / f"{file_name}.json"
################################################################################################################
    ## 添加一个你知道的Actor
    def add_actor_archive(self, actor_archive: ActorArchiveFile) -> Optional[ActorArchiveFile]:
        files = self._actor_archives.setdefault(actor_archive._owner_name, [])
        for file in files:
            if file._actor_name == actor_archive._actor_name:
                # 名字匹配，先返回，不添加。后续可以复杂一些
                return None
        files.append(actor_archive)
        return actor_archive
################################################################################################################
    def has_actor_archive(self, owner_name: str, actor_name: str) -> bool:
        return self.get_actor_archive(owner_name, actor_name) is not None
################################################################################################################
    def get_actor_archive(self, owner_name: str, actor_name: str) -> Optional[ActorArchiveFile]:
        files = self._actor_archives.get(owner_name, [])
        for file in files:
            if file._actor_name == actor_name:
                return file
        return None
################################################################################################################
    def write_actor_archive(self, actor_archive: ActorArchiveFile) -> None:
        archive_file_path = self.actor_archive_path(actor_archive._owner_name, actor_archive._name)
        assert archive_file_path is not None
        actor_archive.write(archive_file_path)
################################################################################################################
################################################################################################################
################################################################################################################
################################################################################################################
    def stage_archive_path(self, owner_name: str, file_name: str) -> Path:
        assert self._runtime_dir is not None
        dir = self._runtime_dir / f"{owner_name}/stages_archive"
        dir.mkdir(parents = True, exist_ok = True)
        return dir / f"{file_name}.json"
################################################################################################################
    def add_stage_archive(self, stage_archive: StageArchiveFile) -> None:
        files = self._stage_archives.setdefault(stage_archive._owner_name, [])
        for file in files:
            if file._stage_name == stage_archive._stage_name:
                # 名字匹配，先返回，不添加。后续可以复杂一些
                return
        files.append(stage_archive)
################################################################################################################
    def write_stage_archive(self, stage_archive_file: StageArchiveFile) -> None:
        archive_file_path = self.stage_archive_path(stage_archive_file._owner_name, stage_archive_file._name)
        assert archive_file_path is not None
        stage_archive_file.write(archive_file_path)
################################################################################################################
    def get_stage_archive(self, owner_name: str, stage_name: str) -> Optional[StageArchiveFile]:
        stage_archives = self._stage_archives.get(owner_name, [])
        for file in stage_archives:
            if file._stage_name == stage_name:
                return file
        return None
################################################################################################################
    def has_stage_archive(self, owner_name: str, stage_name: str) -> bool:
        return self.get_stage_archive(owner_name, stage_name) is not None
################################################################################################################
################################################################################################################
################################################################################################################
################################################################################################################
    def status_profile_path(self, owner_name: str) -> Path:
        assert self._runtime_dir is not None
        dir = self._runtime_dir / f"{owner_name}"
        dir.mkdir(parents = True, exist_ok = True)
        return dir / f"status_profile.json"
################################################################################################################
    def write_status_profile(self, status_profile: StatusProfileFile) -> None:
        status_profile_file_path = self.status_profile_path(status_profile._owner_name)
        assert status_profile_file_path is not None
        status_profile.write(status_profile_file_path)
################################################################################################################
    def set_status_profile(self, status_profile: StatusProfileFile) -> None:
        self._status_profile[status_profile._owner_name] = status_profile
################################################################################################################
################################################################################################################
################################################################################################################
################################################################################################################
    def stage_actors_map_path(self) -> Path:
        assert self._runtime_dir is not None
        dir = self._runtime_dir
        dir.mkdir(parents = True, exist_ok = True)
        return dir / f"stage_actors_map.json"
################################################################################################################
    def set_stage_actors_map(self, stage_actors_map: StageActorsMapFile) -> None:
        self._stage_actors_map = stage_actors_map
################################################################################################################
    def write_stage_actors_map(self, stage_actors_map: StageActorsMapFile) -> None:
        _stage_actors_map_path = self.stage_actors_map_path()
        assert _stage_actors_map_path is not None
        stage_actors_map.write(_stage_actors_map_path)
################################################################################################################