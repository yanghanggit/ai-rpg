#!/usr/bin/env python3
"""查看某个存档快照里的 Spoils（候选奖励 + 已领取）及其词缀校验结果。

配合 `scripts/flush_card_prototypes.py` 使用，形成卡牌开发循环：
  刷原型 → generate-spoils → 本脚本看 agent 有没有把它设计成合规、多样的规则。

用法：
  uv run python -m scripts.inspect_spoils --snapshot .worlds/e2e/Game1/2026-...
  uv run python -m scripts.inspect_spoils --snapshot <path> --actor 角色.无名
  uv run python -m scripts.inspect_spoils --snapshot <path> --db   # 同时列出库中原型
"""

import json
from pathlib import Path

import click

from ai_rpg.models import AFFIX_FIELDS, Card, validate_affix_slot
from ai_rpg.pgsql import list_card_prototype_index


#######################################################################################################
def _print_card(card: Card, claimed: bool) -> None:
    mark = "（已领取）" if claimed else ""
    print(f"- {card.name}{mark}")
    print(
        f"    字段: damage={card.damage} hit_count={card.hit_count} block={card.block} "
        f"cost={card.cost} target={card.target_type.value} self_target={card.self_target} "
        f"retain={card.retain} exhaust={card.exhaust} ethereal={card.ethereal} "
        f"transferable={card.transferable}"
    )
    print(f"    叙事: {card.description}")
    has_affix = False
    for field in AFFIX_FIELDS:
        for affix in getattr(card, field):
            has_affix = True
            result = validate_affix_slot(field, affix, card)
            verdict = "OK " if result.ok else "BAD"
            reason = "" if result.ok else f"  ← {result.reason}"
            print(f"    [{verdict}] {field}: {affix}{reason}")
    if not has_affix:
        print("    (无词缀)")


#######################################################################################################
@click.command()
@click.option("--snapshot", required=True, help="存档快照目录")
@click.option("--actor", default="", help="只看某个角色（如 角色.无名）")
@click.option("--db", "show_db", is_flag=True, help="同时列出当前库中的原型")
def main(snapshot: str, actor: str, show_db: bool) -> None:
    """查看快照里的 Spoils 与逐条词缀校验。"""

    entities_dir = Path(snapshot) / "entities"
    if not entities_dir.is_dir():
        raise click.BadParameter(
            f"找不到实体目录: {entities_dir}", param_hint="--snapshot"
        )

    found = False
    for path in sorted(entities_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        spoils = data.get("SpoilsComponent")
        if not spoils:
            continue
        name = data.get("name", path.stem)
        if actor and name != actor:
            continue

        found = True
        claimed_uuids = {c.get("uuid") for c in spoils.get("claimed_cards", [])}
        candidates = spoils.get("candidate_cards", [])
        claimed = spoils.get("claimed_cards", [])
        print(
            f"\n=== {name} · Spoils（候选 {len(candidates)} / 已领取 {len(claimed)}）==="
        )
        for raw in candidates:
            _print_card(Card.model_validate(raw), raw.get("uuid") in claimed_uuids)

    if not found:
        print("没有找到 SpoilsComponent（可能尚未生成奖励，或被 --actor 过滤掉了）")

    if show_db:
        print("\n=== 当前库中卡牌原型 ===")
        for row in list_card_prototype_index():
            print(
                f"  {row['prototype_id']:<18} "
                f"[{row['card_type']}/{row['archetype']}] {row['name']}"
            )


#######################################################################################################
if __name__ == "__main__":
    main()
