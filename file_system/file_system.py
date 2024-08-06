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
    def prop_file_path(self, ownersname: str, filename: str) -> Path:
        assert self._runtime_dir is not None
        dir = self._runtime_dir / f"{ownersname}/props"
        dir.mkdir(parents=True, exist_ok=True)
        return dir / f"{filename}.json"
################################################################################################################
    ## 写一个道具的文件
    def write_prop_file(self, propfile: PropFile) -> None:
        content = propfile.serialization()
        assert content is not None
        assert len(content) > 0
        assert propfile._owner_name is not None
        assert propfile._name is not None
        assert self._runtime_dir is not None
        
        prop_file_path = self.prop_file_path(propfile._owner_name, propfile._name)
        assert prop_file_path is not None

        try:
            res = prop_file_path.write_text(content, encoding="utf-8")
            assert res > 0
            #logger.info(f"写入文件成功: {prop_file_path}, res = {res}")
        except Exception as e:
            logger.error(f"写入文件失败: {prop_file_path}, e = {e}")
            return
################################################################################################################
    ## 添加一个道具文件
    def add_prop_file(self, propfile: PropFile, write: bool = True) -> None:
        self._prop_files.setdefault(propfile._owner_name, []).append(propfile)
        if write:
            self.write_prop_file(propfile)
################################################################################################################
    def get_prop_files(self, ownersname: str) -> List[PropFile]:
        return self._prop_files.get(ownersname, [])
################################################################################################################
    def get_prop_file(self, ownersname: str, propname: str) -> Optional[PropFile]:
        propfiles = self.get_prop_files(ownersname)
        for file in propfiles:
            if file._name == propname:
                return file
        return None
################################################################################################################
    def has_prop_file(self, ownersname: str, propname: str) -> bool:
        return self.get_prop_file(ownersname, propname) is not None
################################################################################################################
    def exchange_prop_file(self, from_owner: str, to_owner: str, propname: str) -> None:
        find_owners_file = self.get_prop_file(from_owner, propname)
        if find_owners_file is None:
            logger.error(f"{from_owner}没有{propname}这个道具。")
            return
        # 文件得从管理数据结构中移除掉
        self._prop_files[from_owner].remove(find_owners_file)
        # 文件得从文件系统中删除掉
        self.prop_file_path(from_owner, propname).unlink()
        #self.delete_file(self.prop_file_path(from_owner, propname))

        # 文件重新写入
        self.add_prop_file(PropFile(propname, to_owner, find_owners_file._prop, find_owners_file._count))
################################################################################################################
################################################################################################################
################################################################################################################
################################################################################################################
    def actor_archive_path(self, ownersname: str, filename: str) -> Path:
        assert self._runtime_dir is not None
        dir = self._runtime_dir / f"{ownersname}/actors_archive"
        dir.mkdir(parents=True, exist_ok=True)
        return dir / f"{filename}.json"
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
    def has_actor_archive(self, ownersname: str, actorname: str) -> bool:
        return self.get_actor_archive(ownersname, actorname) is not None
################################################################################################################
    def get_actor_archive(self, ownersname: str, actorname: str) -> Optional[ActorArchiveFile]:
        files = self._actor_archives.get(ownersname, [])
        for file in files:
            if file._actor_name == actorname:
                return file
        return None
################################################################################################################
    def write_actor_archive(self, actor_archive: ActorArchiveFile) -> None:
        ## 测试
        content = actor_archive.serialization()
        assert content is not None
        assert len(content) > 0

        archive_file_path = self.actor_archive_path(actor_archive._owner_name, actor_archive._name)
        assert archive_file_path is not None

        try:
            res = archive_file_path.write_text(content, encoding="utf-8")
            assert res > 0
            #logger.info(f"写入文件成功: {archive_file_path}, res = {res}")
        except Exception as e:
            logger.error(f"写入文件失败: {archive_file_path}, e = {e}")
            return
################################################################################################################
################################################################################################################
################################################################################################################
################################################################################################################
    def stage_archive_path(self, ownersname: str, filename: str) -> Path:
        assert self._runtime_dir is not None
        dir = self._runtime_dir / f"{ownersname}/stages_archive"
        dir.mkdir(parents=True, exist_ok=True)
        return dir / f"{filename}.json"
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
        content = stage_archive_file.serialization()
        assert content is not None
        assert len(content) > 0

        archive_file_path = self.stage_archive_path(stage_archive_file._owner_name, stage_archive_file._name)
        assert archive_file_path is not None

        try:
            res = archive_file_path.write_text(content, encoding="utf-8")
            assert res > 0
            #logger.info(f"写入文件成功: {archive_file_path}, res = {res}")
        except Exception as e:
            logger.error(f"写入文件失败: {archive_file_path}, e = {e}")
            return
################################################################################################################
    def get_stage_archive(self, ownersname: str, stagename: str) -> Optional[StageArchiveFile]:
        stagelist = self._stage_archives.get(ownersname, [])
        for file in stagelist:
            if file._stage_name == stagename:
                return file
        return None
################################################################################################################
    def has_stage_archive(self, ownersname: str, stagename: str) -> bool:
        return self.get_stage_archive(ownersname, stagename) is not None
################################################################################################################
################################################################################################################
################################################################################################################
################################################################################################################
    def status_profile_path(self, ownersname: str) -> Path:
        assert self._runtime_dir is not None
        dir = self._runtime_dir / f"{ownersname}"
        dir.mkdir(parents=True, exist_ok=True)
        return dir / f"status_profile.json"
################################################################################################################
    def write_status_profile(self, status_profile: StatusProfileFile) -> None:
        ## 测试
        content = status_profile.serialization()
        assert content is not None
        assert len(content) > 0

        status_profile_file_path = self.status_profile_path(status_profile._owner_name)
        assert status_profile_file_path is not None

        try:
            res = status_profile_file_path.write_text(content, encoding="utf-8")
            assert res > 0
        except Exception as e:
            logger.error(f"写入文件失败: {status_profile_file_path}, e = {e}")
            return
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
        dir.mkdir(parents=True, exist_ok=True)
        return dir / f"stage_actors_map.json"
################################################################################################################
    def set_stage_actors_map(self, stage_actors_map: StageActorsMapFile) -> None:
        self._stage_actors_map = stage_actors_map
################################################################################################################
    def write_stage_actors_map(self, stage_actors_map: StageActorsMapFile) -> None:
        ## 测试
        content = stage_actors_map.serialization()
        assert content is not None
        assert len(content) > 0

        _stage_actors_map_path = self.stage_actors_map_path()
        assert _stage_actors_map_path is not None

        try:
            res = _stage_actors_map_path.write_text(content, encoding="utf-8")
            assert res > 0
        except Exception as e:
            logger.error(f"写入文件失败: {_stage_actors_map_path}, e = {e}")
            return
################################################################################################################



