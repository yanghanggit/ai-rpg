"""测试 markdown.py 中的 extract_json 函数"""

import pytest
from src.ai_rpg.utils.markdown import extract_json


class TestExtractJson:
    """测试 extract_json 函数"""

    # ── 基本提取 ────────────────────────────────────────────

    def test_simple_json_object(self) -> None:
        result = extract_json('```json\n{"name": "test", "value": 123}\n```')
        assert result == '{"name": "test", "value": 123}'

    def test_json_array(self) -> None:
        result = extract_json("```json\n[1, 2, 3, 4, 5]\n```")
        assert result == "[1, 2, 3, 4, 5]"

    def test_empty_json_object(self) -> None:
        result = extract_json("```json\n{}\n```")
        assert result == "{}"

    def test_empty_json_array(self) -> None:
        result = extract_json("```json\n[]\n```")
        assert result == "[]"

    def test_complex_nested_json(self) -> None:
        markdown = """```json
{
    "status": "success",
    "data": {
        "users": [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"}
        ],
        "count": 2
    },
    "timestamp": "2025-11-19T00:00:00Z"
}
```"""
        result = extract_json(markdown)
        assert '"status": "success"' in result
        assert '"users"' in result
        assert '"timestamp"' in result
        assert "```" not in result

    def test_content_whitespace_is_stripped(self) -> None:
        result = extract_json('```json\n\n  {"key": "value"}  \n\n```')
        assert result == '{"key": "value"}'

    # ── 无代码块 / 非 JSON 代码块 ──────────────────────────

    def test_no_code_block_returns_original(self) -> None:
        text = '{"name": "test"}'
        assert extract_json(text) == text

    def test_plain_text_returns_original(self) -> None:
        text = "这是普通文本，不包含任何代码块。"
        assert extract_json(text) == text

    def test_empty_string(self) -> None:
        assert extract_json("") == ""

    def test_non_json_code_block_returns_original(self) -> None:
        text = '```python\nprint("hello")\n```'
        assert extract_json(text) == text

    def test_no_language_code_block_returns_original(self) -> None:
        text = '```\n{"key": "value"}\n```'
        assert extract_json(text) == text

    # ── 围栏变体 ────────────────────────────────────────────

    def test_tilde_fence(self) -> None:
        result = extract_json('~~~json\n{"a": 1}\n~~~')
        assert result == '{"a": 1}'

    def test_longer_backtick_fence(self) -> None:
        result = extract_json('````json\n{"a": 1}\n````')
        assert result == '{"a": 1}'

    def test_info_string_with_extra_attributes(self) -> None:
        result = extract_json('```json title="example"\n{"a": 1}\n```')
        assert result == '{"a": 1}'

    # ── 多块选区 ────────────────────────────────────────────

    def test_multiple_blocks_returns_first(self) -> None:
        result = extract_json(
            '```json\n{"first": 1}\n```\n\n```json\n{"second": 2}\n```'
        )
        assert result == '{"first": 1}'

    def test_with_surrounding_markdown_text(self) -> None:
        markdown = """前面的说明文字

```json
{"key": "value"}
```

后面的说明文字"""
        assert extract_json(markdown) == '{"key": "value"}'

    # ── 容错：LLM 常见截断 ──────────────────────────────────

    def test_unclosed_fence(self) -> None:
        result = extract_json('```json\n{"key": "value"}\ntrailing text')
        assert '"key": "value"' in result
        assert "```" not in result

    def test_empty_code_block(self) -> None:
        result = extract_json("```json\n```")
        assert result == ""

    # ── 大小写 ──────────────────────────────────────────────

    @pytest.mark.parametrize("lang", ["json", "Json", "JSON"])
    def test_case_insensitive_info_string(self, lang: str) -> None:
        text = f'```{lang}\n{{"a": 1}}\n```'
        assert extract_json(text) == '{"a": 1}'
