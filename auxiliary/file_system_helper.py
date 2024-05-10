from typing import Set, Optional, List
from auxiliary.file_def import NPCArchiveFile, StageArchiveFile
from auxiliary.file_system import FileSystem


# 为一个NPC添加他认识的其他NPC的文件
def add_npc_archive_files(file_system: FileSystem, myname: str, others_names: Set[str]) -> List[NPCArchiveFile]:

    res: List[NPCArchiveFile] = []

    for targetname in others_names:
        if myname == targetname or file_system.has_npc_archive_file(myname, targetname):
            continue
        file = NPCArchiveFile(targetname, myname, targetname, "")
        file_system.add_npc_archive_file(file)
        file_system.write_npc_archive_file(file)
        res.append(file)

    return res

# 更新一个NPC的档案文件
def update_npc_archive_file(file_system: FileSystem, ownersname: str, npcname: str, appearance: str) -> Optional[NPCArchiveFile]:
    file = file_system.get_npc_archive_file(ownersname, npcname)
    if file is None:
        return None
    file.appearance = appearance
    file_system.write_npc_archive_file(file)
    return file

## 为一个NPC添加他认识的Stage的文件
def add_stage_archive_files(file_system: FileSystem, myname: str, stage_names: Set[str]) -> List[StageArchiveFile]:
    
    res: List[StageArchiveFile] = []

    for stagename in stage_names:
        if myname == stagename:
            continue
        file = StageArchiveFile(stagename, myname, stagename)
        file_system.add_stage_archive_file(file)
        file_system.write_stage_archive_file(file)
        res.append(file)
    
    return res