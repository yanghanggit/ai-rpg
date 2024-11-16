from typing import Set, Optional, List, Dict
from extended_systems.archive_file import ActorArchiveFile, StageArchiveFile
from extended_systems.prop_file import PropFile
from extended_systems.file_system import FileSystem
from loguru import logger
from my_models.file_models import (
    EntityProfileModel,
    PropFileModel,
    ActorArchiveFileModel,
    StageArchiveFileModel,
)
from extended_systems.dump_file import EntityProfileFile


##################################################################################################################################
def register_actor_archives(
    file_system: FileSystem, archive_owner: str, actor_names_to_register: Set[str]
) -> List[ActorArchiveFile]:

    ret: List[ActorArchiveFile] = []

    for actor_name in actor_names_to_register:

        if archive_owner == actor_name or file_system.has_file(
            ActorArchiveFile, archive_owner, actor_name
        ):
            continue

        archive_file = ActorArchiveFile(
            ActorArchiveFileModel(name=actor_name, owner=archive_owner, appearance="")
        )
        file_system.add_file(archive_file)
        file_system.write_file(archive_file)
        ret.append(archive_file)

    return ret


##################################################################################################################################
def register_stage_archives(
    file_system: FileSystem, archive_owner: str, stage_names_to_register: Set[str]
) -> List[StageArchiveFile]:

    ret: List[StageArchiveFile] = []

    for stage_name in stage_names_to_register:

        if archive_owner == stage_name or file_system.has_file(
            StageArchiveFile, archive_owner, stage_name
        ):
            continue

        archive_file = StageArchiveFile(
            StageArchiveFileModel(
                name=stage_name, owner=archive_owner, stage_narrate="", stage_tags=[]
            )
        )
        file_system.add_file(archive_file)
        file_system.write_file(archive_file)
        ret.append(archive_file)

    return ret


##################################################################################################################################
def persist_entity_profile(
    file_system: FileSystem, entity_profile_model: EntityProfileModel
) -> Optional[EntityProfileFile]:
    file = EntityProfileFile(entity_profile_model)
    file_system.add_file(file)
    file_system.write_file(file)
    return file


##################################################################################################################################
def transfer_file(
    file_system: FileSystem, source_name: str, target_name: str, file_name: str
) -> None:

    swap_file(file_system, source_name, target_name, file_name, "")


##################################################################################################################################
def swap_file(
    file_system: FileSystem,
    left_file_owner: str,
    right_file_owner: str,
    left_file_name: str,
    right_file_name: str,
) -> None:

    left_file = file_system.get_file(PropFile, left_file_owner, left_file_name)
    if left_file is not None:

        file_system.remove_file(left_file)

        # 文件重新写入
        swapped_left_file_copy = PropFile(
            PropFileModel(
                owner=right_file_owner,
                prop_model=left_file.prop_model,
                prop_instance_model=left_file.prop_instance_model,
            ),
        )

        file_system.add_file(swapped_left_file_copy)
        file_system.write_file(swapped_left_file_copy)

    right_file = file_system.get_file(PropFile, right_file_owner, right_file_name)
    if right_file is not None:

        file_system.remove_file(right_file)

        # 文件重新写入
        swapped_right_file_copy = PropFile(
            PropFileModel(
                owner=left_file_owner,
                prop_model=right_file.prop_model,
                prop_instance_model=right_file.prop_instance_model,
            ),
        )

        file_system.add_file(swapped_right_file_copy)
        file_system.write_file(swapped_right_file_copy)


##################################################################################################################################
def categorize_files_by_type(
    file_system: FileSystem, owner_name: str
) -> Dict[str, List[PropFile]]:

    ret: Dict[str, List[PropFile]] = {}

    for file in file_system.get_files(PropFile, owner_name):
        if file.prop_model.type not in ret:
            ret[file.prop_model.type] = []
        ret[file.prop_model.type].append(file)

    return ret


##################################################################################################################################
def consume_file(
    file_system: FileSystem, prop_file: PropFile, consume_count: int = 1
) -> None:

    prop_file.consume(consume_count)
    if prop_file.count == 0:
        file_system.remove_file(prop_file)
        return

    file_system.write_file(prop_file)


##################################################################################################################################
def load_actor_archives(
    file_system: FileSystem,
    owners_name: str,
    load_archives_model: List[ActorArchiveFileModel],
) -> List[ActorArchiveFile]:

    ret: List[ActorArchiveFile] = []

    for file_model in load_archives_model:

        actor_archive_file = file_system.get_file(
            ActorArchiveFile, owners_name, file_model.name
        )
        if actor_archive_file is None:
            # 添加新的
            file = ActorArchiveFile(file_model)
            file_system.add_file(file)
            file_system.write_file(file)
            ret.append(file)

        else:

            # 更新已有的
            actor_archive_file.update(file_model)
            file_system.write_file(actor_archive_file)
            ret.append(actor_archive_file)

    return ret


##################################################################################################################################
def load_stage_archives(
    file_system: FileSystem,
    owners_name: str,
    load_archives_model: List[StageArchiveFileModel],
) -> List[StageArchiveFile]:

    ret: List[StageArchiveFile] = []

    for file_model in load_archives_model:

        stage_archive_file = file_system.get_file(
            StageArchiveFile, owners_name, file_model.name
        )
        if stage_archive_file is None:

            # 添加新的
            file = StageArchiveFile(file_model)
            file_system.add_file(file)
            file_system.write_file(file)
            ret.append(file)

        else:

            # 更新已有的
            stage_archive_file.update(file_model)
            file_system.write_file(stage_archive_file)
            ret.append(stage_archive_file)

    return ret


##################################################################################################################################
