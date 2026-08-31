"""生成一个卡牌流派 archetype（一组互相衔接的 Card），直接输出 Card 结构体。

与旧版不同：不再生成 keywords 中间层（GenerateDeckActionSystem 已停用），
而是让 LLM 直接产出一组完整卡牌，写入 .archetypes/ 下的单个 JSON 文件。

JSON 结构：
{
  "model": ...,
  "thinking": ...,
  "generated_at": ...,
  "strategy": ...,
  "card_count_requested": ...,
  "card_count_actual": ...,
  "archetype": {"name", "positioning", "win_condition", "weakness"},
  "thinking_process": ...,
  "cards": [ ...Card... ],
  "warnings": [...],
  "raw_output": ...
}
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import click
from pydantic import BaseModel

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from ai_rpg.deepseek import MODEL_FLASH, MODEL_PRO, DeepSeekClient
from ai_rpg.models.card import Card
from ai_rpg.models.messages import SystemMessage
from ai_rpg.models.target_type import TargetType
from ai_rpg.systems.card_prompt_builders import BUILD_CARD_FIELD_DESCRIPTION
from ai_rpg.utils import extract_json

# 日志文件目录 archetypes
ARCHETYPE_DIR = Path(".archetypes")
ARCHETYPE_DIR.mkdir(parents=True, exist_ok=True)
assert ARCHETYPE_DIR.exists(), f"找不到目录: {ARCHETYPE_DIR}"

# 可选模型
MODEL_CHOICES = {
    "flash": MODEL_FLASH,
    "pro": MODEL_PRO,
}


# ── 系统提示词：跨内容原则 + 可结算边界 + 文本风格 + 衔接与弱点 ──
_SYSTEM_PROMPT = SystemMessage(
    content="""# 你是本游戏的卡牌构筑设计者。为一个角色设计一个完整 archetype——一组互相衔接的战斗卡牌（Card），直接作为该角色初始牌库蓝图。

## 设计铁律

- 机制与内容分离：只写规则层逻辑，用游戏通用词汇，不绑定人设/世界观/叙事内容（人设润色由 profile 运行时注入）。
- 有衔接：不是并列功能清单，而是一条互相衔接的取胜链条；整套有且仅有一个「如何对自己有利」的倾向。
- 有弱点：该倾向自带结构性弱点，并在 narrative 中显式写出。
- 可结算：每张卡都能被战斗流程落地，落在「稳定且无聊」与「花哨但无法结算」之间。
- 字段独立：每个字段只表达自己的职责，不重复、不互相替代。

## 数值原则

随成长数值（伤害/防御）挂靠聚合属性（攻击/防御）作基数；离散数值（hit_count/cost）给确定值。"""
)


###############################################################################################################################################
class ArchetypeNarrative(BaseModel):
    """archetype 的叙事元数据（流派名称 / 定位 / 取胜逻辑 / 结构性弱点）。"""

    name: str = ""
    positioning: str = ""
    win_condition: str = ""
    weakness: str = ""


###############################################################################################################################################
class CardEntry(BaseModel):
    """LLM 输出中的单张卡牌条目；source / uuid / gear_item 由脚本侧填充，不在其中。"""

    name: str
    description: str
    on_play_affixes: List[str] = []
    on_hit_affixes: List[str] = []
    on_turn_end_affixes: List[str] = []
    playable: bool = True
    exhaust: bool = False
    retain: bool = False
    ethereal: bool = False
    transferable: bool = False
    cost: int = 1
    damage: int = 0
    hit_count: int = 1
    block: int = 0
    target_type: str = TargetType.SINGLE
    self_target: bool = False


###############################################################################################################################################
def build_prompt(strategy: str | None, num_cards: int) -> str:
    """构造本次生成任务提示词"""
    seed = (
        f"策略方向种子：{strategy}。围绕该方向设计。"
        if strategy
        else "策略方向由你自由设计。"
    )
    return f"""请设计一个完整的 archetype：{num_cards} 张互相衔接的战斗卡牌。{seed}

