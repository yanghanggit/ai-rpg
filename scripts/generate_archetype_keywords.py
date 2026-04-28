"""
生成 TCG 卡组原型（Archetype）及其关键词约束（Keywords）

流程：
  1. 同步调用 LLM 生成一个 Archetype（name + description）
  2. 基于该 Archetype，并发生成 3 个 Keyword 约束规则
  3. 将结果保存为 JSON 文件至 generated_archetypes/ 目录
"""

import asyncio
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, final

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from loguru import logger
from pydantic import BaseModel

from ai_rpg.deepseek import MODEL_FLASH, DeepSeekClient
from ai_rpg.models.messages import SystemMessage
from ai_rpg.utils import extract_json_from_code_block

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
_OUTPUT_DIR: Path = Path(__file__).resolve().parent.parent / "generated_archetypes"
_NUM_KEYWORDS: int = 3

# ---------------------------------------------------------------------------
# 本地 Pydantic 解析模型
# ---------------------------------------------------------------------------


@final
class ArchetypeResult(BaseModel):
    name: str
    description: str


@final
class KeywordResult(BaseModel):
    description: str


@final
class GeneratedArchetype(BaseModel):
    archetype: ArchetypeResult
    keywords: List[KeywordResult]


# ---------------------------------------------------------------------------
# Prompt 构建
# ---------------------------------------------------------------------------
_ARCHETYPE_SYSTEM = SystemMessage(
    content="""你是一名 TCG（集换式卡牌游戏）游戏设计师。
你的任务是设计卡组原型（Archetype）。Archetype 是具有共同核心机制、战术策略或主题风格的卡牌原型，\
是玩家和设计师用来归类卡组类型的高层次标签（如"多段连击型"、"状态控制型"、"牺牲换利型"）。

请用 JSON 代码块返回，格式如下：
```json
{"name": "原型名称（2-6字，简洁有力）", "description": "原型的整体设计意图与核心玩法定位（2-4句话）"}
```
只输出 JSON 代码块，不要任何额外说明。""",
)


def _build_archetype_prompt() -> str:
    return "请设计一个独特且有趣的 TCG 卡组原型，要求风格鲜明、机制清晰，与常见原型有所区别。"


def _build_keyword_system_message(archetype: ArchetypeResult) -> SystemMessage:
    return SystemMessage(
        content=f"""你是一名 TCG 游戏设计师。
你正在为以下卡组原型设计具体的关键词约束规则（Keyword）：

原型名称：{archetype.name}
原型描述：{archetype.description}

Keyword 是 LLM 生成卡牌时施加的具体字段级约束，示例：
- "每张卡牌的 hit_count ≥ 2，damage_dealt 不为 0"
- "每张卡牌的 effects 不得为空，优先生成持续状态效果（如虚弱、减速、灼烧）"

请用 JSON 代码块返回，格式如下：
```json
{{"description": "一条具体的卡牌生成约束规则（一句话，包含字段名与数值要求）"}}
```
只输出 JSON 代码块，不要任何额外说明。""",
    )


def _build_keyword_prompt(index: int) -> str:
    return (
        f"请为该原型设计第 {index + 1} 条关键词约束规则，"
        "确保与其他规则互补、聚焦不同的卡牌字段。"
    )


# ---------------------------------------------------------------------------
# 生成函数
# ---------------------------------------------------------------------------


def generate_archetype() -> Optional[ArchetypeResult]:
    """同步生成一个 Archetype。"""
    client = DeepSeekClient(
        name="archetype_generator",
        prompt=_build_archetype_prompt(),
        context=[_ARCHETYPE_SYSTEM],
        model=MODEL_FLASH,
        temperature=1.5,
    )
    client.chat()
    if not client.response_content:
        logger.error("archetype_generator: empty response")
        return None
    try:
        return ArchetypeResult.model_validate_json(
            extract_json_from_code_block(client.response_content)
        )
    except Exception as e:
        logger.error(
            f"archetype_generator: failed to parse response: {e}\n"
            f"Raw: {client.response_content}"
        )
        return None


async def generate_keywords(archetype: ArchetypeResult) -> List[KeywordResult]:
    """并发生成 _NUM_KEYWORDS 个 Keyword。"""
    system_msg = _build_keyword_system_message(archetype)
    clients = [
        DeepSeekClient(
            name=f"keyword_generator_{i}",
            prompt=_build_keyword_prompt(i),
            context=[system_msg],
            model=MODEL_FLASH,
            temperature=1.3,
        )
        for i in range(_NUM_KEYWORDS)
    ]
    await DeepSeekClient.batch_chat(clients)
    await DeepSeekClient.close_async_client()

    results: List[KeywordResult] = []
    for kw_client in clients:
        if not kw_client.response_content:
            logger.warning(f"{kw_client.name}: empty response, skipping")
            continue
        try:
            kw = KeywordResult.model_validate_json(
                extract_json_from_code_block(kw_client.response_content)
            )
            results.append(kw)
        except Exception as e:
            logger.warning(
                f"{kw_client.name}: failed to parse keyword: {e}\n"
                f"Raw: {kw_client.response_content}"
            )
    return results


# ---------------------------------------------------------------------------
# 保存结果
# ---------------------------------------------------------------------------


def _sanitize_name(name: str) -> str:
    """将 name 中不适合作文件名的字符替换为下划线。"""
    return re.sub(r"[^\w]", "_", name).strip("_")


def save_result(result: GeneratedArchetype) -> Path:
    """将生成结果以 JSON 格式保存到 _OUTPUT_DIR，返回文件路径。"""
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{_sanitize_name(result.archetype.name)}_{timestamp}.json"
    output_path = _OUTPUT_DIR / filename
    output_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------


def main() -> None:
    DeepSeekClient.setup()

    print("\n=== Phase 1: 生成 Archetype ===")
    archetype = generate_archetype()
    assert archetype is not None, "Archetype 生成失败，请检查日志"
    print(f"✅ 原型名称: {archetype.name}")
    print(f"   描述: {archetype.description}")

    print(f"\n=== Phase 2: 生成 Keywords (×{_NUM_KEYWORDS} 并发) ===")
    keywords = asyncio.run(generate_keywords(archetype))
    assert keywords, "Keywords 全部生成失败，请检查日志"
    for i, kw in enumerate(keywords, 1):
        print(f"  Keyword {i}: {kw.description}")

    result = GeneratedArchetype(archetype=archetype, keywords=keywords)
    output_path = save_result(result)
    print(f"\n💾 已保存至: {output_path}")


if __name__ == "__main__":
    main()
