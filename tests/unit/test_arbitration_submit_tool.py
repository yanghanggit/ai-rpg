"""三种仲裁的 submit_arbitration 工具 schema 一致性回归测试。

出牌 / 回合结束 / 神器三种仲裁共用同一个 stage 记忆、又是同名工具；参数 schema（字段集合、
required、类型）一旦漂移，LLM 会沿用上一场仲裁看到的字段而产生调用错误（如多传
unsettled_affixes）。三份定义各自写在所属仲裁文件内（不抽共享工厂），此测试锁死它们的
参数结构必须一致；描述文案允许按仲裁类型不同。
"""

from typing import Any, Dict, List

from ai_rpg.systems.artifact_post_arbitration_system import (
    SUBMIT_ARBITRATION_TOOL as ARTIFACT_SUBMIT,
)
from ai_rpg.systems.play_cards_arbitration_system import (
    SUBMIT_ARBITRATION_TOOL as PLAY_CARDS_SUBMIT,
)
from ai_rpg.systems.turn_end_arbitration_system import (
    SUBMIT_ARBITRATION_TOOL as TURN_END_SUBMIT,
)


def _schema_shape(tool: Any) -> Dict[str, Any]:
    """提取参数 schema 中决定兼容性的结构（忽略描述文案）。"""
    parameters = tool.function.parameters
    properties: Dict[str, Any] = parameters["properties"]
    return {
        "keys": sorted(properties.keys()),
        "required": parameters["required"],
        "types": {name: spec["type"] for name, spec in properties.items()},
    }


def test_all_submit_tools_share_the_same_name() -> None:
    assert (
        PLAY_CARDS_SUBMIT.function.name
        == TURN_END_SUBMIT.function.name
        == ARTIFACT_SUBMIT.function.name
        == "submit_arbitration"
    )


def test_all_submit_tools_share_identical_parameter_shape() -> None:
    shapes: List[Dict[str, Any]] = [
        _schema_shape(t) for t in (PLAY_CARDS_SUBMIT, TURN_END_SUBMIT, ARTIFACT_SUBMIT)
    ]
    assert shapes[0] == shapes[1] == shapes[2]


def test_all_submit_tools_accept_optional_unsettled_affixes() -> None:
    for tool in (PLAY_CARDS_SUBMIT, TURN_END_SUBMIT, ARTIFACT_SUBMIT):
        properties = tool.function.parameters["properties"]
        assert "unsettled_affixes" in properties
        # 仍只需 combat_log / narrative 即可提交
        assert tool.function.parameters["required"] == ["combat_log", "narrative"]
