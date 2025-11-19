"""测试 md_format.py 中的函数"""

from src.ai_rpg.utils.md_format import has_json_code_block, extract_json_from_code_block


class TestHasJsonCodeBlock:
    """测试 has_json_code_block 函数"""

    def test_has_json_code_block_with_json_marker(self) -> None:
        """测试包含 ```json 标记的文本"""
        text = "```json\n{}\n```"
        assert has_json_code_block(text) is True

    def test_has_json_code_block_with_uppercase(self) -> None:
        """测试包含 ```JSON 大写标记的文本"""
        text = "```JSON\n{}\n```"
        assert has_json_code_block(text) is True

    def test_has_json_code_block_with_mixed_case(self) -> None:
        """测试包含 ```Json 混合大小写标记的文本"""
        text = "```Json\n{}\n```"
        assert has_json_code_block(text) is True

    def test_has_json_code_block_without_json_marker(self) -> None:
        """测试不包含 ```json 标记的普通文本"""
        text = "这是普通文本"
        assert has_json_code_block(text) is False

    def test_has_json_code_block_with_other_code_block(self) -> None:
        """测试包含其他代码块标记(如 ```python)的文本"""
        text = "```python\nprint('hello')\n```"
        assert has_json_code_block(text) is False

    def test_has_json_code_block_with_json_content_but_no_marker(self) -> None:
        """测试包含 JSON 内容但没有代码块标记的文本"""
        text = '{"key": "value"}'
        assert has_json_code_block(text) is False

    def test_has_json_code_block_with_empty_string(self) -> None:
        """测试空字符串"""
        text = ""
        assert has_json_code_block(text) is False

    def test_has_json_code_block_with_json_in_middle(self) -> None:
        """测试 ```json 标记在文本中间的情况"""
        text = "前面的文本\n```json\n{}\n```\n后面的文本"
        assert has_json_code_block(text) is True


class TestExtractJsonFromCodeBlock:
    """测试 extract_json_from_code_block 函数"""

    def test_extract_simple_json_object(self) -> None:
        """测试提取简单的 JSON 对象"""
        markdown_text = '```json\n{"name": "test", "value": 123}\n```'
        expected = '{"name": "test", "value": 123}'
        assert extract_json_from_code_block(markdown_text) == expected

    def test_extract_json_array(self) -> None:
        """测试提取 JSON 数组"""
        markdown_text = "```json\n[1, 2, 3, 4, 5]\n```"
        expected = "[1, 2, 3, 4, 5]"
        assert extract_json_from_code_block(markdown_text) == expected

    def test_extract_nested_json(self) -> None:
        """测试提取嵌套的 JSON 对象"""
        markdown_text = """```json
{
    "user": {
        "name": "Alice",
        "age": 30
    },
    "items": [1, 2, 3]
}
```"""
        result = extract_json_from_code_block(markdown_text)
        assert '"user"' in result
        assert '"name": "Alice"' in result
        assert '"items"' in result
        assert "```" not in result

    def test_extract_json_with_extra_whitespace(self) -> None:
        """测试提取带有额外空白字符的 JSON"""
        markdown_text = '```json\n\n  {"key": "value"}  \n\n```'
        expected = '{"key": "value"}'
        assert extract_json_from_code_block(markdown_text) == expected

    def test_extract_json_uppercase_marker(self) -> None:
        """测试提取带有大写 ```JSON 标记的内容"""
        markdown_text = '```JSON\n{"name": "test"}\n```'
        expected = '{"name": "test"}'
        assert extract_json_from_code_block(markdown_text) == expected

    def test_extract_json_mixed_case_marker(self) -> None:
        """测试提取带有混合大小写 ```Json 标记的内容"""
        markdown_text = '```Json\n{"name": "test"}\n```'
        expected = '{"name": "test"}'
        assert extract_json_from_code_block(markdown_text) == expected

    def test_extract_without_code_block_returns_original(self) -> None:
        """测试没有代码块标记时返回原文本"""
        text = '{"name": "test", "value": 123}'
        assert extract_json_from_code_block(text) == text

    def test_extract_plain_text_returns_original(self) -> None:
        """测试纯文本返回原文本"""
        text = "这是普通文本"
        assert extract_json_from_code_block(text) == text

    def test_extract_empty_json_object(self) -> None:
        """测试提取空 JSON 对象"""
        markdown_text = "```json\n{}\n```"
        expected = "{}"
        assert extract_json_from_code_block(markdown_text) == expected

    def test_extract_empty_json_array(self) -> None:
        """测试提取空 JSON 数组"""
        markdown_text = "```json\n[]\n```"
        expected = "[]"
        assert extract_json_from_code_block(markdown_text) == expected

    def test_extract_json_with_surrounding_text(self) -> None:
        """测试提取含有前后文本的 JSON 代码块"""
        markdown_text = """这是前面的说明文字
```json
{"key": "value"}
```
这是后面的说明文字"""
        result = extract_json_from_code_block(markdown_text)
        assert result == '{"key": "value"}'

    def test_extract_json_with_special_characters(self) -> None:
        """测试提取包含特殊字符的 JSON"""
        markdown_text = (
            r'```json\n{"message": "Hello\nWorld", "path": "C:\\Users\\test"}\n```'
        )
        result = extract_json_from_code_block(markdown_text)
        assert "```" not in result
        assert "json" not in result.lower() or '"' in result

    def test_extract_json_multiline_complex(self) -> None:
        """测试提取复杂的多行 JSON"""
        markdown_text = """```json
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
        result = extract_json_from_code_block(markdown_text)
        assert '"status": "success"' in result
        assert '"users"' in result
        assert '"timestamp"' in result
        assert "```" not in result

    def test_extract_json_with_only_opening_marker(self) -> None:
        """测试只有开始标记的情况"""
        markdown_text = '```json\n{"key": "value"}'
        # 应该能够处理这种情况(通过回退方法)
        result = extract_json_from_code_block(markdown_text)
        assert '{"key": "value"}' in result

    def test_extract_empty_string(self) -> None:
        """测试空字符串"""
        markdown_text = ""
        assert extract_json_from_code_block(markdown_text) == ""

    def test_extract_only_code_block_markers(self) -> None:
        """测试只有代码块标记没有内容"""
        markdown_text = "```json\n```"
        result = extract_json_from_code_block(markdown_text)
        assert result == "" or result == "```json\n```"  # 可能返回空字符串或原文本
