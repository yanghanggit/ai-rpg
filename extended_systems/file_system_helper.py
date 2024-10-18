from typing import Set, Optional, List, Dict
from extended_systems.files_def import (
    PropFile,
    ActorArchiveFile,
    StageArchiveFile,
    EntityProfileFile,
    # MapFile,
)
from extended_systems.file_system import FileSystem
from loguru import logger
from my_data.model_def import EntityProfileModel


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
def update_entity_profile_file(
    file_system: FileSystem, owner_name: str, entity_dump_model: EntityProfileModel
) -> Optional[EntityProfileFile]:
    file = EntityProfileFile(owner_name, owner_name, entity_dump_model)
    file_system.add_file(file)
    file_system.write_file(file)
    return file


##################################################################################################################################
# 场景中有哪些人的总文件。
# def update_map_file(
#     file_system: FileSystem, update_data: Dict[str, List[str]]
# ) -> Optional[MapFile]:
#     file = MapFile(update_data)
#     file_system.add_file(file)
#     file_system.write_file(file)
#     return file


##################################################################################################################################
def give_prop_file(
    file_system: FileSystem, from_name: str, target_name: str, prop_name: str
) -> None:

    exchange_prop_file(file_system, from_name, target_name, prop_name, "")


##################################################################################################################################


def exchange_prop_file(
    file_system: FileSystem,
    left_owner_name: str,
    right_owner_name: str,
    left_prop_name: str,
    right_prop_name: str,
) -> None:

    left_prop_file = file_system.get_file(PropFile, left_owner_name, left_prop_name)
    if left_prop_file is not None:

        file_system.remove_file(left_prop_file)

        # 文件重新写入
        new_file1 = PropFile(
            left_prop_file._guid,
            left_prop_file.name,
            right_owner_name,  ###!!!!!!
            left_prop_file._prop_model,
            left_prop_file._count,
        )

        file_system.add_file(new_file1)
        file_system.write_file(new_file1)

    right_prop_file = file_system.get_file(PropFile, right_owner_name, right_prop_name)
    if right_prop_file is not None:

        file_system.remove_file(right_prop_file)

        # 文件重新写入
        new_file2 = PropFile(
            right_prop_file._guid,
            right_prop_file.name,
            left_owner_name,  ###!!!!!!
            right_prop_file._prop_model,
            right_prop_file._count,
        )

        file_system.add_file(new_file2)
        file_system.write_file(new_file2)

    return None


##################################################################################################################################
def get_categorized_files(
    file_system: FileSystem, from_owner: str
) -> Dict[str, List[PropFile]]:
    ret: Dict[str, List[PropFile]] = {}
    for file in file_system.get_files(PropFile, from_owner):
        if file._prop_model.type not in ret:
            ret[file._prop_model.type] = []
        ret[file._prop_model.type].append(file)
    return ret


##################################################################################################################################
def consume_consumable(
    file_system: FileSystem, prop: PropFile, consume_count: int = 1
) -> bool:
    if not prop.is_consumable_item:
        return False

    if prop._count < consume_count:
        logger.error(f"consume_consumable: {prop.name} count is not enough.")
        return False

    prop._count -= consume_count
    file_system.write_file(prop)
    return True


##################################################################################################################################
