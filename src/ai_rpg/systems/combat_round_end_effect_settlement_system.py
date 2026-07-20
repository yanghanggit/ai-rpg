"""战斗回合末状态效果结算系统：并发调用 LLM 推理 ROUND_END 状态效果对 HP 的影响，并处理死亡结算。"""

from typing import Final, List, Optional, final, override
from loguru import logger
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.dbg_game import DBGGame
from ..game.dbg_combat_processor import (
    compute_character_stats,
    get_status_effects_by_phase,
    process_zero_health_entities,
    set_character_hp,
)
from ..models import HumanMessage, StatusEffect, StatusEffectsComponent, PhaseType
from ..utils import extract_json_from_code_block


def _make_round_end_hp_update_message(new_hp: int, max_hp: int) -> str:
    """生成回合末生命值更新的 LLM 通知文本。"""
    return f"# 回合末结算 — 生命值更新\n\n当前HP: {new_hp}/{max_hp}"


###############################################################################################################################################
@final
class _RoundEndEffectResponse(BaseModel):
    """回合末状态效果 LLM 推理响应"""

    hp: int  # 效果 tick 后的新 HP（LLM 计算；系统会 clamp 至 [0, max_hp]）
    combat_log: str  # 简短战斗记录（如"中毒发作，扣除3HP"）


###############################################################################################################################################
def _generate_round_end_effects_prompt(
    entity_name: str,
    current_hp: int,
    max_hp: int,
    round_end_effects: List[StatusEffect],
) -> str:
    """生成回合末状态效果结算提示词。"""

    def _fmt_duration(d: int) -> str:
        return "永久" if d == -1 else f"剩余{d}回合"

    effects_list = "\n".join(
        [
            f"- {e.name}（{_fmt_duration(e.duration)}）: {e.description}"
            for e in round_end_effects
        ]
    )

    return f"""# 回合末状态效果结算

角色：{entity_name}
当前HP：{current_hp}/{max_hp}

## 本回合末生效的状态效果

{effects_list}

根据以上状态效果，推算本回合末结算后你的新 HP。

**约束**：
- 最终 HP 必须在 0 ～ {max_hp} 范围内
- 仅上方列出的效果参与本次计算，不考虑其他因素

```json
{{
  "hp": <新HP整数值>,
  "combat_log": "<简短战斗记录，如：中毒发作，扣除3HP>"
}}
```

只输出JSON，不要输出其他内容。"""


###############################################################################################################################################
@final
class CombatRoundEndEffectSettlementSystem(ExecuteProcessor):
    """
    战斗回合末状态效果结算系统：并发调用 LLM 推理 ROUND_END 效果的 HP 变化，并在结算后处理 HP 归零的实体（如标记死亡）。
    """

    ############################################################################################################
    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ############################################################################################################
    @override
    async def execute(self) -> None:

        if not self._game.current_combat_room.combat.is_ongoing:
            logger.debug("当前战斗状态非 ONGOING，跳过 ROUND_END 效果结算")
            return

        current_rounds = self._game.current_combat_room.combat.rounds or []
        if len(current_rounds) == 0:
            return

        last_round = self._game.current_combat_room.combat.latest_round
        assert last_round is not None, "latest_round is None"
        if not last_round.is_completed:
            return

        # 为所有持有 ROUND_END 状态效果的实体创建聊天客户端，用于并发调用 LLM 推理 HP 变化
        entities = self._game.get_group(Matcher(StatusEffectsComponent)).entities.copy()
        chat_clients = [
            client
            for entity in entities
            if (client := self._create_round_end_effect_client(entity)) is not None
        ]

        # 并发调用 LLM 推理所有实体的 ROUND_END 效果
        logger.debug(f"开始并发结算 {len(chat_clients)} 个实体的 ROUND_END 效果...")
        await DeepSeekClient.batch_chat(clients=chat_clients)

        # 处理每个实体的 LLM 响应，更新 HP 并写入上下文
        for chat_client in chat_clients:
            self._apply_round_end_effect_response(chat_client)

        # 结算后处理 HP 为 0 的实体（如标记死亡、触发后续效果等）
        process_zero_health_entities(self._game)

    ################################################################################################################
    def _create_round_end_effect_client(
        self, entity: Entity
    ) -> Optional[DeepSeekClient]:
        """为单个实体构建 ROUND_END 效果的 DeepSeekClient；无效果时返回 None。"""

        round_end_effects = get_status_effects_by_phase(entity, PhaseType.ROUND_END)
        if len(round_end_effects) == 0:
            return None

        logger.info(
            f"[{entity.name}] 发现 {len(round_end_effects)} 个 ROUND_END 效果: "
            f"{[e.name for e in round_end_effects]}"
        )
        current_stats = compute_character_stats(entity)

        prompt = _generate_round_end_effects_prompt(
            entity_name=entity.name,
            current_hp=current_stats.hp,
            max_hp=current_stats.max_hp,
            round_end_effects=round_end_effects,
        )

        # 返回 DeepSeekClient，用于并发调用 LLM 推理 ROUND_END 效果
        return DeepSeekClient(
            name=entity.name,
            prompt=prompt,
            context=self._game.get_agent_context(entity).context,
        )

    ################################################################################################################
    def _apply_round_end_effect_response(self, chat_client: DeepSeekClient) -> None:
        """解析单个实体的 ROUND_END LLM 响应，更新 HP 并写入 agent 上下文。"""

        # 检查 LLM 是否返回了有效的 AI 消息，如果没有则记录错误并返回
        if chat_client.response_ai_message is None:
            logger.error(
                f"[{chat_client.name}] LLM 返回空响应，跳过 ROUND_END 效果结算"
            )
            return

        entity = self._game.get_entity_by_name(chat_client.name)
        assert entity is not None, f"无法找到角色实体: {chat_client.name}"

        # 尝试解析 LLM 返回的 JSON 内容，构建 ROUND_END 效果响应对象
        try:
            json_content = extract_json_from_code_block(chat_client.response_content)
            response = _RoundEndEffectResponse.model_validate_json(json_content)
        except Exception as e:
            logger.error(f"[{entity.name}] ROUND_END 效果结算异常: {e}")
            logger.error(f"原始响应: {chat_client.response_content}")
            return

        # 将本轮 prompt 和 AI 回复写入 agent 上下文，完成对话
        self._game.add_human_message(entity, HumanMessage(content=chat_client.prompt))

        # 将 LLM 的 JSON 响应写入 agent 上下文，保持对话连续性
        self._game.add_ai_message(entity, chat_client.response_ai_message)

        # 应用 ROUND_END 效果，更新角色 HP，并记录日志
        after_stats = set_character_hp(entity, response.hp)
        new_hp = after_stats.hp
        max_hp = after_stats.max_hp
        logger.info(
            f"[{entity.name}] ROUND_END tick: {new_hp}/{max_hp}, log={response.combat_log!r}"
        )

        # 将本轮 HP 更新写入 agent 上下文，通知 AI 本轮的 HP 变化
        self._game.add_human_message(
            entity,
            HumanMessage(content=_make_round_end_hp_update_message(new_hp, max_hp)),
        )

    ################################################################################################################
