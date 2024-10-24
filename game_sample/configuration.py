from pathlib import Path

# Excel文件中的Sheet名称
ACTOR_SHEET_NAME = "Actor"
STAGE_SHEET_NAME = "Stage"
PROP_SHEET_NAME = "Prop"
WORLD_SYSTEM_SHEET_NAME = "WorldSystem"

# 根目录
GAME_SAMPLE_DIR: Path = Path("game_sample")
assert GAME_SAMPLE_DIR.exists(), f"找不到目录: {GAME_SAMPLE_DIR}"

# Excel文件路径
GAME_SAMPLE_EXCEL_FILE_PATH: Path = Path(f"game_sample/excel/game_sample.xlsx")
assert (
    GAME_SAMPLE_EXCEL_FILE_PATH.exists()
), f"找不到Excel文件: {GAME_SAMPLE_EXCEL_FILE_PATH}"

## 输出路径gen_actor_sys_prompt
OUT_PUT_ACTOR_SYS_PROMPT_DIR: Path = Path("game_sample/gen_actor_sys_prompt")
OUT_PUT_ACTOR_SYS_PROMPT_DIR.mkdir(parents=True, exist_ok=True)
assert (
    OUT_PUT_ACTOR_SYS_PROMPT_DIR.exists()
), f"找不到目录: {OUT_PUT_ACTOR_SYS_PROMPT_DIR}"

## 输出路径gen_stage_sys_prompt
OUT_PUT_STAGE_SYS_PROMPT_DIR: Path = Path("game_sample/gen_stage_sys_prompt")
OUT_PUT_STAGE_SYS_PROMPT_DIR.mkdir(parents=True, exist_ok=True)
assert (
    OUT_PUT_STAGE_SYS_PROMPT_DIR.exists()
), f"找不到目录: {OUT_PUT_STAGE_SYS_PROMPT_DIR}"

## 输出路径gen_world_sys_prompt
OUT_PUT_WORLD_SYS_PROMPT_DIR: Path = Path("game_sample/gen_world_sys_prompt")
OUT_PUT_WORLD_SYS_PROMPT_DIR.mkdir(parents=True, exist_ok=True)
assert (
    OUT_PUT_WORLD_SYS_PROMPT_DIR.exists()
), f"找不到目录: {OUT_PUT_WORLD_SYS_PROMPT_DIR}"

# 输出路径gen_agent
OUT_PUT_AGENT_DIR: Path = Path("game_sample/gen_agent")
OUT_PUT_AGENT_DIR.mkdir(parents=True, exist_ok=True)
assert OUT_PUT_AGENT_DIR.exists(), f"找不到目录: {OUT_PUT_AGENT_DIR}"

# 输出路径gen_sys_prompt_templates
OUT_PUT_SYS_PROMPT_TEMPLATES_DIR: Path = Path("game_sample/gen_sys_prompt_templates")
OUT_PUT_SYS_PROMPT_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
assert (
    OUT_PUT_SYS_PROMPT_TEMPLATES_DIR.exists()
), f"找不到目录: {OUT_PUT_SYS_PROMPT_TEMPLATES_DIR}"

# 输出路径gen_games
OUT_PUT_GEN_GAMES_DIR: Path = Path("game_sample/gen_games")
OUT_PUT_GEN_GAMES_DIR.mkdir(parents=True, exist_ok=True)
assert OUT_PUT_GEN_GAMES_DIR.exists(), f"找不到目录: {OUT_PUT_GEN_GAMES_DIR}"
