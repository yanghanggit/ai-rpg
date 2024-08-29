from loguru import logger
from typing import Dict, Optional, List
from pathlib import Path


####################################################################################################################################
## 第一次初始化的时候，会做读取来确定角色初始上下文（记忆）
class KickOffMessageSystem:
    def __init__(self, name: str) -> None:
        self._name: str = name
        self._messages: Dict[str, str] = {}
        self._runtime_dir: Optional[Path] = None

    ####################################################################################################################################
    def set_runtime_dir(self, runtime_dir: Path) -> None:
        assert runtime_dir is not None
        self._runtime_dir = runtime_dir
        self._runtime_dir.mkdir(parents=True, exist_ok=True)
        assert runtime_dir.exists()
        assert (
            self._runtime_dir.is_dir()
        ), f"Directory is not a directory: {self._runtime_dir}"

    ####################################################################################################################################
    def md_file_path(self, actor_name: str) -> Path:
        assert self._runtime_dir is not None
        dir = self._runtime_dir / f"{actor_name}"
        dir.mkdir(parents=True, exist_ok=True)
        return dir / f"kick_off_message.md"

    ####################################################################################################################################
    def add_message(self, actor_name: str, kick_off_message: str) -> None:
        # 初始化
        self.write_md(actor_name, kick_off_message)
        # 初始化成功了
        mm = self.read_md(actor_name)
        assert mm is not None
        if mm is not None:
            assert mm == kick_off_message
            self._messages[actor_name] = mm

    ####################################################################################################################################
    def get_message(self, actor_name: str) -> str:
        return self._messages.get(actor_name, "")

    ####################################################################################################################################
    def read_md(self, actor_name: str) -> Optional[str]:

        try:

            file_path = self.md_file_path(actor_name)
            if not file_path.exists():
                logger.error(f"文件不存在: {file_path}")
                return None

            return file_path.read_text(encoding="utf-8")

        except Exception as e:
            logger.error(f"读取文件失败: {file_path}, e = {e}")

        return None

    ####################################################################################################################################
    def write_md(self, actor_name: str, content: str) -> int:
        try:
            file_path = self.md_file_path(actor_name)
            return file_path.write_text(content, encoding="utf-8")
        except Exception as e:
            logger.error(f"写入文件失败: {file_path}, e = {e}")
        return -1


####################################################################################################################################
