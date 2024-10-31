from pathlib import Path
from enum import StrEnum, unique


# 文件内容替换的标记
@unique
class GenSystemPromptSymbol(StrEnum):
    NAME = "<%name>"
    SYSTEM_PROMPT = "<%sys_prompt>"
    CONVERSATION_EXAMPLE = "<%conversation_example>"


# 文件内容替换的标记
@unique
class GenAgentAppContentSymbol(StrEnum):
    SYSTEM_PROMPT_CONTENT = "<%SYSTEM_PROMPT_CONTENT>"
    RAG_CONTENT = "<%RAG_CONTENT>"
    PORT = "<%PORT>"
    API = "<%API>"


# Excel文件中的Sheet名称
ACTOR_SHEET_NAME = "Actor"
STAGE_SHEET_NAME = "Stage"
PROP_SHEET_NAME = "Prop"
WORLD_SYSTEM_SHEET_NAME = "WorldSystem"

# 根目录
GAME_SAMPLE_DIR: Path = Path("game_sample")
assert GAME_SAMPLE_DIR.exists(), f"找不到目录: {GAME_SAMPLE_DIR}"

# Excel文件路径
excel_path = Path(f"game_sample/excel/")
excel_path.mkdir(parents=True, exist_ok=True)
GAME_SAMPLE_EXCEL_FILE_PATH: Path = (
    excel_path / "game_sample.xlsx"
)  # Path(f"game_sample/excel/game_sample.xlsx")
assert (
    GAME_SAMPLE_EXCEL_FILE_PATH.exists()
), f"找不到Excel文件: {GAME_SAMPLE_EXCEL_FILE_PATH}"

## 输出路径gen_actor_sys_prompt
GAME_SAMPLE_OUT_PUT_ACTOR_SYS_PROMPT_DIR: Path = Path(
    "game_sample/gen_actor_sys_prompt"
)
GAME_SAMPLE_OUT_PUT_ACTOR_SYS_PROMPT_DIR.mkdir(parents=True, exist_ok=True)
assert (
    GAME_SAMPLE_OUT_PUT_ACTOR_SYS_PROMPT_DIR.exists()
), f"找不到目录: {GAME_SAMPLE_OUT_PUT_ACTOR_SYS_PROMPT_DIR}"

## 输出路径gen_stage_sys_prompt
GAME_SAMPLE_OUT_PUT_STAGE_SYS_PROMPT_DIR: Path = Path(
    "game_sample/gen_stage_sys_prompt"
)
GAME_SAMPLE_OUT_PUT_STAGE_SYS_PROMPT_DIR.mkdir(parents=True, exist_ok=True)
assert (
    GAME_SAMPLE_OUT_PUT_STAGE_SYS_PROMPT_DIR.exists()
), f"找不到目录: {GAME_SAMPLE_OUT_PUT_STAGE_SYS_PROMPT_DIR}"

## 输出路径gen_world_sys_prompt
GAME_SAMPLE_OUT_PUT_WORLD_SYS_PROMPT_DIR: Path = Path(
    "game_sample/gen_world_sys_prompt"
)
GAME_SAMPLE_OUT_PUT_WORLD_SYS_PROMPT_DIR.mkdir(parents=True, exist_ok=True)
assert (
    GAME_SAMPLE_OUT_PUT_WORLD_SYS_PROMPT_DIR.exists()
), f"找不到目录: {GAME_SAMPLE_OUT_PUT_WORLD_SYS_PROMPT_DIR}"

# 输出路径gen_agent
GAME_SAMPLE_OUT_PUT_AGENT_DIR: Path = Path("game_sample/gen_agents")
GAME_SAMPLE_OUT_PUT_AGENT_DIR.mkdir(parents=True, exist_ok=True)
assert (
    GAME_SAMPLE_OUT_PUT_AGENT_DIR.exists()
), f"找不到目录: {GAME_SAMPLE_OUT_PUT_AGENT_DIR}"

# 输出路径gen_sys_prompt_templates
GAME_SAMPLE_OUT_PUT_SYS_PROMPT_TEMPLATES_DIR: Path = Path(
    "game_sample/gen_sys_prompt_templates"
)
GAME_SAMPLE_OUT_PUT_SYS_PROMPT_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
assert (
    GAME_SAMPLE_OUT_PUT_SYS_PROMPT_TEMPLATES_DIR.exists()
), f"找不到目录: {GAME_SAMPLE_OUT_PUT_SYS_PROMPT_TEMPLATES_DIR}"

# 输出路径gen_games
GAME_SAMPLE_OUT_PUT_GAME_DIR: Path = Path("game_sample/gen_games")
GAME_SAMPLE_OUT_PUT_GAME_DIR.mkdir(parents=True, exist_ok=True)
assert (
    GAME_SAMPLE_OUT_PUT_GAME_DIR.exists()
), f"找不到目录: {GAME_SAMPLE_OUT_PUT_GAME_DIR}"
