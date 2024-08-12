from typing import Set, Optional, List, Any, Dict
from file_system.files_def import ActorArchiveFile, StageArchiveFile, StatusProfileFile, StageActorsMapFile
from file_system.file_system import FileSystem

##################################################################################################################################
# 为一个Actor添加他认识的其他Actor的文件
def add_actor_archive_files(file_system: FileSystem, owners_name: str, actor_archive_names: Set[str]) -> List[ActorArchiveFile]:

    assert file_system is not None

    ret: List[ActorArchiveFile] = []

    for actor_name in actor_archive_names:

        if owners_name == actor_name or file_system.has_actor_archive(owners_name, actor_name):
            continue

        archive_file = ActorArchiveFile(actor_name, owners_name, actor_name, "")
        file_system.add_actor_archive(archive_file)
        file_system.write_actor_archive(archive_file)
        ret.append(archive_file)

    return ret
##################################################################################################################################
# 更新一个Actor的档案文件
def update_actor_archive_file(file_system: FileSystem, owner_name: str, actor_name: str, appearance: str) -> Optional[ActorArchiveFile]:
    
    file = file_system.get_actor_archive(owner_name, actor_name)
    
    if file is None:
        return None
    file._appearance = appearance
    file_system.write_actor_archive(file)
    
    return file
##################################################################################################################################
## 为一个Actor添加他认识的Stage的文件
def add_stage_archive_files(file_system: FileSystem, my_name: str, stage_names: Set[str]) -> List[StageArchiveFile]:
    
    res: List[StageArchiveFile] = []

    for stagename in stage_names:
        if my_name == stagename or file_system.has_stage_archive(my_name, stagename):
            continue
        file = StageArchiveFile(stagename, my_name, stagename)
        file_system.add_stage_archive(file)
        file_system.write_stage_archive(file)
        res.append(file)
    
    return res
##################################################################################################################################
## 更新角色的属性文件并记录下来～
def update_status_profile_file(file_system: FileSystem, owner_name: str, update_data: Dict[str, Any]) -> Optional[StatusProfileFile]:
    file = StatusProfileFile(owner_name, owner_name, update_data)
    file_system.set_status_profile(file)
    file_system.write_status_profile(file)
    return file
##################################################################################################################################
# 场景中有哪些人的总文件。
def update_stage_actors_map_file(file_system: FileSystem, update_data: Dict[str, List[str]]) -> Optional[StageActorsMapFile]:
    file = StageActorsMapFile(update_data)
    file_system.set_stage_actors_map(file)
    file_system.write_stage_actors_map(file)
    return file
##################################################################################################################################