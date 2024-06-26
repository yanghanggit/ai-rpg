from typing import Set, Optional, List, Any, Dict
from file_system.files_def import ActorArchiveFile, StageArchiveFile, StatusProfileFile, StageActorsMapFile
from file_system.file_system import FileSystem

##################################################################################################################################
# 为一个Actor添加他认识的其他Actor的文件
def add_actor_archive_files(file_system: FileSystem, myname: str, others_names: Set[str]) -> List[ActorArchiveFile]:

    res: List[ActorArchiveFile] = []

    for targetname in others_names:
        if myname == targetname or file_system.has_actor_archive(myname, targetname):
            continue
        file = ActorArchiveFile(targetname, myname, targetname, "")
        file_system.add_actor_archive(file)
        file_system.write_actor_archive(file)
        res.append(file)

    return res
##################################################################################################################################
# 更新一个Actor的档案文件
def update_actor_archive_file(file_system: FileSystem, ownersname: str, actorname: str, appearance: str) -> Optional[ActorArchiveFile]:
    file = file_system.get_actor_archive(ownersname, actorname)
    if file is None:
        return None
    file._appearance = appearance
    file_system.write_actor_archive(file)
    return file
##################################################################################################################################
## 为一个Actor添加他认识的Stage的文件
def add_stage_archive_files(file_system: FileSystem, myname: str, stage_names: Set[str]) -> List[StageArchiveFile]:
    
    res: List[StageArchiveFile] = []

    for stagename in stage_names:
        if myname == stagename or file_system.has_stage_archive(myname, stagename):
            continue
        file = StageArchiveFile(stagename, myname, stagename)
        file_system.add_stage_archive(file)
        file_system.write_stage_archive(file)
        res.append(file)
    
    return res
##################################################################################################################################
## 更新角色的属性文件并记录下来～
def update_status_profile_file(file_system: FileSystem, ownersname: str, update_data: Dict[str, Any]) -> Optional[StatusProfileFile]:
    file = StatusProfileFile(ownersname, ownersname, update_data)
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