"""禁止隐式字符串拼接：相邻字面量会被 Python 自动粘成一个字符串。

这类写法把「两条字符串」写成了「一条」，肉眼很难发现（我曾在卡牌词缀上踩过：
`"[余刃]:规则——" "袖里那柄还在"` 实际是一个元素、一段混合了机制与叙事的文本）。
ruff 的 `ISC` 规则覆盖同行与集合内的情形，但**跨行括号拼接**（下面这种最常见的折行写法）
当前版本不报，因此这里用 tokenizer 兜底：

    text = (
        "第一句"
        "第二句"
    )

要折行就写成多个独立字符串（列表元素、参数、变量），或在 f-string 里一次写完。
"""

import tokenize
from pathlib import Path
from typing import List

import pytest

ROOT = Path(__file__).resolve().parents[2]
_SCAN_DIRS = ("src", "tests", "demo", "scripts")

# 这些 token 出现在两个字面量之间时，不构成「隐式拼接」以外的语义
_IGNORABLE = {
    tokenize.NL,
    tokenize.NEWLINE,
    tokenize.INDENT,
    tokenize.DEDENT,
    tokenize.ENCODING,
}


def _iter_sources() -> List[Path]:
    """待扫描源码；跳过本文件——它为了自测扫描器而故意保留了反例片段。"""
    paths: List[Path] = []
    for dirname in _SCAN_DIRS:
        for path in sorted((ROOT / dirname).rglob("*.py")):
            if "__pycache__" in path.parts or path.name == Path(__file__).name:
                continue
            paths.append(path)
    return paths


def _adjacent_literal_lines(path: Path) -> List[int]:
    """返回该文件中「前一个字面量」所在行号：其后（跳过空行/注释）紧跟另一个字面量。

    Python 3.12 起 f-string 被拆成 FSTRING_START/MIDDLE/END 三种 token，
    因此这里按「一个字面量从哪开始、到哪结束」来判断，而不是只看 STRING。
    """
    hits: List[int] = []
    with path.open("rb") as handle:
        tokens = list(tokenize.tokenize(handle.readline))

    previous_literal_line: int | None = None
    fstring_depth = 0
    fstring_start_line = 0

    for token in tokens:
        if fstring_depth:
            if token.type == tokenize.FSTRING_START:
                fstring_depth += 1
            elif token.type == tokenize.FSTRING_END:
                fstring_depth -= 1
                if fstring_depth == 0:
                    if previous_literal_line is not None:
                        hits.append(previous_literal_line)
                    previous_literal_line = fstring_start_line
            continue

        if token.type in _IGNORABLE:
            continue
        if token.type == tokenize.STRING:
            if previous_literal_line is not None:
                hits.append(previous_literal_line)
            previous_literal_line = token.start[0]
        elif token.type == tokenize.FSTRING_START:
            fstring_depth = 1
            fstring_start_line = token.start[0]
        else:
            previous_literal_line = None
    return hits


def test_no_implicit_string_concatenation() -> None:
    """全仓源码不得出现相邻字面量拼接（同行、跨行、集合内都算）。"""
    offenders: List[str] = []
    for path in _iter_sources():
        for line in _adjacent_literal_lines(path):
            offenders.append(f"{path.relative_to(ROOT)}:{line}")

    assert not offenders, (
        "检测到隐式字符串拼接（相邻字面量会被自动粘成一个字符串）：\n  "
        + "\n  ".join(offenders)
        + "\n请合并为一个字面量，或拆成多个独立字符串（列表元素 / 参数 / 变量）。"
    )


@pytest.mark.parametrize(
    "snippet",
    [
        'x = "第一句" "第二句"',
        'x = (\n    "第一句"\n    "第二句"\n)',
        'lines = [\n    "第一句"\n    "第二句",\n]',
    ],
)
def test_scanner_detects_all_shapes(tmp_path: Path, snippet: str) -> None:
    """扫描器对同行、跨行、集合内三种写法都能命中。"""
    path = tmp_path / "sample.py"
    path.write_text(snippet + "\n")
    assert _adjacent_literal_lines(path)


def test_scanner_allows_separate_literals(tmp_path: Path) -> None:
    """正常写法：逗号分隔、独立语句、f-string 内部折行都不算拼接。"""
    path = tmp_path / "sample.py"
    path.write_text(
        "\n".join(
            [
                'a = "第一句"',
                'b = "第二句"',
                'lines = ["第一句", "第二句"]',
                'text = f"""',
                "{a}",
                '"""',
            ]
        )
        + "\n"
    )
    assert not _adjacent_literal_lines(path)
