"""记忆标记登记表（`models/memory_tags.py`）的自检。

词表与代码必须双向对齐：
- 代码用到未登记标记 → `add_human_message` / `add_ai_message` 运行时断言（见 test_rpg_agent_memory）；
- 词表登记了没人用的标记 → 本测试的「词表腐烂」检查。
"""

import re
from pathlib import Path
from typing import Dict, List, Set

from ai_rpg.models.memory_tags import MEMORY_TAGS

_SRC_ROOT = Path(__file__).resolve().parents[2] / "src"


def _all_source_text() -> str:
    """src 下全部 Python 源码（排除登记表自身）。"""
    chunks = [
        path.read_text(encoding="utf-8")
        for path in _SRC_ROOT.rglob("*.py")
        if path.name != "memory_tags.py"
    ]
    return "\n".join(chunks)


def test_no_unused_tag() -> None:
    """词表里的每个标记都要在代码里真的用到，避免登记表腐烂。"""
    source = _all_source_text()
    unused = sorted(
        tag
        for tag in MEMORY_TAGS
        if f'"{tag}"' not in source
        and f"{tag}=" not in source
        and f"{tag}:" not in source
    )
    assert not unused, f"这些标记已登记但没有任何调用点：{unused}"


def test_tags_are_identifier_friendly() -> None:
    """标记要能作为关键字参数名使用（`HumanMessage(**{tag: ...})` 与 `tag=...` 都要求）。"""
    bad = sorted(
        tag for tag in MEMORY_TAGS if not re.fullmatch(r"[a-z][a-z0-9_]*", tag)
    )
    assert not bad, f"标记名必须是 snake_case 标识符：{bad}"


_ALLOWED_DECLARED = {"content", "additional_kwargs", "type", "tool_call_id"}
_MESSAGE_CTORS = ("HumanMessage", "AIMessage", "ToolMessage", "SystemMessage")


def _top_level_kwargs(body: str) -> List[str]:
    """取构造参数体里**顶层**的 kwarg 名（忽略嵌套调用/容器的内部关键字）。"""
    keys: List[str] = []
    depth = 0
    for match in re.finditer(r"[\(\[\{\)\]\}]|[a-zA-Z_]\w*\s*=(?!=)", body):
        token = match.group(0)
        if token in "([{":
            depth += 1
        elif token in ")]}":
            depth -= 1
        elif depth == 0:
            keys.append(token.split("=")[0].strip())
    return keys


def test_message_kwargs_are_registered_tags() -> None:
    """静态闸门：消息构造处的顶层关键字必须是已登记标记。

    运行时校验（`add_human_message`）只能覆盖真的跑到的路径；本测试覆盖全部构造点，
    避免新写的标记只在没被测到的分支里静默失效。
    """
    unregistered: Dict[str, Set[str]] = {}
    for path in _SRC_ROOT.rglob("*.py"):
        if path.name in ("memory_tags.py", "messages.py"):
            continue
        text = path.read_text(encoding="utf-8")
        for ctor in _MESSAGE_CTORS:
            for match in re.finditer(rf"\b{ctor}\(", text):
                start = match.end() - 1
                depth = 0
                end = None
                for index in range(start, len(text)):
                    if text[index] == "(":
                        depth += 1
                    elif text[index] == ")":
                        depth -= 1
                        if depth == 0:
                            end = index
                            break
                assert end is not None, f"{path}: 未闭合的消息构造 {ctor}("
                for key in _top_level_kwargs(text[start + 1 : end]):
                    if key in _ALLOWED_DECLARED or key in MEMORY_TAGS:
                        continue
                    unregistered.setdefault(key, set()).add(path.name)

    assert not unregistered, f"这些关键字未在 memory_tags.py 登记：{unregistered}"


def test_every_registered_tag_is_accepted_by_runtime_gate() -> None:
    """反向：词表里的标记不会触发运行时校验（拼错/漏登记之外的另一半）。"""
    from ai_rpg.models import HumanMessage, assert_known_memory_tags

    for tag in MEMORY_TAGS:
        message = HumanMessage(content="", **{tag: "value"})
        assert_known_memory_tags(message)


def test_structured_tag_values_have_expected_shape() -> None:
    """结构化标记的值有约定形态：调用方与消费者都依赖它，不能被随手改坏。"""
    import json

    from ai_rpg.models import Card, PlayCardsAction, TargetType
    from ai_rpg.systems.card_common import (
        build_play_card_record_tag,
        build_received_card_tag,
    )

    card = Card(
        name="攻击",
        description="描述不该进标记",
        cost=1,
        damage=5,
        hit_count=1,
        block=2,
        target_type=TargetType.SINGLE,
        source="角色.无名",
    )
    action = PlayCardsAction(name="角色.无名", card=card, targets=["怪物.渡口野狗"])

    play_record = json.loads(build_play_card_record_tag(action))
    assert set(play_record) == {
        "name",
        "uuid",
        "source",
        "cost",
        "damage",
        "hit_count",
        "block",
        "target_type",
        "targets",
    }
    assert play_record["targets"] == ["怪物.渡口野狗"]

    received = json.loads(build_received_card_tag(card))
    assert set(received) == {
        "name",
        "uuid",
        "source",
        "cost",
        "damage",
        "hit_count",
        "block",
        "target_type",
    }
    # 精简后的标记不带描述/词缀，避免每条记忆被整张卡撑爆
    assert "描述不该进标记" not in json.dumps(received, ensure_ascii=False)


def test_stats_update_tag_records_hp_transition() -> None:
    """`stats_update` 的值是「旧 HP->新 HP」，审计时不必再读正文。"""
    from unittest.mock import MagicMock

    from ai_rpg.entitas.context import Context
    from ai_rpg.game.dbg_game import DBGGame
    from ai_rpg.models import (
        ActorComponent,
        CharacterStats,
        CharacterStatsComponent,
        CombatArbitrationEvent,
    )
    from ai_rpg.systems.arbitration_common import (
        ArbitrationContext,
        RoundKind,
        apply_arbitration_result,
    )

    context = Context()
    entity = context.create_entity()
    entity._name = "角色.无名"
    entity.add(ActorComponent, entity._name, "场景.河湾芦苇丛")
    entity.add(
        CharacterStatsComponent,
        entity._name,
        CharacterStats(hp=10, max_hp=10),
    )

    game = MagicMock(spec=DBGGame)
    game.current_dungeon_combat_room.combat.rounds = [MagicMock()]
    game.current_dungeon_combat_room.combat.latest_round = MagicMock()
    game.get_entity_by_name.side_effect = lambda name: entity
    game.broadcast_to_stage.side_effect = lambda **kw: None
    assert issubclass(CombatArbitrationEvent, object)

    ctx = ArbitrationContext(hp_changes={"角色.无名": 7}, narrative="被撞了一下")
    apply_arbitration_result(
        game,
        stage_entity=entity,
        ctx=ctx,
        kind=RoundKind.PLAY_CARDS,
        title_label="测试仲裁",
        combat_log="无",
    )

    stats_messages = [
        call.args[1]
        for call in game.add_human_message.call_args_list
        if getattr(call.args[1], "stats_update", None) is not None
    ]
    assert len(stats_messages) == 1
    assert stats_messages[0].stats_update == "10->7"
