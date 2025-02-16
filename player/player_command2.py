from dataclasses import dataclass
from typing import List, Any
from loguru import logger


@dataclass
class PlayerCommand2:
    user: str = ""
    command: str = "/command"


if __name__ == "__main__":
    pass
