from pathlib import Path
from typing import Final


SENTENCE_TRANSFORMERS_CACHE: Final[Path] = Path(".cache") / "sentence_transformers"
SENTENCE_TRANSFORMERS_CACHE.mkdir(parents=True, exist_ok=True)
assert (
    SENTENCE_TRANSFORMERS_CACHE.exists()
), f"找不到目录: {SENTENCE_TRANSFORMERS_CACHE}"
