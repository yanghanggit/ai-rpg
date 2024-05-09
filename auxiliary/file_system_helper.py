from typing import Set, Optional
from auxiliary.file_def import NPCArchiveFile
from auxiliary.file_system import FileSystem


# 为一个NPC添加他认识的其他NPC的文件
def create_npc_archive_files(file_system: FileSystem, myname: str, others_names: Set[str]) -> None:
    for targetname in others_names:
        if myname == targetname:
            continue
        if file_system.has_npc_archive_file(myname, targetname):
            continue
        file = NPCArchiveFile(targetname, myname, targetname)
        file_system.add_npc_archive_file(file)
        file_system.write_npc_archive_file(file)

# 更新一个NPC的档案文件
def update_npc_archive_file(file_system: FileSystem, ownersname: str, npcname: str, appearance: str) -> Optional[NPCArchiveFile]:
    file = file_system.get_npc_archive_file(ownersname, npcname)
    if file is None:
        return None
    file.last_appearance = appearance
    file_system.write_npc_archive_file(file)
    return file