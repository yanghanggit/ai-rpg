import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
import os
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
def read_text_file(full_path: str) -> str:
    _path_ = Path(full_path)
    if not _path_.exists():
        assert False, f"File not found: {full_path}"
        return ""
    try:
        content = _path_.read_text(encoding="utf-8")
        assert content is not None, f"File is empty: {full_path}"
        assert len(content) > 0, f"File is empty: {full_path}"
        return content
    except FileNotFoundError:
        assert False, f"File not found: {full_path}"
        return ""
############################################################################################################
def readmd(budding_world_path: str) -> str:
    cwd = os.getcwd()
    return read_text_file(cwd + budding_world_path)
############################################################################################################
def readpy(budding_world_path: str) -> str:
    cwd = os.getcwd()
    return read_text_file(cwd + budding_world_path)
############################################################################################################

