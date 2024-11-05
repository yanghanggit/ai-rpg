from loguru import logger
from typing import Dict, List, Optional, TypeVar, Type, cast, final
from extended_systems.base_file import (
    BaseFile,
)
from pathlib import Path
from extended_systems.prop_file import PropFile
from extended_systems.archive_file import ActorArchiveFile, StageArchiveFile
from extended_systems.dump_file import EntityProfileFile

FileType = TypeVar("FileType")


@final
class FileSystem:

    def __init__(self, name: str) -> None:

        self._name: str = name

        self._runtime_dir: Optional[Path] = None

        self._prop_files: Dict[str, List[PropFile]] = {}

        self._actor_archives: Dict[str, List[ActorArchiveFile]] = {}

        self._stage_archives: Dict[str, List[StageArchiveFile]] = {}

        self._entity_profiles: Dict[str, EntityProfileFile] = {}

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

        elif isinstance(file, EntityProfileFile):
            dir = self._runtime_dir / f"{file._owner_name}"
            dir.mkdir(parents=True, exist_ok=True)
            return dir / f"entity.json"

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
                    # exist_file._count += file._count
                    exist_file.increase_count(file.count)
                    return True

            return self._add_file_2_base_file_dict(
                cast(Dict[str, List[BaseFile]], self._prop_files), file
            )
        elif isinstance(file, ActorArchiveFile):
            return self._add_file_2_base_file_dict(
                cast(Dict[str, List[BaseFile]], self._actor_archives), file
            )
        elif isinstance(file, StageArchiveFile):
            return self._add_file_2_base_file_dict(
                cast(Dict[str, List[BaseFile]], self._stage_archives), file
            )
        elif isinstance(file, EntityProfileFile):
            self._entity_profiles[file._owner_name] = file
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
        elif isinstance(file, EntityProfileFile):
            self._entity_profiles.pop(file._owner_name, None)
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
                self._get_file_from_base_file_dict(
                    cast(Dict[str, List[BaseFile]], self._prop_files),
                    owner_name,
                    file_name,
                ),
            )
        elif file_type == ActorArchiveFile:
            return cast(
                Optional[FileType],
                self._get_file_from_base_file_dict(
                    cast(Dict[str, List[BaseFile]], self._actor_archives),
                    owner_name,
                    file_name,
                ),
            )
        elif file_type == StageArchiveFile:
            return cast(
                Optional[FileType],
                self._get_file_from_base_file_dict(
                    cast(Dict[str, List[BaseFile]], self._stage_archives),
                    owner_name,
                    file_name,
                ),
            )
        elif file_type == EntityProfileFile:
            return cast(Optional[FileType], self._entity_profiles.get(owner_name, None))
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
        elif file_type == EntityProfileFile:
            return cast(List[FileType], [self._entity_profiles.get(owner_name, None)])
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
        elif file_type == EntityProfileFile:
            return owner_name in self._entity_profiles
        else:
            logger.error(f"file type {file_type} not support")

        return False

    ###############################################################################################################################################
    def _add_file_2_base_file_dict(
        self, data: Dict[str, List[BaseFile]], new_file: BaseFile
    ) -> bool:
        files = data.setdefault(new_file._owner_name, [])
        for file in files:
            if file._name == new_file._name:
                return False
        files.append(new_file)
        return True

    ###############################################################################################################################################
    def _get_file_from_base_file_dict(
        self, data: Dict[str, List[BaseFile]], owner_name: str, file_name: str
    ) -> Optional[BaseFile]:
        files = data.get(owner_name, [])
        for file in files:
            if file._name == file_name:
                return file
        return None

    ###############################################################################################################################################
