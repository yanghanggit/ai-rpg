"""使用 MODEL_PRO + 思考模式生成一个卡牌流派 archetype（多个 keywords）。

参考 scripts/run_deepseek_test.py 的 DeepSeekClient 直连用法：
- 用 MODEL_PRO 高能力模型；
- thinking=True 开启思考模式，一并抓取 reasoning_content；
- 输出写入 logs/ 下的 Markdown 文件，同时打印到 stdout。

archetype 即一组 keywords（ArchetypeComponent.keywords），是角色牌库的规则层蓝图。
本脚本只生成「跨内容的逻辑层」：keywords 使用游戏设计通用词汇，不绑定具体人设；
人设润色由 profile 在运行时注入（见 demo/world.py 的 create_guzhiqiu 等工厂）。
约束目标：落在战斗管道可结算的动作集内，keywords 互相衔接成一条取胜倾向，并自带结构性弱点。
"""

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

# ── 系统提示词：跨内容原则 + 可结算边界 + 文本风格 + 衔接与弱点 ──
_SYSTEM_PROMPT = SystemMessage(
    content="""你是一名 DBG（牌库构筑游戏）的角色牌库流派（archetype）设计者。
你设计的是规则层：一组跨内容的逻辑关键词（keywords），是角色全部卡牌风格的蓝图；
牌库生成 LLM 会逐条消费它们，每条 keyword 对应一张卡牌。

## 跨内容原则（硬约束）
keywords 是纯逻辑表述，只用游戏设计通用词汇（如 穿甲、持续伤害、减速、易伤、增伤、多段、防御），禁止绑定任何具体人设、世界观或叙事内容（如特定武器、职业名、招式意象）。同一套逻辑应能套用到不同人设（人 / 妖）上，各自获得自己的解释——人设润色由 profile 在运行时注入，与本层无关。

## 可结算的动作集（硬边界，禁止超出）
keyword 描述的效果必须能被本游戏结算，只能属于以下三类：
1. 直接伤害：不携带词缀，对目标造成伤害（单目标 / 多目标 / 多段）。
2. 即时词缀：仅本次出牌结算生效的一次性规则（如本次伤害无视防御、本次伤害提高）。
3. 延迟词缀 → 持续状态：跨回合落在角色身上的影响，只能是下列之一：
   - 结算期属性变化：增减防御、增减速度、反伤、增减伤（出牌 / 使用结算时生效）；
   - 回合末生命变化：每回合末损失或恢复 HP（DOT / HOT）；
   - 抽牌后调整：影响刚抽到手牌的费用、伤害、可出性等。
禁止出现：转移、移除、召唤、改牌堆、操控目标行动、复活等——写了也无法结算。

## keyword 文本风格（只学格式与可暴露范围，不要照抄内容）
每条 keyword =「类型名（可选：优质）：一句话」。
可暴露：效果倾向（定性）、目标、时效、词缀类型（不携带词缀 / 即时词缀 / 持续状态）。
不可暴露：具体字段与数值、人设与世界观内容。
示例：
- 攻击型：对单个目标造成适中数值的直接伤害，不携带词缀。
- 穿甲型：携带即时词缀，令本次出牌伤害无视目标防御。
- 持续侵蚀型：携带持续负面状态效果（目标每回合末 HP 下降），直接伤害适中。
同一效果可有「普通 / 优质」两档，作为两条独立 keyword 并列放入池中。

## 整体倾向与衔接
keywords 不是并列的功能清单，而是一条互相衔接的取胜链条：前一张的产出是后一张的输入（例如先减防或挂持续状态，再用多段或高伤收割）。整套牌库有且仅有一个明确的「如何对自己有利」的倾向。

## 内建弱点
该倾向必须自带结构性弱点（如慢速依赖前置、怕爆发、怕被打断等），并在输出中显式写出。"""
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

流派名称用游戏设计通用词汇（如「穿甲爆发流」「消耗控制流」），不绑定任何具体人设。

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
    """最终输出写入 logs/ 下的 .md，思考过程写入独立的 .txt"""
    logs_dir = Path(__file__).resolve().parent.parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = logs_dir / f"{timestamp}_archetype.md"

    reasoning = client.response_reasoning_content.strip()
    output = client.response_content.strip()

    lines = [
        "# archetype 生成结果",
        "",
        f"- 模型：`{MODEL_PRO}`",
        "- 思考模式：开启",
        f"- 生成时间：{datetime.now().isoformat()}",
        f"- keyword 数量：{num_keywords}",
        f"- 策略方向：{strategy or '自由设计'}",
        "",
        "---",
        "",
        "## 最终输出",
        "",
        output,
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")

    reasoning_path: Path | None = None
    if reasoning:
        reasoning_path = logs_dir / f"{timestamp}_archetype_reasoning.txt"
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
    """生成一个跨内容的卡牌流派 archetype 并写入 logs/。"""
    asyncio.run(_run(strategy, num_keywords))


if __name__ == "__main__":
    main()