流派名称用游戏设计通用词汇，不绑定任何具体人设。

## 输出格式

输出 JSON，严格遵循以下结构（`cards` 数组长度恰好为 {num_cards}）：

```json
{{
  "archetype": {{
    "name": "<逻辑流派名称>",
    "positioning": "<一句话定位>",
    "win_condition": "<如何取胜：卡牌之间的衔接逻辑>",
    "weakness": "<结构性弱点>"
  }},
  "cards": [
    {{
      "name": "...",
      "description": "...",
      "on_play_affixes": [],
      "on_hit_affixes": [],
      "on_turn_end_affixes": [],
      "playable": true,
      "exhaust": false,
      "retain": false,
      "ethereal": false,
      "transferable": false,
      "cost": 1,
      "damage": 0,
      "hit_count": 1,
      "block": 0,
      "target_type": "single",
      "self_target": false
    }}
  ]
}}
```

{BUILD_CARD_FIELD_DESCRIPTION}

## 约束

- `cards` 数组长度必须恰好为 {num_cards}
- 每张卡必须给出所有字段；无附加效果时 on_play_affixes / on_hit_affixes / on_turn_end_affixes 输出 []
- `description` 是叙事锚点：不含数值，不重述其它字段已确定的效果
- 不要输出 source / uuid / gear_item（系统自动填充）
- 只输出 JSON，不附加任何说明文字"""


###############################################################################################################################################
async def generate(
    strategy: str | None, num_cards: int, model: str, thinking: bool
) -> DeepSeekClient:
    """调用选定模型生成 archetype（可选 thinking）"""
    client = DeepSeekClient(
        name="archetype_gen",
        full_prompt=build_prompt(strategy, num_cards),
        messages=[_SYSTEM_PROMPT],
        model=model,
        thinking=thinking,
        timeout=300,
        max_tokens=65536 if thinking else None,
    )
    await client.chat()
    return client


###############################################################################################################################################
def _build_cards(raw_cards: List[object]) -> Tuple[List[Card], List[str]]:
    """把 LLM 输出的 cards 逐张校验并构造为 Card；非法卡打警告并跳过。"""
    cards: List[Card] = []
    warnings: List[str] = []
    valid_target_types = {t.value for t in TargetType}

    for i, raw_card in enumerate(raw_cards, 1):
        if not isinstance(raw_card, dict):
            warnings.append(f"第 {i} 张卡不是 JSON 对象，已跳过：{raw_card!r}")
            continue

        try:
            entry = CardEntry.model_validate(raw_card)
        except Exception as e:
            warnings.append(f"第 {i} 张卡字段校验失败，已跳过：{e}")
            continue

        if entry.target_type not in valid_target_types:
            warnings.append(
                f"第 {i} 张卡「{entry.name}」target_type 无效（{entry.target_type!r}），"
                f"有效值为 {sorted(valid_target_types)}，已跳过"
            )
            continue

        try:
            card = Card(
                name=entry.name,
                description=entry.description,
                on_play_affixes=entry.on_play_affixes,
                on_hit_affixes=entry.on_hit_affixes,
                on_turn_end_affixes=entry.on_turn_end_affixes,
                playable=entry.playable,
                exhaust=entry.exhaust,
                retain=entry.retain,
                ethereal=entry.ethereal,
                transferable=entry.transferable,
                cost=entry.cost,
                damage=entry.damage,
                hit_count=entry.hit_count,
                block=entry.block,
                target_type=TargetType(entry.target_type),
                self_target=entry.self_target,
                source="",
                gear_item=None,
            )
        except Exception as e:
            warnings.append(f"第 {i} 张卡「{entry.name}」构造失败，已跳过：{e}")
            continue

        cards.append(card)

    return cards, warnings


###############################################################################################################################################
def parse_response(
    client: DeepSeekClient,
) -> Tuple[dict[str, object], List[Card], str, str, List[str]]:
    """解析 LLM 响应，返回 (archetype 叙事, cards, 思考过程, 原始输出, 警告)。"""
    raw = client.response_content.strip()
    reasoning = client.response_reasoning_content.strip()
    warnings: List[str] = []
    archetype: dict[str, object] = {}
    cards: List[Card] = []

    try:
        data = json.loads(extract_json(raw))
    except Exception as e:
        warnings.append(f"解析 LLM 输出 JSON 失败：{e}")
        return archetype, cards, reasoning, raw, warnings

    if not isinstance(data, dict):
        warnings.append("LLM 输出不是 JSON 对象")
        return archetype, cards, reasoning, raw, warnings

    try:
        archetype = ArchetypeNarrative.model_validate(
            data.get("archetype") or {}
        ).model_dump(mode="json")
    except Exception as e:
        warnings.append(f"解析 archetype 叙事元数据失败：{e}")

    raw_cards = data.get("cards")
    if not isinstance(raw_cards, list):
        warnings.append("cards 字段缺失或不是数组")
        return archetype, cards, reasoning, raw, warnings

    cards, card_warnings = _build_cards(raw_cards)
    warnings.extend(card_warnings)

    return archetype, cards, reasoning, raw, warnings


###############################################################################################################################################
def write_outputs(
    *,
    strategy: str | None,
    num_cards: int,
    model: str,
    thinking: bool,
    archetype: dict[str, object],
    cards: List[Card],
    reasoning: str,
    raw: str,
    warnings: List[str],
) -> Path:
    """最终输出写入 .archetypes/ 下的单个 JSON 文件。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = ARCHETYPE_DIR / f"{timestamp}_archetype.json"

    data = {
        "model": model,
        "thinking": thinking,
        "generated_at": datetime.now().isoformat(),
        "strategy": strategy or "自由设计",
        "card_count_requested": num_cards,
        "card_count_actual": len(cards),
        "archetype": archetype,
        "thinking_process": reasoning,
        "cards": [card.model_dump(mode="json") for card in cards],
        "warnings": warnings,
        "raw_output": raw,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


###############################################################################################################################################
async def _run(
    strategy: str | None, num_cards: int, model: str, thinking: bool
) -> None:
    client = await generate(strategy, num_cards, model, thinking)

    print("=" * 80)
    print("💭 思考过程:")
    print(client.response_reasoning_content)
    print("=" * 80)
    print("📝 最终输出:")
    print(client.response_content)
    print("=" * 80)

    archetype, cards, reasoning, raw, warnings = parse_response(client)
    path = write_outputs(
        strategy=strategy,
        num_cards=num_cards,
        model=model,
        thinking=thinking,
        archetype=archetype,
        cards=cards,
        reasoning=reasoning,
        raw=raw,
        warnings=warnings,
    )

    print(f"✅ 已写入: {path}")
    print(f"   卡牌数量: {len(cards)}/{num_cards}")
    if archetype:
        print(f"   流派: {archetype.get('name', '')}")
    for warning in warnings:
        print(f"⚠️  {warning}")


###############################################################################################################################################
@click.command()
@click.option(
    "--strategy",
    "-s",
    default=None,
    help="策略方向种子（逻辑层面，如「消耗控制」「爆发收割」「防御反击」），留空则自由设计。",
)
@click.option(
    "--count",
    "-n",
    "num_cards",
    default=5,
    show_default=True,
    help="生成的卡牌数量。",
)
@click.option(
    "--model",
    "-m",
    "model",
    type=click.Choice(list(MODEL_CHOICES.keys()), case_sensitive=False),
    default="flash",
    show_default=True,
    help="使用的模型。",
)
@click.option(
    "--thinking/--no-thinking",
    "thinking",
    default=False,
    show_default=True,
    help="是否开启思考模式。",
)
def main(strategy: str | None, num_cards: int, model: str, thinking: bool) -> None:
    """生成一组互相衔接的卡牌（archetype）并写入 .archetypes/ 下的 JSON。"""
    asyncio.run(_run(strategy, num_cards, MODEL_CHOICES[model], thinking))


if __name__ == "__main__":
    main()
