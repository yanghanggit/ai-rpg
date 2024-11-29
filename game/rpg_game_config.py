from enum import StrEnum, unique

# from typing import List
from pathlib import Path


@unique
class WorldSystemNames(StrEnum):
    WORLD_APPEARANCE_SYSTEM_NAME = "角色外观生成器"
    WORLD_SKILL_SYSTEM_NAME = "技能系统"


# 检查版本，因为gen_game.py先写死了。
CHECK_GAME_RESOURCE_VERSION = "0.0.1"

# 生成游戏的目录
ROOT_GEN_GAMES_DIR: Path = Path("gen_games")
ROOT_GEN_GAMES_DIR.mkdir(parents=True, exist_ok=True)
assert ROOT_GEN_GAMES_DIR.exists(), f"找不到目录: {ROOT_GEN_GAMES_DIR}"

# 生成agents的目录
ROOT_GEN_AGENTS_DIR: Path = Path("gen_agents")
ROOT_GEN_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
assert ROOT_GEN_AGENTS_DIR.exists(), f"找不到目录: {ROOT_GEN_AGENTS_DIR}"

# 运行时的文件存放目录
GAMES_RUNTIME_DIR: Path = ROOT_GEN_GAMES_DIR / "gen_runtimes"
GAMES_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
assert GAMES_RUNTIME_DIR.exists(), f"找不到目录: {GAMES_RUNTIME_DIR}"

# 存档目录
GAMES_ARCHIVE_DIR: Path = Path("game_archive")
GAMES_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
assert GAMES_ARCHIVE_DIR.exists(), f"找不到目录: {GAMES_ARCHIVE_DIR}"

# 生成log的目录
LOGS_DIR: Path = Path("logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
assert LOGS_DIR.exists(), f"找不到目录: {LOGS_DIR}"
