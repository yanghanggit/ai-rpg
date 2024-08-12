from typing import Set, Optional, List, Any, Dict
from file_system.files_def import PropFile, ActorArchiveFile, StageArchiveFile, StatusProfileFile, StageActorsMapFile
from file_system.file_system import FileSystem
from loguru import logger

##################################################################################################################################
# 为一个Actor添加他认识的其他Actor的文件
def add_actor_archive_files(file_system: FileSystem, owners_name: str, actor_archive_names: Set[str]) -> List[ActorArchiveFile]:

    assert file_system is not None

    ret: List[ActorArchiveFile] = []

    for actor_name in actor_archive_names:

        if owners_name == actor_name or file_system.has_file(ActorArchiveFile, owners_name, actor_name):
            continue

        archive_file = ActorArchiveFile(actor_name, owners_name, actor_name, "")
        file_system.add_file(archive_file)
        file_system.write_file(archive_file)
        ret.append(archive_file)

    return ret
##################################################################################################################################
# 更新一个Actor的档案文件
def update_actor_archive_file(file_system: FileSystem, owner_name: str, actor_name: str, appearance: str) -> Optional[ActorArchiveFile]:
    
    file = file_system.get_file(ActorArchiveFile, owner_name, actor_name)
    if file is None:
        return None
    
    file._appearance = appearance
    file_system.write_file(file)
    return file
##################################################################################################################################
## 为一个Actor添加他认识的Stage的文件
def add_stage_archive_files(file_system: FileSystem, my_name: str, stage_names: Set[str]) -> List[StageArchiveFile]:
    
    ret: List[StageArchiveFile] = []

    for stage_name in stage_names:

        if my_name == stage_name or file_system.has_file(StageArchiveFile, my_name, stage_name):
            continue
        
        file = StageArchiveFile(stage_name, my_name, stage_name)
        file_system.add_file(file)
        file_system.write_file(file)
        ret.append(file)
    
    return ret
##################################################################################################################################
## 更新角色的属性文件并记录下来～
def update_status_profile_file(file_system: FileSystem, owner_name: str, update_data: Dict[str, Any]) -> Optional[StatusProfileFile]:
    file = StatusProfileFile(owner_name, owner_name, update_data)
    file_system.add_file(file)
    file_system.write_file(file)
    return file
##################################################################################################################################
# 场景中有哪些人的总文件。
def update_stage_actors_map_file(file_system: FileSystem, update_data: Dict[str, List[str]]) -> Optional[StageActorsMapFile]:
    file = StageActorsMapFile(update_data)
    file_system.add_file(file)
    file_system.write_file(file)
    return file
##################################################################################################################################
def give_prop_file(file_system: FileSystem, from_owner: str, to_owner: str, prop_name: str) -> Optional[PropFile]:
    find_owners_file = file_system.get_file(PropFile, from_owner, prop_name)
    if find_owners_file is None:
        logger.error(f"{from_owner}没有{prop_name}这个道具。")
        return None
    # 文件得从管理数据结构中移除掉
    file_system.remove_file(find_owners_file)
    # 文件重新写入
    new_file = PropFile(prop_name, to_owner, find_owners_file._prop_model, find_owners_file._count)
    file_system.add_file(new_file)
    file_system.write_file(new_file)
    return new_file
##################################################################################################################################