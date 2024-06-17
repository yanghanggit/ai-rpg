from loguru import logger
from typing import Dict, Optional
from pathlib import Path

####################################################################################################################################
## 第一次初始化的时候，会做读取来确定角色初始上下文（记忆）
class KickOffMemorySystem:
    def __init__(self, name: str) -> None:
        self.name: str = name
        self.kick_off_memories: Dict[str, str] = {}
        self._runtime_dir: Optional[Path] = None
####################################################################################################################################
    def set_runtime_dir(self, runtime_dir: Path) -> None:
        assert runtime_dir is not None
        self._runtime_dir = runtime_dir
        self._runtime_dir.mkdir(parents=True, exist_ok=True)
        assert runtime_dir.exists()
        assert self._runtime_dir.is_dir(), f"Directory is not a directory: {self._runtime_dir}"
####################################################################################################################################
    def md_file_path(self, who: str) -> Path:
        assert self._runtime_dir is not None
        dir = self._runtime_dir / f"{who}"
        dir.mkdir(parents=True, exist_ok=True)
        return dir / f"kick_off_memory.md"
####################################################################################################################################
    def add_kick_off_memory(self, who: str, kick_off_memory_content: str) -> None:
        #初始化
        self.write_md(who, kick_off_memory_content)
        #初始化成功了
        mm = self.read_md(who)
        assert mm is not None
        if mm is not None:
            assert mm == kick_off_memory_content
            self.kick_off_memories[who] = mm
####################################################################################################################################
    def read_md(self, who: str) -> Optional[str]:

        file_path = self.md_file_path(who)
        if not file_path.exists():
            assert False, f"文件不存在: {file_path}"
            return None
        
        try:
            content = file_path.read_text(encoding="utf-8")
            assert content is not None
            return content
        except Exception as e:
            logger.error(f"读取文件失败: {file_path}, e = {e}")
            return None
####################################################################################################################################
    def write_md(self, who: str, content: str) -> None:
        file_path = self.md_file_path(who)
        try:
            res = file_path.write_text(content, encoding="utf-8")
            logger.info(f"写入文件成功: {file_path}, res = {res}")
        except Exception as e:
            logger.error(f"写入文件失败: {file_path}, e = {e}")
            return
####################################################################################################################################
    def get_kick_off_memory(self, who: str) -> str:
        return self.kick_off_memories.get(who, "")
####################################################################################################################################