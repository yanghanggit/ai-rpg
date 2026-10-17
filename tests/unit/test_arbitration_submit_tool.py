"""三种仲裁的 submit_arbitration 工具 schema 一致性回归测试。

出牌 / 回合结束 / 神器三种仲裁共用同一个 stage 记忆、又是同名工具；参数 schema（字段集合、
required、类型）一旦漂移，LLM 会沿用上一场仲裁看到的字段而产生调用错误（如多传
unsettled_affixes）。三份定义由 `arbitration_common.make_submit_arbitration_tool` 统一构造，
参数结构由构造保证一致；此测试仍锁死这一点（描述文案允许按仲裁类型不同）。

三者都携带 `summary`：loop 结束后据它把本次完整工具轨迹整段替换为一条压缩记忆。
"""

from typing import Any, Dict, List

from ai_rpg.models import Card, TargetType
from ai_rpg.systems.artifact_post_arbitration_system import (
    SUBMIT_ARBITRATION_TOOL as ARTIFACT_SUBMIT,
)
from ai_rpg.systems.play_cards_arbitration_system import (
    SUBMIT_ARBITRATION_TOOL as PLAY_CARDS_SUBMIT,
)
from ai_rpg.systems.play_cards_arbitration_system import (
    _build_play_cards_arbitration_prompt,
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


def test_all_submit_tools_require_summary() -> None:
    for tool in (PLAY_CARDS_SUBMIT, TURN_END_SUBMIT, ARTIFACT_SUBMIT):
        properties: Dict[str, Any] = tool.function.parameters["properties"]
        assert "unsettled_affixes" in properties
        assert "summary" in properties
        assert tool.function.parameters["required"] == [
            "combat_log",
            "narrative",
            "summary",
        ]


def test_submit_schema_carries_narrative_and_summary_specs() -> None:
    """narrative / summary 的字段规范属于 schema，而不是任务提示词。"""
    properties: Dict[str, Any] = PLAY_CARDS_SUBMIT.function.parameters["properties"]
    narrative: str = properties["narrative"]["description"]
    summary: str = properties["summary"]["description"]

    assert "60-120" in narrative and "第三人称" in narrative
    assert "旧→新" in summary and "长期记忆" in summary


def test_play_arbitration_prompt_does_not_restate_submit_field_specs() -> None:
    """任务提示词不应重复 submit_arbitration 字段说明（单一事实源）。"""
    card = Card(
        name="测试卡",
        description="一次试探。",
        cost=1,
        damage=1,
        hit_count=1,
        block=0,
        target_type=TargetType.SINGLE,
        on_play_affixes=[
            "[测试]:打出时，若目标的总格挡为 0，则本次伤害额外加上本卡 damage 的伤害"
        ],
    )
    prompt = _build_play_cards_arbitration_prompt(
        "角色.甲", card, ["怪物.乙"], 1, ["角色.甲", "怪物.乙"], [], "角色.甲"
    )

    assert "### narrative" not in prompt
    assert "### summary" not in prompt
    assert "60-120" not in prompt
    assert "压缩性总结" not in prompt
    # cost 不参与仲裁结算，不应出现在本卡数据里（减少噪声）。
    assert "- cost：" not in prompt


def test_arbitration_prompts_state_source_relationship_without_conditionals() -> None:
    """source 只说明「创建者 / 持有者可能不同」，不写「若 A 则 X」式条件指令。"""
    from ai_rpg.systems.autonomous_arbitration_system import (
        _build_autonomous_arbitration_tool_prompt,
    )
    from ai_rpg.systems.turn_end_arbitration_system import (
        _build_turn_end_arbitration_prompt,
    )

    card = Card(
        name="测试卡",
        description="一次试探。",
        cost=0,
        damage=1,
        hit_count=1,
        block=0,
        target_type=TargetType.SELF,
        on_turn_end_affixes=["[测试]:回合结束时回复本卡持有者 1 点 HP"],
        on_autonomous_affixes=["[测试]:自主攻击一名随机敌人"],
    )
    prompts = [
        _build_play_cards_arbitration_prompt("角色.甲", card, ["怪物.乙"], 1),
        _build_turn_end_arbitration_prompt("角色.甲", [card], 1),
        _build_autonomous_arbitration_tool_prompt(
            "角色.甲", [card], 1, "角色.甲", "怪物.乙"
        ),
    ]
    for prompt in prompts:
        assert "## source 与持有者" in prompt
        assert "创建者" in prompt and "持有者" in prompt
        assert "仅当持有者 ==" not in prompt
        assert "仅当 " not in prompt
