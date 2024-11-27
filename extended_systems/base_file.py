from abc import ABC, abstractmethod
from pathlib import Path
from loguru import logger


class BaseFile(ABC):

    def __init__(self, name: str, owner_name: str) -> None:
        self._name: str = name
        self._owner_name: str = owner_name

    ############################################################################################################
    @property
    def name(self) -> str:
        return self._name

    ############################################################################################################
    @property
    def owner_name(self) -> str:
        return self._owner_name

    ############################################################################################################
    @abstractmethod
    def serialization(self) -> str:
        pass

    ############################################################################################################
    @abstractmethod
    def deserialization(self, content: str) -> None:
        pass

    ############################################################################################################
    def write(self, write_path: Path) -> int:
        try:
            write_content = self.serialization()
            return write_path.write_text(write_content, encoding="utf-8")
        except Exception as e:
            logger.error(f"{self._name}, {self._owner_name} 写文件失败: {write_path}")
        return 0

    ############################################################################################################
