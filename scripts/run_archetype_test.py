"""生成一个卡牌流派 archetype（多个 keywords）。"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

import click

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from ai_rpg.deepseek import MODEL_PRO, DeepSeekClient
from ai_rpg.models.messages import SystemMessage


# 日志文件目录 archetypes
ARCHETYPE_DIR = Path(".archetypes")
ARCHETYPE_DIR.mkdir(parents=True, exist_ok=True)
assert ARCHETYPE_DIR.exists(), f"找不到目录: {ARCHETYPE_DIR}"

# ── 系统提示词：跨内容原则 + 可结算边界 + 文本风格 + 衔接与弱点 ──
_SYSTEM_PROMPT = SystemMessage(
    content="""# 你是本游戏的卡牌构筑设计者。你为角色设计「keywords」——一组跨内容的逻辑关键词，是角色牌库的规则层蓝图；牌库生成 LLM 会逐条消费它们，每条 keyword 对应一张卡牌。

## 本游戏的战斗流程

战斗按回合推进，回合内角色按速度依次行动，消耗行动点（energy）出牌。角色 AI 决策出牌后，由场景实体「仲裁 LLM」结算：它以卡的确定性基数为底，结合卡上词缀与场上双方的持续状态，自由泛化出本次结果。命中的牌会把延迟词缀转为持续状态，挂到目标身上，在后续回合按阶段生效。

## 关键设计点（机制的根部）

卡牌由以下部分组成：
- 确定性基数：damage（单段伤害，被目标防御减免）、hit_count（段数）、target_type（单目标 / 全体 / 散射 / 自身）。
- 即时词缀：本次出牌结算生效的一次性规则，仲裁 LLM 在执行确定性基数之上自行泛化套用。
- 延迟词缀：命中目标后转化为持续状态。
- 资源字段：cost（行动点消耗）、playable（是否可出）、exhaust（出后本场移除）。

持续状态（StatusEffect）由以下部分组成：
- description：一段仲裁 LLM 能直接套用的规则文本。
- phase：生效时机——出牌 / 使用结算时、每回合末、抽牌后。
- counter：一个整数计数，由仲裁 LLM 按游戏事件推进（可增可减）。
- speed / defense：确定性的属性修正。

框架边界：战斗只发生在当前场景的既有角色之间，没有生成新实体、操控角色行动、改牌堆的机制；需要这些能力的想法都不可结算。

## 设计哲学

- 机制与内容分离：keywords 只写规则层逻辑，用游戏通用词汇；禁止绑定具体人设、世界观或叙事内容——人设润色由 profile 在运行时注入。
- 有衔接：keywords 不是并列功能清单，而是一条互相衔接的取胜链条，前一张的产出喂给后一张，整套有且仅有一个明确的「如何对自己有利」的倾向。
- 有弱点：该倾向必须自带结构性弱点，并在输出中显式写出。
- 可结算：每条 keyword 都必须能被上面的流程落地；设计应落在「稳定且无聊」与「花哨但无法结算」之间。

## keyword 文本风格
每条 keyword =「类型名（可选：优质）：一句话」，只声明效果倾向（定性）、目标、时效与资源倾向，不写具体数值，不写人设与世界观内容。同一效果可有「普通 / 优质」两档，作为两条独立 keyword 并列放入池中。"""
)


def build_prompt(strategy: str | None, num_keywords: int) -> str:
    """构造本次生成任务提示词"""
    seed = (
        f"策略方向种子：{strategy}。围绕该方向设计。"
        if strategy
        else "策略方向由你自由设计。"
    )
    keyword_lines = "\n".join(f"- <keyword {i}>" for i in range(1, num_keywords + 1))
    return f"""请设计一个完整的 archetype（含 {num_keywords} 条 keywords）。{seed}

流派名称用游戏设计通用词汇，不绑定任何具体人设。

输出 Markdown，严格遵循以下结构：

## 流派

<逻辑流派名称 + 一句话定位>

## 倾向

<如何取胜：keywords 的衔接逻辑>

## 弱点

<结构性弱点>

## keywords

{keyword_lines}"""


async def generate(strategy: str | None, num_keywords: int) -> DeepSeekClient:
    """调用 MODEL_PRO + thinking 生成 archetype"""
    client = DeepSeekClient(
        name="archetype_gen",
        full_prompt=build_prompt(strategy, num_keywords),
        context=[_SYSTEM_PROMPT],
        model=MODEL_PRO,
        thinking=True,
        timeout=300,
    )
    await client.chat()
    return client


def write_outputs(
    client: DeepSeekClient, strategy: str | None, num_keywords: int
) -> tuple[Path, Path | None]:
    """最终输出写入 .archetypes/ 下的 .md，思考过程写入独立的 .txt"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = ARCHETYPE_DIR / f"{timestamp}_archetype.md"

    reasoning = client.response_reasoning_content.strip()
    output = client.response_content.strip()

    content = f"""# archetype 生成结果

- 模型：`{MODEL_PRO}`
- 思考模式：开启
- 生成时间：{datetime.now().isoformat()}
- keyword 数量：{num_keywords}
- 策略方向：{strategy or '自由设计'}

---

## 最终输出

{output}
"""
    md_path.write_text(content, encoding="utf-8")

    reasoning_path: Path | None = None
    if reasoning:
        reasoning_path = ARCHETYPE_DIR / f"{timestamp}_archetype_reasoning.txt"
        reasoning_path.write_text(reasoning + "\n", encoding="utf-8")

    return md_path, reasoning_path


async def _run(strategy: str | None, num_keywords: int) -> None:
    client = await generate(strategy, num_keywords)

    print("=" * 80)
    print("💭 思考过程:")
    print(client.response_reasoning_content)
    print("=" * 80)
    print("📝 最终输出:")
    print(client.response_content)
    print("=" * 80)

    path, reasoning_path = write_outputs(client, strategy, num_keywords)
    print(f"✅ 已写入: {path}")
    if reasoning_path is not None:
        print(f"✅ 思考过程: {reasoning_path}")


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
    "num_keywords",
    default=6,
    show_default=True,
    help="生成的 keyword 数量。",
)
def main(strategy: str | None, num_keywords: int) -> None:
    """生成一个跨内容的卡牌流派 archetype 并写入 .archetypes/。"""
    asyncio.run(_run(strategy, num_keywords))


if __name__ == "__main__":
    main()
