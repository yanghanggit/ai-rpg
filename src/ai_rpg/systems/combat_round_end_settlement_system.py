"""战斗回合末状态效果结算系统：并发调用 LLM 推理 ROUND_END 效果对 HP 的影响，处理排斥移除，并将繁殖/新增效果转发给 AddStatusEffectsActionSystem。"""

from typing import Final, List, Optional, final, override

from loguru import logger
from pydantic import BaseModel

from ..deepseek import DeepSeekClient, batch_chat
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.dbg_combat_processor import (
    accumulate_status_effects_action,
    compute_character_stats,
    get_status_effects_by_phase,
    set_character_hp,
)
from ..game.dbg_game import DBGGame
from ..models import (
    AffixTrigger,
    DeathComponent,
    HumanMessage,
    PhaseType,
    StatusEffect,
    StatusEffectsComponent,
)
from ..utils import extract_json


def _make_round_end_hp_update_message(new_hp: int, max_hp: int) -> str:
    """生成回合末生命值更新的 LLM 通知文本。"""
    return f"# 回合末结算 — 生命值更新\n\n当前HP: {new_hp}/{max_hp}"


def _make_round_end_remove_effects_message(removed: List[StatusEffect]) -> str:
    """生成回合末状态效果移除通知文本。"""
    lines = ["# 回合末结算 — 状态效果移除"]
    for effect in removed:
        lines.append(f"- {effect.name} 已被顶掉/清除")
    return "\n".join(lines)


###############################################################################################################################################
@final
class _RoundEndEffectResponse(BaseModel):
    """回合末状态效果 LLM 推理响应"""

    hp: int  # 效果 tick 后的新 HP（LLM 计算；系统会 clamp 至 [0, max_hp]）
    combat_log: str  # 简短战斗记录（如"中毒发作，扣除3HP"）
    remove_effects: List[str] = []  # 排斥/克制：按名精确移除（同名全部移除）
    add_effect_affixes: List[str] = (
        []
    )  # 繁殖/新增：affix 描述文本，交由 AddStatusEffectsActionSystem 生成


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

根据以上状态效果，推算本回合末结算后你的新 HP，并判断效果之间的排斥/克制与繁殖/新增。

**约束**：
- 最终 HP 必须在 0 ～ {max_hp} 范围内
- 仅上方列出的效果参与本次计算，不考虑其他因素

**效果增删规则**：
- `remove_effects`：要顶掉/清除的现有效果名（按名精确匹配，同名全部移除）；仅在效果间存在克制/排斥关系时输出
- `add_effect_affixes`：本回合末应繁殖/新生的效果描述文本（每条 affix 由下游生成 1 个 StatusEffect）；需写清目标效果名与规则，同名覆盖旧效果、异名追加；无则输出空数组

```json
{{
  "hp": <新HP整数值>,
  "combat_log": "<简短战斗记录，如：中毒发作，扣除3HP>",
  "remove_effects": ["<被顶掉的效果名>"],
  "add_effect_affixes": ["<繁殖/新增效果的 affix 描述>"]
}}
```

只输出JSON，不要输出其他内容。"""


###############################################################################################################################################
@final
class CombatRoundEndSettlementSystem(ExecuteProcessor):
    """
    战斗回合末状态效果结算系统：并发调用 LLM 推理 ROUND_END 效果的 HP 变化并写回实体。
    """

    ############################################################################################################
    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ############################################################################################################
    @override
    async def execute(self) -> None:

        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("当前战斗状态非 ONGOING，跳过 ROUND_END 效果结算")
            return

        current_rounds = self._game.current_dungeon_combat_room.combat.rounds or []
        if len(current_rounds) == 0:
            return

        last_round = self._game.current_dungeon_combat_room.combat.latest_round
        assert last_round is not None, "latest_round is None"
        if not last_round.is_completed:
            return

        # 为所有存活且持有 ROUND_END 状态效果的实体创建聊天客户端，用于并发调用 LLM 推理 HP 变化
        entities = self._game.get_group(
            Matcher(all_of=[StatusEffectsComponent], none_of=[DeathComponent])
        ).entities.copy()
        chat_clients = [
            client
            for entity in entities
            if (client := self._create_round_end_effect_client(entity)) is not None
        ]

        # 并发调用 LLM 推理所有实体的 ROUND_END 效果
        logger.debug(f"开始并发结算 {len(chat_clients)} 个实体的 ROUND_END 效果...")
        await batch_chat(clients=chat_clients)

        # 处理每个实体的 LLM 响应，更新 HP 并写入上下文
        for chat_client in chat_clients:
            self._apply_round_end_effect_response(chat_client)

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
            full_prompt=prompt,
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
            json_content = extract_json(chat_client.response_content)
            response = _RoundEndEffectResponse.model_validate_json(json_content)
        except Exception as e:
            logger.error(f"[{entity.name}] ROUND_END 效果结算异常: {e}")
            logger.error(f"原始响应: {chat_client.response_content}")
            return

        # 将本轮 prompt 和 AI 回复写入 agent 上下文，完成对话
        self._game.add_human_message(
            entity, HumanMessage(content=chat_client.full_prompt)
        )

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

        # 排斥/克制：按名精确移除被顶掉的效果（同名全部移除）
        if response.remove_effects:
            removed = self._remove_status_effects_by_name(
                entity, response.remove_effects
            )
            if removed:
                logger.info(
                    f"[{entity.name}] ROUND_END 移除 {len(removed)} 个效果: "
                    f"{[e.name for e in removed]}"
                )
                self._game.add_human_message(
                    entity,
                    HumanMessage(
                        content=_make_round_end_remove_effects_message(removed)
                    ),
                )

        # 繁殖/新增：将 affix 描述转成 AffixTrigger，交由 AddStatusEffectsActionSystem 生成
        if response.add_effect_affixes:
            triggers = [
                AffixTrigger(source="回合末结算", affix=affix)
                for affix in response.add_effect_affixes
            ]
            accumulate_status_effects_action(entity, triggers)
            logger.info(
                f"[{entity.name}] ROUND_END 繁殖/新增 {len(triggers)} 条 affix，"
                "待 AddStatusEffectsActionSystem 生成"
            )

    ################################################################################################################
    def _remove_status_effects_by_name(
        self, entity: Entity, names: List[str]
    ) -> List[StatusEffect]:
        """按名称精确移除状态效果（同名全部移除），返回被移除的效果列表。"""
        assert entity.has(
            StatusEffectsComponent
        ), f"{entity.name} 缺少 StatusEffectsComponent！"
        status_comp = entity.get(StatusEffectsComponent)
        remove_set = set(names)
        removed = [e for e in status_comp.status_effects if e.name in remove_set]
        if removed:
            status_comp.status_effects = [
                e for e in status_comp.status_effects if e.name not in remove_set
            ]
        return removed

    ################################################################################################################
