"""suggest_actions 的战后分支单元测试。

战斗结算后只有胜利才允许「收战利品 + 推进」；战败只能离开副本——
否则建议里会出现服务端必然拒绝的 `dungeon advance-stage`（409）。
"""

from typing import Any, Dict

from ai_rpg.dbg_api_agent.flow import suggest_actions


def _post_combat_status(
    result: str, current_room_index: int = 1, room_count: int = 4
) -> Dict[str, Any]:
    """构造一个战斗房间 POST_COMBAT 的状态快照。"""
    return {
        "mode": "dungeon",
        "dungeon": {
            "room_type": "combat",
            "current_room_index": current_room_index,
            "room_count": room_count,
        },
        "combat": {"state": "POST_COMBAT", "result": result, "round": {}},
    }


def test_post_combat_win_with_next_room_suggests_loot_and_advance() -> None:
    actions = suggest_actions(_post_combat_status("WIN", current_room_index=1))

    assert "combat collect-loot" in actions
    assert "dungeon advance-stage" in actions
    assert "dungeon exit" in actions


def test_post_combat_win_last_room_skips_advance() -> None:
    actions = suggest_actions(_post_combat_status("WIN", current_room_index=3))

    assert "combat collect-loot" in actions
    assert "dungeon advance-stage" not in actions
    assert "dungeon exit" in actions


def test_post_combat_lose_only_suggests_exit() -> None:
    actions = suggest_actions(_post_combat_status("LOSE", current_room_index=1))

    assert "dungeon exit" in actions
    assert "combat collect-loot" not in actions
    assert "dungeon advance-stage" not in actions
