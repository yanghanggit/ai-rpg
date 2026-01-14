"""测试 command_parser.py 中的函数"""

from src.ai_rpg.utils.command_parser import parse_command_args


class TestParseCommandArgs:
    """测试 parse_command_args 函数"""

    def test_parse_single_argument(self) -> None:
        """测试解析单个参数"""
        result = parse_command_args("/switch_stage --stage=场景.营地", {"stage"})
        assert result == {"stage": "场景.营地"}

    def test_parse_multiple_arguments(self) -> None:
        """测试解析多个参数"""
        result = parse_command_args(
            "/speak --target=角色.法师.奥露娜 --content=你好", {"target", "content"}
        )
        assert result == {"target": "角色.法师.奥露娜", "content": "你好"}

    def test_parse_with_spaces_around_equals(self) -> None:
        """测试等号前后有空格的情况"""
        result = parse_command_args(
            "/speak --target = 玩家 --content = 测试", {"target", "content"}
        )
        assert result == {"target": "玩家", "content": "测试"}

    def test_parse_value_with_equals_sign(self) -> None:
        """测试值中包含等号的情况"""
        result = parse_command_args("/cmd --expr=x=1", {"expr"})
        assert result == {"expr": "x=1"}

    def test_parse_with_empty_value(self) -> None:
        """测试空值会被过滤"""
        result = parse_command_args(
            "/speak --target= --content=你好", {"target", "content"}
        )
        assert result == {"content": "你好"}

    def test_parse_with_whitespace_only_value(self) -> None:
        """测试只有空白字符的值会被过滤"""
        result = parse_command_args(
            "/speak --target=   --content=你好", {"target", "content"}
        )
        assert result == {"content": "你好"}

    def test_parse_only_specified_keys(self) -> None:
        """测试只返回指定的键"""
        result = parse_command_args(
            "/speak --target=玩家 --content=你好 --extra=额外", {"target", "content"}
        )
        assert result == {"target": "玩家", "content": "你好"}
        assert "extra" not in result

    def test_parse_with_missing_key(self) -> None:
        """测试缺少某个键的情况"""
        result = parse_command_args("/speak --target=玩家", {"target", "content"})
        assert result == {"target": "玩家"}
        assert "content" not in result

    def test_parse_with_no_arguments(self) -> None:
        """测试没有参数的命令"""
        result = parse_command_args("/quit", {"target", "content"})
        assert result == {}

    def test_parse_empty_string(self) -> None:
        """测试空字符串"""
        result = parse_command_args("", {"target"})
        assert result == {}

    def test_parse_with_invalid_format(self) -> None:
        """测试无效格式（没有等号）"""
        result = parse_command_args("/speak --target", {"target"})
        assert result == {}

    def test_parse_with_chinese_characters(self) -> None:
        """测试包含中文字符的参数"""
        result = parse_command_args(
            "/speak --target=角色.法师.奥露娜 --content=我还是需要准备一下",
            {"target", "content"},
        )
        assert result == {"target": "角色.法师.奥露娜", "content": "我还是需要准备一下"}

    def test_parse_with_special_characters(self) -> None:
        """测试包含特殊字符的参数值"""
        result = parse_command_args(
            "/speak --target=玩家 --content=你好!@#$%^&*()", {"target", "content"}
        )
        assert result == {"target": "玩家", "content": "你好!@#$%^&*()"}

    def test_parse_with_dots_in_value(self) -> None:
        """测试值中包含点号的情况"""
        result = parse_command_args("/switch_stage --stage=场景.训练场.副本", {"stage"})
        assert result == {"stage": "场景.训练场.副本"}

    def test_parse_multiple_equals_in_value(self) -> None:
        """测试值中包含多个等号的情况"""
        result = parse_command_args("/cmd --formula=a=b=c", {"formula"})
        assert result == {"formula": "a=b=c"}

    def test_parse_with_empty_keys_set(self) -> None:
        """测试空的键集合"""
        result = parse_command_args("/speak --target=玩家 --content=你好", set())
        assert result == {}

    def test_parse_case_sensitive_keys(self) -> None:
        """测试键名大小写敏感"""
        result = parse_command_args(
            "/speak --Target=玩家 --content=你好", {"target", "content"}
        )
        # 键名不匹配，Target != target
        assert result == {"content": "你好"}

    def test_parse_with_numeric_values(self) -> None:
        """测试数字值"""
        result = parse_command_args("/cmd --count=123 --score=99.5", {"count", "score"})
        assert result == {"count": "123", "score": "99.5"}

    def test_parse_with_long_content(self) -> None:
        """测试较长的内容"""
        long_content = (
            "这是一段很长的对话内容，包含多个句子。第一句话。第二句话。第三句话。"
        )
        result = parse_command_args(
            f"/speak --target=玩家 --content={long_content}", {"target", "content"}
        )
        assert result == {"target": "玩家", "content": long_content}
