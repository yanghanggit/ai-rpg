from typing import Set, Optional, List, Any, Dict
from file_system.files_def import (
    PropFile,
    ActorArchiveFile,
    StageArchiveFile,
    StatusProfileFile,
    StageActorsMapFile,
)
from file_system.file_system import FileSystem
from loguru import logger


##################################################################################################################################
def add_actor_archive_files(
    file_system: FileSystem, owners_name: str, actor_archive_names: Set[str]
) -> List[ActorArchiveFile]:

    ret: List[ActorArchiveFile] = []

    for actor_name in actor_archive_names:

        if owners_name == actor_name or file_system.has_file(
            ActorArchiveFile, owners_name, actor_name
        ):
            continue

        archive_file = ActorArchiveFile(actor_name, owners_name, actor_name, "")
        file_system.add_file(archive_file)
        file_system.write_file(archive_file)
        ret.append(archive_file)

    return ret


##################################################################################################################################
def add_stage_archive_files(
    file_system: FileSystem, my_name: str, stage_names: Set[str]
) -> List[StageArchiveFile]:

    ret: List[StageArchiveFile] = []

    for stage_name in stage_names:

        if my_name == stage_name or file_system.has_file(
            StageArchiveFile, my_name, stage_name
        ):
            continue

        file = StageArchiveFile(stage_name, my_name, stage_name)
        file_system.add_file(file)
        file_system.write_file(file)
        ret.append(file)

    return ret


##################################################################################################################################
## 更新角色的属性文件并记录下来～
def update_status_profile_file(
    file_system: FileSystem, owner_name: str, update_data: Dict[str, Any]
) -> Optional[StatusProfileFile]:
    file = StatusProfileFile(owner_name, owner_name, update_data)
    file_system.add_file(file)
    file_system.write_file(file)
    return file


##################################################################################################################################
# 场景中有哪些人的总文件。
def update_stage_actors_map_file(
    file_system: FileSystem, update_data: Dict[str, List[str]]
) -> Optional[StageActorsMapFile]:
    file = StageActorsMapFile(update_data)
    file_system.add_file(file)
    file_system.write_file(file)
    return file


##################################################################################################################################
def give_prop_file(
    file_system: FileSystem, from_name: str, target_name: str, prop_name: str
) -> None:

    exchange_prop_file(file_system, from_name, target_name, prop_name, "")

    # found_file = file_system.get_file(PropFile, from_name, prop_name)
    # if found_file is None:
    #     logger.error(f"{from_name}没有{prop_name}这个道具。")
    #     return None

    # # 文件得从管理数据结构中移除掉
    # file_system.remove_file(found_file)

    # # 文件重新写入
    # new_file = PropFile(
    #     found_file._guid,
    #     prop_name,
    #     target_name,
    #     found_file._prop_model,
    #     found_file._count,
    # )
    # file_system.add_file(new_file)
    # file_system.write_file(new_file)
    # return new_file


##################################################################################################################################


def exchange_prop_file(
    file_system: FileSystem,
    left_owner_name: str,
    right_owner_name: str,
    left_prop_name: str,
    right_prop_name: str,
) -> None:

    from_file = file_system.get_file(PropFile, left_owner_name, left_prop_name)
    if from_file is not None:

        file_system.remove_file(from_file)

        # 文件重新写入
        new_file1 = PropFile(
            from_file._guid,
            from_file.name,
            right_owner_name,  ###!!!!!!
            from_file._prop_model,
            from_file._count,
        )

        file_system.add_file(new_file1)
        file_system.write_file(new_file1)

    target_file = file_system.get_file(PropFile, right_owner_name, right_prop_name)
    if target_file is not None:

        file_system.remove_file(target_file)

        # 文件重新写入
        new_file2 = PropFile(
            target_file._guid,
            target_file.name,
            left_owner_name,  ###!!!!!!
            target_file._prop_model,
            target_file._count,
        )

        file_system.add_file(new_file2)
        file_system.write_file(new_file2)

    return None


##################################################################################################################################
def get_categorized_files_dict(
    file_system: FileSystem, from_owner: str
) -> Dict[str, List[PropFile]]:
    ret: Dict[str, List[PropFile]] = {}
    for file in file_system.get_files(PropFile, from_owner):
        if file._prop_model.type not in ret:
            ret[file._prop_model.type] = []
        ret[file._prop_model.type].append(file)
    return ret


##################################################################################################################################
