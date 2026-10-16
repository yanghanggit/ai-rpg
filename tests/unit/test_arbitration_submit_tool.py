"""三种仲裁的 submit_arbitration 工具 schema 回归测试。

出牌 / 回合结束 / 神器三种仲裁共用同一个 stage 记忆、又是同名工具；参数 schema（字段集合、
required、类型）一旦漂移，LLM 会沿用上一场仲裁看到的字段而产生调用错误（如多传
unsettled_affixes）。三份定义各自写在所属仲裁文件内（不抽共享工厂），此测试锁死参数结构。

出牌仲裁作为「loop 记忆压缩」试点，额外携带 `summary`（把本次过程压缩为长期记忆）；
回合结束 / 神器仲裁暂未迁移，仍保持彼此一致。故此处断言：
- 三者同名；
- 回合结束 / 神器两者参数结构完全一致；
- 出牌仲裁 = 共享结构 + 试点字段 `summary`（字段与 required 各多一个，其余类型一致）。
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

# 出牌仲裁试点相对共享 schema 额外携带的字段
_PILOT_EXTRA_KEYS = {"summary"}


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


def test_turn_end_and_artifact_submit_tools_share_identical_parameter_shape() -> None:
    assert _schema_shape(TURN_END_SUBMIT) == _schema_shape(ARTIFACT_SUBMIT)


def test_play_cards_submit_tool_is_shared_shape_plus_pilot_summary() -> None:
    play = _schema_shape(PLAY_CARDS_SUBMIT)
    shared = _schema_shape(TURN_END_SUBMIT)
    # 字段与 required 恰好各多一个试点字段，其余类型完全一致
    assert set(play["keys"]) - set(shared["keys"]) == _PILOT_EXTRA_KEYS
    assert set(play["required"]) - set(shared["required"]) == _PILOT_EXTRA_KEYS
    assert {
        name: type_name
        for name, type_name in play["types"].items()
        if name not in _PILOT_EXTRA_KEYS
    } == shared["types"]


def test_all_submit_tools_accept_optional_unsettled_affixes() -> None:
    for tool in (PLAY_CARDS_SUBMIT, TURN_END_SUBMIT, ARTIFACT_SUBMIT):
        properties: Dict[str, Any] = tool.function.parameters["properties"]
        assert "unsettled_affixes" in properties
        # 仍只需 combat_log / narrative（+ 出牌试点的 summary）即可提交
        required: List[str] = tool.function.parameters["required"]
        assert "combat_log" in required
        assert "narrative" in required
