"""战斗回合清理系统：回合结束后重置战场瞬态，确保下一回合以干净状态启动。"""

from typing import Final, List, Optional, final, override
from loguru import logger
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.dbg_game import DBGGame
from ..game.entity_ops import (
    compute_character_stats,
    get_status_effects_by_phase,
    set_character_hp,
)
from ..game.zero_health_processor import process_zero_health_entities
from ..models import (
    ActorComponent,
    HumanMessage,
    StatusEffect,
    StatusEffectsComponent,
    PhaseType,
)
from ..utils import extract_json_from_code_block


def _make_round_end_hp_update_message(new_hp: int, max_hp: int) -> str:
    """生成回合末生命值更新的 LLM 通知文本。

    Args:
        new_hp: 结算后的当前 HP
        max_hp: 最大 HP

    Returns:
        写入 agent 上下文的 human message 文本
    """
    return f"# 回合末结算 — 生命值更新\n\n当前HP: {new_hp}/{max_hp}"


def _make_status_effects_tick_message(
    ticked: List[StatusEffect],
    expired: List[StatusEffect],
) -> str:
    """生成回合结束时状态效果更新的 LLM 通知文本。

    Args:
        ticked: 持续时间已递减但尚未过期的效果列表
        expired: 本回合耗尽（已移除）的效果列表

    Returns:
        写入 agent 上下文的 human message 文本
    """
    lines = ["# 回合结束 — 状态效果更新"]
    for e in ticked:
        lines.append(f"- {e.name}（剩余{e.duration}回合）")
    for e in expired:
        lines.append(f"- {e.name} → 已过期，已从状态列表移除")
    return "\n".join(lines)


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
    """生成回合末状态效果结算提示词。

    Args:
        entity_name: 角色名称
        current_hp: 当前 HP
        max_hp: 最大 HP
        round_end_effects: 本回合末生效的 ROUND_END 状态效果列表

    Returns:
        格式化的提示词字符串，要求 LLM 输出 RoundEndEffectResponse JSON
    """

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
class CombatRoundCleanupSystem(ExecuteProcessor):
    """
    战斗回合清理系统。
    """

    ############################################################################################################
    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ############################################################################################################
    @override
    async def execute(self) -> None:

        if not self._game.current_dungeon.is_ongoing:
            logger.debug("当前战斗状态非 ONGOING，跳过旧回合状态清除")
            return

        current_rounds = self._game.current_dungeon.current_rounds or []
        if len(current_rounds) == 0:
            return

        last_round = self._game.current_dungeon.latest_round
        assert last_round is not None, "latest_round is None"
        if not last_round.is_completed:
            return

        logger.debug("清除旧回合手牌状态")
        self._game.clear_round_state()

        """并发为所有持有 ROUND_END 效果的实体调用 LLM 推理 HP 变化。"""
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

        # 推进所有角色的状态效果时钟，移除到期效果，并将变化同步写入角色 agent 上下文
        self.tick_status_effects_duration()

    ############################################################################################################
    def tick_status_effects_duration(self) -> None:
        """推进所有角色的状态效果时钟，移除到期效果，并将变化同步写入角色 agent 上下文。"""
        for entity in self._game.get_group(
            Matcher(StatusEffectsComponent)
        ).entities.copy():
            assert entity.has(
                ActorComponent
            ), f"Entity {entity.name} has StatusEffectsComponent but is not an Actor"
            comp = entity.get(StatusEffectsComponent)

            # 递减持续时间并移除过期效果
            updated = []
            ticked = []
            expired = []
            for effect in comp.status_effects:
                if effect.duration == -1:
                    updated.append(effect)
                    continue
                effect.duration -= 1
                if effect.duration > 0:
                    updated.append(effect)
                    ticked.append(effect)
                else:
                    expired.append(effect)
                    logger.debug(
                        f"[{entity.name}] 状态效果「{effect.name}」持续时间耗尽，已移除"
                    )

            # 更新组件状态效果列表
            comp.status_effects = updated

            # 没有任何变化则跳过写入上下文
            if not ticked and not expired:
                continue

            # 将更新结果写入角色上下文，保持对话连续性
            self._game.add_human_message(
                entity,
                HumanMessage(
                    content=_make_status_effects_tick_message(ticked, expired)
                ),
            )

    ################################################################################################################
    def _create_round_end_effect_client(
        self, entity: Entity
    ) -> Optional[DeepSeekClient]:
        """为单个实体构建 ROUND_END 效果的 DeepSeekClient；无效果时返回 None。"""
        # assert entity.has(
        #     ActorComponent
        # ), f"Entity {entity.name} has StatusEffectsComponent but is not an Actor"
        # round_end_effects = [
        #     e
        #     for e in entity.get(StatusEffectsComponent).status_effects
        #     if e.phase == PhaseType.ROUND_END
        # ]
        # if not round_end_effects:
        #     return None

        round_end_effects = get_status_effects_by_phase(entity, PhaseType.ROUND_END)
        if len(round_end_effects) == 0:
            return None

        logger.info(
            f"[{entity.name}] 发现 {len(round_end_effects)} 个 ROUND_END 效果: "
            f"{[e.name for e in round_end_effects]}"
        )
        # assert entity.has(
        #     CharacterStatsComponent
        # ), f"Entity {entity.name} has ROUND_END effects but is missing CharacterStatsComponent"
        current_stats = compute_character_stats(entity)

        prompt = _generate_round_end_effects_prompt(
            entity_name=entity.name,
            current_hp=current_stats.hp,
            max_hp=current_stats.max_hp,
            round_end_effects=round_end_effects,
        )
        return DeepSeekClient(
            name=entity.name,
            prompt=prompt,
            context=self._game.get_agent_context(entity).context,
        )

    ################################################################################################################
    def _apply_round_end_effect_response(self, chat_client: DeepSeekClient) -> None:
        """解析单个实体的 ROUND_END LLM 响应，更新 HP 并写入 agent 上下文。"""

        entity = self._game.get_entity_by_name(chat_client.name)
        assert entity is not None, f"无法找到角色实体: {chat_client.name}"

        try:
            json_content = extract_json_from_code_block(chat_client.response_content)
            response = _RoundEndEffectResponse.model_validate_json(json_content)

            # 将本轮 prompt 和 AI 回复写入 agent 上下文，完成对话
            self._game.add_human_message(
                entity, HumanMessage(content=chat_client.prompt)
            )
            assert chat_client.response_ai_message is not None
            self._game.add_ai_message(entity, chat_client.response_ai_message)

            after_stats = set_character_hp(entity, response.hp)
            new_hp = after_stats.hp
            max_hp = after_stats.max_hp
            logger.info(
                f"[{entity.name}] ROUND_END tick: {new_hp}/{max_hp}, log={response.combat_log!r}"
            )

            self._game.add_human_message(
                entity,
                HumanMessage(content=_make_round_end_hp_update_message(new_hp, max_hp)),
            )

        except Exception as e:
            logger.error(f"[{entity.name}] ROUND_END 效果结算异常: {e}")

    ################################################################################################################
