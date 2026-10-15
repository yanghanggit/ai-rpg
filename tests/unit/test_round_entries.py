"""Round 记录队列单元测试：验证跨种类操作的全局先后顺序。"""

from ai_rpg.models.combat import Round, RoundEntry, RoundEntryKind


def test_record_preserves_global_order_across_kinds() -> None:
    rnd = Round()
    rnd.record(RoundEntryKind.CARDS, "出牌1", "叙事1")
    rnd.record(RoundEntryKind.GEAR, "装备", "装备叙事")
    rnd.record(RoundEntryKind.CARDS, "出牌2", "叙事2")
    rnd.record(RoundEntryKind.CONSUMABLE, "消耗品", "消耗品叙事")
    rnd.record(RoundEntryKind.ARTIFACT, "神器", "神器叙事")

    assert [e.kind for e in rnd.entries] == [
        RoundEntryKind.CARDS,
        RoundEntryKind.GEAR,
        RoundEntryKind.CARDS,
        RoundEntryKind.CONSUMABLE,
        RoundEntryKind.ARTIFACT,
    ]
    # log/narrative 成对绑定在同一条目上
    assert rnd.entries[0].log == "出牌1"
    assert rnd.entries[0].narrative == "叙事1"


def test_round_serialization_round_trip() -> None:
    rnd = Round()
    rnd.record(RoundEntryKind.CARDS, "log", "narrative")
    restored = Round.model_validate_json(rnd.model_dump_json())
    assert restored == rnd
    assert restored.entries[0] == RoundEntry(
        kind=RoundEntryKind.CARDS, log="log", narrative="narrative"
    )


def test_kind_is_str_enum() -> None:
    assert RoundEntryKind.CARDS.value == "cards"
    assert RoundEntryKind("artifact") is RoundEntryKind.ARTIFACT
