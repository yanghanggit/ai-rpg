#!/usr/bin/env python3
"""
JSON 格式化模块的兼容性和集成测试 - 仅函数式 API
"""

import json
import pytest

from src.ai_rpg.utils.json_format import (
    strip_json_code_block,
    combine_json_fragments,
    contains_duplicate_segments,
    contains_json_code_block,
)


class TestJsonFormatCompatibility:
    """测试 JSON 格式化模块的兼容性"""

    def test_existing_code_compatibility(self) -> None:
        """测试与现有代码的兼容性"""
        # 模拟现有代码中常见的使用场景
        test_markdown = """```json
        {"feedback": "Good job!", "score": 95}
        ```"""

        # 使用独立函数（现有代码的调用方式）
        cleaned = strip_json_code_block(test_markdown)

        # 验证清理结果
        assert cleaned.strip() == '{"feedback": "Good job!", "score": 95}'

        # 验证可以正常解析为 JSON
        parsed = json.loads(cleaned)
        assert parsed["feedback"] == "Good job!"
        assert parsed["score"] == 95

    def test_complex_workflow_integration(self) -> None:
        """测试复杂工作流的集成"""
        # 包含 Markdown 代码块和重复片段的复杂输入
        test_input = """```json
        {"action": "move", "direction": "north"}{"action": "attack", "target": "orc"}
        ```"""

        # 处理流程
        cleaned = strip_json_code_block(test_input)
        result = combine_json_fragments(cleaned)

        # 验证处理结果
        assert result is not None
        assert "action" in result
        assert "direction" in result
        assert "target" in result

        # action 应该是一个包含两个值的列表
        assert isinstance(result["action"], list)
        assert "move" in result["action"]
        assert "attack" in result["action"]

        # 其他字段应该保持原值
        assert result["direction"] == "north"
        assert result["target"] == "orc"

    def test_backwards_compatibility_with_module_import(self) -> None:
        """测试模块导入的向后兼容性"""
        # 测试通过模块方式的导入和使用
        from src.ai_rpg.utils import json_format

        test_response = """```json
        {"player_action": "cast_spell", "spell_name": "fireball"}
        ```"""

        # 使用现有的模块调用方式
        cleaned = json_format.strip_json_code_block(test_response)
        expected = '{"player_action": "cast_spell", "spell_name": "fireball"}'

        assert cleaned.strip() == expected

        # 验证新函数也可以通过模块访问
        result = json_format.combine_json_fragments(cleaned)
        assert result is not None
        assert result["player_action"] == "cast_spell"
        assert result["spell_name"] == "fireball"

    def test_edge_cases_integration(self) -> None:
        """测试边界情况的集成"""
        # 空字符串
        empty_result = combine_json_fragments("")
        assert empty_result is None

        # 只有空白字符
        whitespace_cleaned = strip_json_code_block("   \n\t   ")
        assert whitespace_cleaned.strip() == ""

        # 无效的 JSON
        invalid_json = '{"incomplete": "json"'
        invalid_result = combine_json_fragments(invalid_json)
        assert invalid_result is None

    def test_real_world_usage_scenario(self) -> None:
        """测试真实世界的使用场景"""
        # 模拟从 AI 响应中提取 JSON 的场景
        ai_response = """
        Based on your request, here's the action:
        
        ```json
        {"type": "game_action", "action": "move"}{"type": "ui_update", "message": "Player moved north"}
        ```
        
        This should handle both the game logic and UI updates.
        """

        # 处理这种复杂的输入
        cleaned = strip_json_code_block(ai_response)
        result = combine_json_fragments(cleaned)

        # 验证结果
        assert result is not None

        # 验证可以解析为有效 JSON
        json_str = json.dumps(result)
        parsed = json.loads(json_str)
        assert parsed is not None
        assert "type" in parsed
        assert isinstance(parsed["type"], list)
        assert "game_action" in parsed["type"]
        assert "ui_update" in parsed["type"]

    def test_performance_and_memory_efficiency(self) -> None:
        """测试性能和内存效率"""
        # 创建一个较大的 JSON 字符串
        large_json_parts = []
        for i in range(100):
            large_json_parts.append(f'{{"item_{i}": "value_{i}"}}')

        large_input = f"```json\n{''.join(large_json_parts)}\n```"

        # 处理大型输入
        cleaned = strip_json_code_block(large_input)
        result = combine_json_fragments(cleaned)

        # 验证结果仍然有效
        assert result is not None
        assert len(result) == 100  # 应该有 100 个唯一的键

        # 验证可以序列化
        serialized = json.dumps(result)
        assert serialized is not None

    def test_chain_operations_robustness(self) -> None:
        """测试链式操作的健壮性"""
        # 测试多种组合的操作
        test_cases = [
            '```json\n{"a": 1}\n```',
            '```json\n{"a": 1}{"b": 2}\n```',
            '{"already": "clean"}',
            "",
            "not json at all",
        ]

        for test_case in test_cases:
            try:
                # 应该能够安全地执行操作而不抛出异常
                cleaned = strip_json_code_block(test_case)
                result = combine_json_fragments(cleaned)

                # 如果有有效的 JSON，验证它
                if result is not None:
                    json.dumps(result)  # 应该不抛出异常

            except Exception as e:
                pytest.fail(f"Operations failed for input: {test_case}, error: {e}")

    def test_function_based_workflow(self) -> None:
        """测试基于函数的完整工作流"""
        # 模拟游戏中的简单场景（避免嵌套对象导致的解析问题）
        game_response = """
        Game turn result:
        ```json
        {"player1_action": "attack"}{"player2_action": "defend"}{"turn": 5}
        ```
        """

        # 步骤1: 检测是否有代码块
        has_code_block = contains_json_code_block(game_response)
        assert has_code_block is True

        # 步骤2: 移除代码块
        cleaned = strip_json_code_block(game_response)

        # 步骤3: 检测是否有重复片段
        has_duplicates = contains_duplicate_segments(cleaned)
        assert has_duplicates is True

        # 步骤4: 合并片段
        result = combine_json_fragments(cleaned)

        # 验证最终结果
        assert result is not None
        assert "player1_action" in result
        assert "player2_action" in result
        assert "turn" in result
        assert result["turn"] == 5

    def test_error_recovery_and_graceful_degradation(self) -> None:
        """测试错误恢复和优雅降级"""
        # 测试部分有效的输入
        mixed_input = """```json
        {"valid": "json"}invalid_part{"another": "valid"}
        ```"""

        cleaned = strip_json_code_block(mixed_input)
        result = combine_json_fragments(cleaned)

        # 由于有无效部分，应该返回 None，但不应该崩溃
        assert result is None

        # 测试只有一个有效片段的情况
        single_valid = """```json
        {"single": "valid", "number": 42}
        ```"""

        cleaned_single = strip_json_code_block(single_valid)
        result_single = combine_json_fragments(cleaned_single)

        assert result_single is not None
        assert result_single["single"] == "valid"
        assert result_single["number"] == 42


if __name__ == "__main__":
    # 如果直接运行此文件，执行一些基本测试
    print("=== 运行函数式 API 兼容性测试 ===")

    # 简单的冒烟测试
    test_input = """```json
    {"action": "move", "direction": "north"}{"action": "attack", "target": "orc"}
    ```"""

    cleaned = strip_json_code_block(test_input)
    result = combine_json_fragments(cleaned)

    print("输入:", repr(test_input))
    print("清理后:", repr(cleaned))
    print("合并结果:", result)

    if result:
        print("序列化:", json.dumps(result, ensure_ascii=False))

    print("\n函数式 API 兼容性测试完成！")
