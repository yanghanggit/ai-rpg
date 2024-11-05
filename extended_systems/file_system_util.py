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
def add_actor_archive_files(
    file_system: FileSystem, owners_name: str, actor_archive_names: Set[str]
) -> List[ActorArchiveFile]:

    ret: List[ActorArchiveFile] = []

    for actor_name in actor_archive_names:

        if owners_name == actor_name or file_system.has_file(
            ActorArchiveFile, owners_name, actor_name
        ):
            continue

        archive_file = ActorArchiveFile(
            ActorArchiveFileModel(name=actor_name, owner=owners_name, appearance="")
        )
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

        file = StageArchiveFile(
            StageArchiveFileModel(name=stage_name, owner=my_name, stage_narrate="")
        )
        file_system.add_file(file)
        file_system.write_file(file)
        ret.append(file)

    return ret


##################################################################################################################################
def update_entity_profile_file(
    file_system: FileSystem, entity_profile_model: EntityProfileModel
) -> Optional[EntityProfileFile]:
    file = EntityProfileFile(entity_profile_model)
    file_system.add_file(file)
    file_system.write_file(file)
    return file


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
            PropFileModel(
                owner=right_owner_name,
                prop_model=left_prop_file.prop_model,
                prop_instance_model=left_prop_file.prop_instance_model,
            ),
        )

        file_system.add_file(new_file1)
        file_system.write_file(new_file1)

    right_prop_file = file_system.get_file(PropFile, right_owner_name, right_prop_name)
    if right_prop_file is not None:

        file_system.remove_file(right_prop_file)

        # 文件重新写入
        new_file2 = PropFile(
            PropFileModel(
                owner=left_owner_name,
                prop_model=right_prop_file.prop_model,
                prop_instance_model=right_prop_file.prop_instance_model,
            ),
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
        if file.prop_model.type not in ret:
            ret[file.prop_model.type] = []
        ret[file.prop_model.type].append(file)
    return ret


##################################################################################################################################
def consume_consumable(
    file_system: FileSystem, prop_file: PropFile, consume_count: int = 1
) -> bool:
    if not prop_file.is_consumable_item:
        return False

    if prop_file.count < consume_count:
        logger.error(f"consume_consumable: {prop_file.name} count is not enough.")
        return False

    prop_file.decrease_count(consume_count)
    if prop_file.count == 0:
        file_system.remove_file(prop_file)
        return True

    file_system.write_file(prop_file)
    return True


##################################################################################################################################
def load_actor_archive_files(
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
def load_stage_archive_files(
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
