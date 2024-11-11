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
        return path.write_text(text, encoding="utf-8")

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
