from enum import StrEnum, unique
from typing import List
from pathlib import Path


@unique
class WorldSystemNames(StrEnum):
    WORLD_APPEARANCE_SYSTEM_NAME = "角色外观生成器"
    WORLD_SKILL_SYSTEM_NAME = "技能系统"


# 临时
GAME_NAMES: List[str] = ["World1", "World2", "World3"]

# 检查版本，因为gen_game.py先写死了。
CHECK_GAME_RESOURCE_VERSION = "0.0.1"

# 生成游戏的目录
GEN_GAMES_DIR: Path = Path("gen_games")
GEN_GAMES_DIR.mkdir(parents=True, exist_ok=True)
assert GEN_GAMES_DIR.exists(), f"找不到目录: {GEN_GAMES_DIR}"

# 运行时的文件存放目录
GAMES_RUNTIME_DIR: Path = GEN_GAMES_DIR / "gen_runtimes"
GAMES_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
assert GAMES_RUNTIME_DIR.exists(), f"找不到目录: {GAMES_RUNTIME_DIR}"

# 存档目录
GAMES_ARCHIVE_DIR: Path = Path("game_archive")
GAMES_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
assert GAMES_ARCHIVE_DIR.exists(), f"找不到目录: {GAMES_ARCHIVE_DIR}"
