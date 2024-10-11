from loguru import logger
from typing import Dict, List, Optional, TypeVar, Type, cast
from extended_systems.files_def import (
    BaseFile,
    PropFile,
    ActorArchiveFile,
    StageArchiveFile,
    EntityDumpFile,
    MapFile,
)
from pathlib import Path


FileType = TypeVar("FileType")


class FileSystem:

    def __init__(self, name: str) -> None:

        self._name: str = name

        self._runtime_dir: Optional[Path] = None

        self._prop_files: Dict[str, List[PropFile]] = {}

        self._actor_archives: Dict[str, List[ActorArchiveFile]] = {}

        self._stage_archives: Dict[str, List[StageArchiveFile]] = {}

        self._status_profile: Dict[str, EntityDumpFile] = {}

        self._stage_actors_map: MapFile = MapFile({})

    ###############################################################################################################################################
    def parse_path(self, file: BaseFile) -> Optional[Path]:

        assert self._runtime_dir is not None

        if isinstance(file, PropFile):
            dir = self._runtime_dir / f"{file._owner_name}/props"
            dir.mkdir(parents=True, exist_ok=True)
            return dir / f"{file._name}.json"

        elif isinstance(file, ActorArchiveFile):
            dir = self._runtime_dir / f"{file._owner_name}/actor_archives"
            dir.mkdir(parents=True, exist_ok=True)
            return dir / f"{file._name}.json"

        elif isinstance(file, StageArchiveFile):
            dir = self._runtime_dir / f"{file._owner_name}/stage_archives"
            dir.mkdir(parents=True, exist_ok=True)
            return dir / f"{file._name}.json"

        elif isinstance(file, EntityDumpFile):
            dir = self._runtime_dir / f"{file._owner_name}"
            dir.mkdir(parents=True, exist_ok=True)
            return dir / f"entity.json"

        elif isinstance(file, MapFile):
            dir = self._runtime_dir
            dir.mkdir(parents=True, exist_ok=True)
            return dir / f"map.json"

        return None

    ###############################################################################################################################################
    def write_file(self, file: BaseFile) -> int:
        assert self._runtime_dir is not None
        assert file is not None
        file_path = self.parse_path(file)
        assert file_path is not None
        return file.write(file_path)

    ###############################################################################################################################################
    ### 必须设置根部的执行路行
    def set_runtime_dir(self, runtime_dir: Path) -> None:
        assert runtime_dir is not None
        self._runtime_dir = runtime_dir
        self._runtime_dir.mkdir(parents=True, exist_ok=True)
        assert runtime_dir.exists()
        assert (
            self._runtime_dir.is_dir()
        ), f"Directory is not a directory: {self._runtime_dir}"

    ###############################################################################################################################################
    def add_file(self, file: BaseFile) -> bool:

        if isinstance(file, PropFile):

            if file.is_consumable_item:
                exist_file = self.get_file(PropFile, file._owner_name, file._name)
                if exist_file is not None:
                    assert exist_file.is_consumable_item
                    exist_file._count += file._count
                    return True

            return self.add_file_2_base_file_dict(
                cast(Dict[str, List[BaseFile]], self._prop_files), file
            )
        elif isinstance(file, ActorArchiveFile):
            return self.add_file_2_base_file_dict(
                cast(Dict[str, List[BaseFile]], self._actor_archives), file
            )
        elif isinstance(file, StageArchiveFile):
            return self.add_file_2_base_file_dict(
                cast(Dict[str, List[BaseFile]], self._stage_archives), file
            )
        elif isinstance(file, EntityDumpFile):
            self._status_profile[file._owner_name] = file
            return True
        elif isinstance(file, MapFile):
            self._stage_actors_map = file
            return True
        else:
            logger.error(f"file type {type(file)} not support")

        return False

    ###############################################################################################################################################
    def remove_file(self, file: BaseFile) -> bool:

        if isinstance(file, PropFile):
            self._prop_files[file._owner_name].remove(file)
        elif isinstance(file, ActorArchiveFile):
            self._actor_archives[file._owner_name].remove(file)
        elif isinstance(file, StageArchiveFile):
            self._stage_archives[file._owner_name].remove(file)
        elif isinstance(file, EntityDumpFile):
            self._status_profile.pop(file._owner_name, None)
        elif isinstance(file, MapFile):
            self._stage_actors_map = MapFile({})
        else:
            logger.error(f"file type {type(file)} not support")
            return False

        file_path = self.parse_path(file)
        assert file_path is not None
        if file_path.exists():
            file_path.unlink()

        return True

    ###############################################################################################################################################
    def get_file(
        self, file_type: Type[FileType], owner_name: str, file_name: str
    ) -> Optional[FileType]:

        if file_type == PropFile:
            return cast(
                Optional[FileType],
                self.get_file_from_base_file_dict(
                    cast(Dict[str, List[BaseFile]], self._prop_files),
                    owner_name,
                    file_name,
                ),
            )
        elif file_type == ActorArchiveFile:
            return cast(
                Optional[FileType],
                self.get_file_from_base_file_dict(
                    cast(Dict[str, List[BaseFile]], self._actor_archives),
                    owner_name,
                    file_name,
                ),
            )
        elif file_type == StageArchiveFile:
            return cast(
                Optional[FileType],
                self.get_file_from_base_file_dict(
                    cast(Dict[str, List[BaseFile]], self._stage_archives),
                    owner_name,
                    file_name,
                ),
            )
        elif file_type == EntityDumpFile:
            return cast(Optional[FileType], self._status_profile.get(owner_name, None))
        elif file_type == MapFile:
            return cast(Optional[FileType], self._stage_actors_map)
        else:
            logger.error(f"file type {file_type} not support")

        return None

    ###############################################################################################################################################
    def get_files(self, file_type: Type[FileType], owner_name: str) -> List[FileType]:

        if file_type == PropFile:
            return cast(List[FileType], self._prop_files.get(owner_name, []))
        elif file_type == ActorArchiveFile:
            return cast(List[FileType], self._actor_archives.get(owner_name, []))
        elif file_type == StageArchiveFile:
            return cast(List[FileType], self._stage_archives.get(owner_name, []))
        elif file_type == EntityDumpFile:
            return cast(List[FileType], [self._status_profile.get(owner_name, None)])
        elif file_type == MapFile:
            return cast(List[FileType], [self._stage_actors_map])
        else:
            logger.error(f"file type {file_type} not support")

        return []

    ###############################################################################################################################################
    def has_file(
        self, file_type: Type[FileType], owner_name: str, file_name: str
    ) -> bool:

        if file_type == PropFile:
            return self.get_file(PropFile, owner_name, file_name) is not None
        elif file_type == ActorArchiveFile:
            return self.get_file(ActorArchiveFile, owner_name, file_name) is not None
        elif file_type == StageArchiveFile:
            return self.get_file(StageArchiveFile, owner_name, file_name) is not None
        elif file_type == EntityDumpFile:
            return owner_name in self._status_profile
        elif file_type == MapFile:
            return self._stage_actors_map is not None
        else:
            logger.error(f"file type {file_type} not support")

        return False

    ###############################################################################################################################################
    def add_file_2_base_file_dict(
        self, data: Dict[str, List[BaseFile]], new_file: BaseFile
    ) -> bool:
        files = data.setdefault(new_file._owner_name, [])
        for file in files:
            if file._name == new_file._name:
                return False
        files.append(new_file)
        return True

    ###############################################################################################################################################
    def get_file_from_base_file_dict(
        self, data: Dict[str, List[BaseFile]], owner_name: str, file_name: str
    ) -> Optional[BaseFile]:
        files = data.get(owner_name, [])
        for file in files:
            if file._name == file_name:
                return file
        return None

    ###############################################################################################################################################
    def get_base_file_dict(
        self, file_type: Type[FileType]
    ) -> Dict[str, List[BaseFile]]:
        if file_type == PropFile:
            return cast(Dict[str, List[BaseFile]], self._prop_files)
        elif file_type == ActorArchiveFile:
            return cast(Dict[str, List[BaseFile]], self._actor_archives)
        elif file_type == StageArchiveFile:
            return cast(Dict[str, List[BaseFile]], self._stage_archives)
        else:
            logger.error(f"file type {file_type} not support")
        return {}


###############################################################################################################################################
