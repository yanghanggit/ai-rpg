import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from loguru import logger
from pathlib import Path

############################################################################################################
def write_text_file(directory: Path, filename: str, text: str) -> int:
    assert len(text) > 0, "Text is empty"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        assert directory.is_dir(), f"Directory is not a directory: {directory}"
        path = directory / filename      
        res = path.write_text(text, encoding='utf-8')
        return res
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    return -1
############################################################################################################
def read_text_file(path: Path) -> str:
    if not path.exists():
        assert False, f"File not found: {path}"
        return ""
    try:
        content = path.read_text(encoding="utf-8")
        assert content is not None, f"File is empty: {path}"
        assert len(content) > 0, f"File is empty: {path}"
        return content
    except FileNotFoundError:
        assert False, f"File not found: {path}"
        return ""
############################################################################################################
def read_system_prompt_md(path: Path) -> str:
    return read_text_file(path)
############################################################################################################
def read_agentpy_template(path: Path) -> str:
    return read_text_file(path)
############################################################################################################
def parse_prop_string(data: str) -> tuple[str, int]:
    # 例子: "道具", "道具#999"
    if "#" not in data:
        # 默认就是一个
        return data, 1
    prop_name, prop_quantity = data.split("#")
    prop_count = int(prop_quantity)
    if prop_count < 1:
        logger.error(f"Invalid prop count: {prop_count}")
        prop_count = 1

    return prop_name, prop_count
############################################################################################################
