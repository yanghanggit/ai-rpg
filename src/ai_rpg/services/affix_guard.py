"""
词条守卫模块

提供出牌和弃牌时的词条约束检查，通过 LLM 判断手牌词条是否允许指定操作。
"""

from typing import List, Tuple
from loguru import logger
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
from ..game.tcg_game import TCGGame
from ..utils import extract_json_from_code_block
from ..models import HandComponent, Card
from ..entitas import Entity


###################################################################################################################################################################
class _AffixGuardResponse(BaseModel):
    """词条守卫 LLM 响应模型"""

    allowed: bool
    reason: str = ""


###################################################################################################################################################################
async def check_play_affixes_allowed(
    tcg_game: TCGGame,
    entity: Entity,
    selected_card: Card,
) -> Tuple[bool, str]:
    """用 LLM 判断当前手牌词条是否允许对 selected_card 执行出牌操作。

    Args:
        tcg_game: TCG 游戏实例
        entity: 执行动作的角色实体
        selected_card: 待出牌的目标卡牌

    Returns:
        (True, "") — 允许；(False, reason) — 阻止
    """
    hand_comp = entity.get(HandComponent)
    if hand_comp is None:
        return True, ""

    affix_rules: List[str] = []
    for card in hand_comp.cards:
        for affix in card.affixes:
            affix_rules.append(f"[{card.name}] {affix}")

    if not affix_rules:
        return True, ""

    rules_text = "\n".join(f"- {r}" for r in affix_rules)
    prompt = f"""# 词条守卫：判断出牌是否被允许（以 JSON 格式返回）

## 当前手牌词条规则

{rules_text}

## 待执行操作

角色「{entity.name}」想要出牌「{selected_card.name}」。

## 判断规则

逐条检查上方词条，若有词条**明确**禁止出牌操作（例如"封印：不可出牌"），则 allowed 为 false；否则为 true。reason 用一句中文说明原因。

只输出 JSON：

```json
{{
  "allowed": true,
  "reason": "无词条禁止出牌"
}}
```"""

    try:
        client = DeepSeekClient(
            name=entity.name,
            prompt=prompt,
            context=tcg_game.get_agent_context(entity).context,
        )
        await client.async_chat()
        response = _AffixGuardResponse.model_validate_json(
            extract_json_from_code_block(client.response_content)
        )
        if not response.allowed:
            logger.warning(
                f"[词条守卫] {entity.name} 出牌「{selected_card.name}」被词条阻止: {response.reason}"
            )
        return response.allowed, response.reason
    except Exception as e:
        logger.warning(
            f"[词条守卫] LLM 推理失败，放行出牌操作: {type(e).__name__}: {e}"
        )
        return True, ""


###################################################################################################################################################################
async def check_discard_affixes_allowed(
    tcg_game: TCGGame,
    entity: Entity,
    selected_card: Card,
) -> Tuple[bool, str]:
    """用 LLM 判断当前手牌词条是否允许对 selected_card 执行弃牌操作。

    Args:
        tcg_game: TCG 游戏实例
        entity: 执行动作的角色实体
        selected_card: 待弃置的目标卡牌

    Returns:
        (True, "") — 允许；(False, reason) — 阻止
    """
    hand_comp = entity.get(HandComponent)
    if hand_comp is None:
        return True, ""

    affix_rules: List[str] = []
    for card in hand_comp.cards:
        for affix in card.affixes:
            affix_rules.append(f"[{card.name}] {affix}")

    if not affix_rules:
        return True, ""

    rules_text = "\n".join(f"- {r}" for r in affix_rules)
    prompt = f"""# 词条守卫：判断弃牌是否被允许（以 JSON 格式返回）

## 当前手牌词条规则

{rules_text}

## 待执行操作

角色「{entity.name}」想要弃牌「{selected_card.name}」。

## 判断规则

逐条检查上方词条，若有词条**明确**禁止弃牌操作（例如"锁定：不可弃牌"），则 allowed 为 false；否则为 true。reason 用一句中文说明原因。

只输出 JSON：

```json
{{
  "allowed": true,
  "reason": "无词条禁止弃牌"
}}
```"""

    try:
        client = DeepSeekClient(
            name=entity.name,
            prompt=prompt,
            context=tcg_game.get_agent_context(entity).context,
        )
        await client.async_chat()
        response = _AffixGuardResponse.model_validate_json(
            extract_json_from_code_block(client.response_content)
        )
        if not response.allowed:
            logger.warning(
                f"[词条守卫] {entity.name} 弃牌「{selected_card.name}」被词条阻止: {response.reason}"
            )
        return response.allowed, response.reason
    except Exception as e:
        logger.warning(
            f"[词条守卫] LLM 推理失败，放行弃牌操作: {type(e).__name__}: {e}"
        )
        return True, ""


###################################################################################################################################################################
