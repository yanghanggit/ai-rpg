"""api_agent.status._entity_summary 失能字段测试。

确认摘要暴露 lives 与 incapacitated，供远程 AI 代理感知队友是否已永久失能。
"""

from ai_rpg.api_agent.status import _entity_summary
from ai_rpg.entitas import EntityData


def _components(*, lives: int, incapacitated: bool) -> EntityData:
    data: EntityData = {
        "NPCComponent": {"name": "角色.NPC_A"},
        "CharacterStatsComponent": {
            "name": "角色.NPC_A",
            "stats": {
                "hp": 5,
                "max_hp": 10,
                "attack": 3,
                "defense": 1,
                "lives": lives,
            },
        },
    }
    if incapacitated:
        data["IncapacitatedComponent"] = {"name": "角色.NPC_A"}
    return data


def test_summary_exposes_lives_and_incapacitated() -> None:
    summary = _entity_summary("角色.NPC_A", _components(lives=0, incapacitated=True))

    assert summary["lives"] == 0
    assert summary["incapacitated"] is True
    assert summary["dead"] is False


def test_summary_healthy_npc() -> None:
    summary = _entity_summary("角色.NPC_A", _components(lives=3, incapacitated=False))

    assert summary["lives"] == 3
    assert summary["incapacitated"] is False
