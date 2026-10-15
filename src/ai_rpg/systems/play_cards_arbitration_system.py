"""战斗仲裁动作系统模块。"""

import json
from dataclasses import dataclass
from functools import partial
from typing import Dict, Final, List, Optional, final

from loguru import logger
from overrides import override
from pydantic import BaseModel, Field

from ..deepseek import ToolDefinition, ToolFunction, agent_loop
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_combat_processor import (
    compute_character_hand_block,
    compute_character_stats,
    set_character_hp,
)
from ..game.dbg_game import DBGGame
from ..models import (
    AIMessage,
    Card,
    CharacterStatsComponent,
    CombatArbitrationEvent,
    HandComponent,
    HumanMessage,
    PlayCardsAction,
    RoundEntryKind,
    RoundStatsComponent,
    TargetType,
    render_labeled_str_list,
)
from ..utils import prompt_builder
from .arbitration_prompt_builders import (
    ArbitrationKind,
    build_calc_rules_section,
    build_combat_log_section,
    build_narrative_section,
    build_on_hit_affix_section,
    build_tool_flow_section,
)


###########################################################################################################################################
# 仲裁提示词构建器（play_cards 专属）
###########################################################################################################################################
@dataclass
class _SpreadSections:
    """SPREAD 专属 prompt 片段"""

    hit_assignment: str
    log_example: str


def _build_spread_sections(
    card: Card,
    targets: List[str],
) -> _SpreadSections:
    """为 SPREAD 卡牌构建仲裁 prompt 中的专属片段。

    当 target_type 不是 SPREAD 时，所有字段均为空字符串。
    """
    if card.target_type != TargetType.SPREAD:
        return _SpreadSections("", "")

    hit_lines = "\n".join(f"  第{i + 1}击 → {t}" for i, t in enumerate(targets))
    hit_assignment = (
        f"\n## 命中分配（系统预先随机确定，共 {card.hit_count} 击）\n\n"
        f"{hit_lines}\n\n"
        f"按上方命中分配逐击结算；combat_log 须覆盖**所有被命中过的不重复目标**，并对每个受影响角色各调用一次 {APPLY_DAMAGE_TOOL.function.name}。"
    )
    log_example = "\nspread 示例：`[英雄|回旋镖→随机: 每击3×1−0×1=3; 敌A×2击=6, 敌B×1击=3] HP:敌A 15→9 敌B 12→9`"
    return _SpreadSections(hit_assignment=hit_assignment, log_example=log_example)


@prompt_builder
def _build_round_action_info_lines(
    action_order: List[str] | None,
    completed_actors: List[str] | None,
    current_actor: str | None,
) -> str:
    """构建回合行动信息段落（仅作背景信息，不改变结算规则）。"""
    order_text = " → ".join(action_order) if action_order else "无"
    completed_text = "、".join(completed_actors) if completed_actors else "无"
    current_text = current_actor if current_actor else "无"
    return (
        f"- 行动顺序：{order_text}\n"
        f"- 已完成行动者：{completed_text}\n"
        f"- 当前行动者：{current_text}"
    )


@prompt_builder
def _build_card_data_lines(card: Card) -> str:
    """输出一张卡参与仲裁的数值字段（词缀单列于「即时词缀」段，来源与叙事一并带上）。"""
    lines = [
        f"- 卡牌：{card.name}",
        f"- source（来源/注入者）：{card.source or '未知'}",
        f"- 叙事（description）：{card.description}",
        f"- cost：{card.cost}",
        f"- damage（本卡单次伤害）：{card.damage}",
        f"- hit_count（本卡攻击次数）：{card.hit_count}",
        f"- block（本卡单牌格挡值）：{card.block}",
    ]
    return "\n".join(lines)


@prompt_builder
def _build_combat_arbitration_tool_prompt(
    actor_name: str,
    card: Card,
    targets: List[str],
    current_round_number: int,
    action_order: List[str] | None = None,
    completed_actors: List[str] | None = None,
    current_actor: str | None = None,
) -> str:

    # 构建本回合的战斗仲裁工具 prompt，包括出牌者信息、本卡数据、目标信息、回合行动信息等。
    unique_targets = list(dict.fromkeys(targets))

    # 构建目标信息段落。
    target_names = "、".join(unique_targets) if unique_targets else "无"

    # 构建回合行动信息段落。
    round_action_info = _build_round_action_info_lines(
        action_order, completed_actors, current_actor
    )

    # 构建 SPREAD 卡牌的专属仲裁片段。
    spread = _build_spread_sections(card, targets)

    return f"""# 第 {current_round_number} 回合：战斗结算（工具调用模式）

## 出牌者

{actor_name}

## 本卡数据（本卡 = 本次实际打出的牌）

{_build_card_data_lines(card)}
{spread.hit_assignment}

## 即时词缀（共 {len(card.on_play_affixes)} 条，逐条结算，一条都不能漏）

{render_labeled_str_list("- 即时词缀", card.on_play_affixes, indent="    ")}

即时词缀是逐条独立规则：**逐条全部读取**，判断它为你给出的哪些参数取值（伤害系数 / 格挡系数 / 反伤 / 吸血 / 治疗等），据此参与骨架结算；不得合并、省略，也不引入词缀未提及的新机制。

## 目标

{target_names}

## 回合行动信息（背景信息，不改变结算规则）

{round_action_info}

{build_calc_rules_section(GET_ENTITY_STATS_TOOL.function.name, APPLY_DAMAGE_TOOL.function.name, ArbitrationKind.PLAY_CARDS)}

{build_on_hit_affix_section(GET_ENTITY_STATS_TOOL.function.name, ArbitrationKind.PLAY_CARDS)}

## source 字段

`source` = 卡牌来源（生成 / 注入者），空串表示未知；词缀提及「非 source 者」时，指当前持有者（当其 ≠ 本卡 `source` 时）。

{build_tool_flow_section(GET_ENTITY_STATS_TOOL.function.name, APPLY_DAMAGE_TOOL.function.name, SUBMIT_ARBITRATION_TOOL.function.name, ArbitrationKind.PLAY_CARDS)}

## {SUBMIT_ARBITRATION_TOOL.function.name} 字段说明

{build_combat_log_section(ArbitrationKind.PLAY_CARDS, spread.log_example)}

{build_narrative_section()}"""


@prompt_builder
def _build_combat_arbitration_broadcast(
    combat_log: str, narrative: str, current_round_number: int, actor_name: str
) -> str:
    """出牌仲裁的广播消息生成器（第 N 回合 · <出牌者> 出牌仲裁）。"""
    return f"""# 第 {current_round_number} 回合 · {actor_name} 出牌仲裁

## 演出

{narrative}

## 数据日志

{combat_log}"""


@prompt_builder
def _build_stats_update_notification(final_hp: int, max_hp: int) -> str:
    return f"""# 你的生命值已更新

当前HP: {final_hp}/{max_hp}"""


###########################################################################################################################################
# 仲裁工具定义
###########################################################################################################################################
GET_ENTITY_STATS_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="get_entity_stats",
        description="读取指定战斗角色的当前生命值（HP/最大HP）与总格挡（其手牌 block 之和）及其手牌中带受击词缀的卡牌（含这些卡牌的 source/damage/hit_count/block 等数据）。用于获取发起者与目标当前状态。",
        parameters={
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "角色全名，如 角色.无名 或 怪物.纸俑甲",
                },
            },
            "required": ["entity_name"],
        },
    )
)


APPLY_DAMAGE_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="apply_damage",
        description="对指定战斗角色结算本次的净伤害：amount 为本次结算对该角色的净 HP 扣减（正数=扣血，负数=净回复，0=不变），工具自动 clamp 到 0~最大HP。对每个受影响角色（含发起者与所有目标）都必须调用一次。",
        parameters={
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "角色全名",
                },
                "amount": {
                    "type": "integer",
                    "description": "本次结算对该角色的净 HP 扣减：正数扣血、负数净回复、0 不变",
                },
            },
            "required": ["entity_name", "amount"],
        },
    )
)


SUBMIT_ARBITRATION_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="submit_arbitration",
        description="提交本次仲裁的最终结果（战斗日志、演出叙事、无法结算的词缀）。调用后本次仲裁结束。",
        parameters={
            "type": "object",
            "properties": {
                "combat_log": {
                    "type": "string",
                    "description": "战斗数据日志；须写出计算过程（参数取值与逐次命中的代入），供核对与向玩家回报。",
                },
                "narrative": {
                    "type": "string",
                    "description": "60-120 字第三人称演出叙事",
                },
                "unsettled_affixes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "可选：无法按上述计算规则结算的词缀原文列表（如要求抽牌/回能/额外行动，或凭空叠加没有牌承载的标记），仅供系统统计，不计入结算。",
                },
            },
            "required": ["combat_log", "narrative"],
        },
    )
)


###########################################################################################################################################
# 仲裁工具 handler
###########################################################################################################################################
class _ArbitrationContext(BaseModel):
    """仲裁工具 handler 的共享结果容器。"""

    hp_changes: Dict[str, int] = Field(default_factory=dict)
    combat_log: Optional[str] = None
    narrative: Optional[str] = None
    unsettled_affixes: List[str] = Field(default_factory=list)


###########################################################################################################################################
def _collect_hand_on_hit_cards(entity: Entity) -> List[Card]:
    """收集角色手牌中所有带受击词缀的卡牌（持有期间参与受击仲裁）。"""
    hand = entity.get(HandComponent) if entity.has(HandComponent) else None
    if hand is None:
        return []
    return [card for card in hand.cards if card.on_hit_affixes]


###########################################################################################################################################
def _handle_get_entity_stats(game: DBGGame, entity_name: str) -> str:
    """处理「获取状态工具」调用：返回 HP/总格挡 + 参与受击仲裁的手牌卡牌数据。"""
    entity = game.get_actor_entity(entity_name)
    if entity is None:
        return f"错误：找不到战斗角色 {entity_name}"

    stats = compute_character_stats(entity)
    hand_block = compute_character_hand_block(entity)

    # 收集角色手牌中所有带受击词缀的卡牌（持有期间参与受击仲裁）
    hit_cards = _collect_hand_on_hit_cards(entity)
    if hit_cards:
        cards_str = "\n".join(
            f"    - {c.name}（source={c.source or '未知'}, description={c.description}, cost={c.cost}, "
            f"damage={c.damage}, hit_count={c.hit_count}, 单牌 block={c.block}, 受击词缀={c.on_hit_affixes}）"
            for c in hit_cards
        )
    else:
        cards_str = "    - 无"

    return (
        f"【{entity_name}】\n"
        f"- HP：{stats.hp}/{stats.max_hp}\n"
        f"- 总格挡（角色级＝该角色手牌 block 之和；结算伤害时只减这个数）：{hand_block}\n"
        f"- 受击卡牌（仅列出带受击词缀的卡牌，不是完整手牌；下面每张卡的 `单牌 block` 只是它自己那张牌的格挡值，**不是**上面的总格挡）：\n"
        f"{cards_str}"
    )


def _handle_apply_damage(
    game: DBGGame, ctx: _ArbitrationContext, entity_name: str, amount: int
) -> str:
    """处理「结算净伤害工具」调用：按净扣减 amount 计算并写入新 HP。"""
    entity = game.get_actor_entity(entity_name)
    if entity is None:
        return f"错误：找不到战斗角色 {entity_name}"
    stats = compute_character_stats(entity)
    clamped = max(0, min(stats.hp - int(amount), stats.max_hp))
    ctx.hp_changes[entity_name] = clamped
    return (
        f"{entity_name} HP 将更新为 {clamped}/{stats.max_hp}"
        f"（{stats.hp} → {clamped}，本次扣减 {stats.hp - clamped}）"
    )


def _handle_submit_arbitration(
    ctx: _ArbitrationContext,
    combat_log: str,
    narrative: str,
    unsettled_affixes: Optional[List[str]] = None,
) -> str:
    """处理「提交仲裁结果工具」调用。"""
    ctx.combat_log = combat_log
    ctx.narrative = narrative
    if unsettled_affixes:
        ctx.unsettled_affixes = [str(a) for a in unsettled_affixes if str(a).strip()]
    return "仲裁结果已提交"


###########################################################################################################################################
@final
class PlayCardsArbitrationSystem(ReactiveProcessor):
    """响应 PlayCardsAction 事件，对单张出牌立即进行 AI 仲裁结算（工具调用模式）。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    #######################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(PlayCardsAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(PlayCardsAction) and entity.has(RoundStatsComponent)

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("PlayCardsArbitrationSystem: 战斗未进行中，跳过仲裁")
            return

        logger.debug(
            f"PlayCardsArbitrationSystem: 触发仲裁，找到 {len(entities)} 个符合条件的出牌实体"
        )

        await self._request_combat_arbitration(entities[0])

    #######################################################################################################################################
    async def _request_combat_arbitration(self, actor_entity: Entity) -> None:
        """驱动单次出牌的完整工具化仲裁流程。"""

        stage_entity = self._game.resolve_stage_entity(actor_entity)
        assert stage_entity is not None, f"无法获取 {actor_entity.name} 所在场景实体！"

        assert actor_entity.has(
            PlayCardsAction
        ), f"实体 {actor_entity.name} 缺少 PlayCardsAction 组件！"
        play_cards_action = actor_entity.get(PlayCardsAction)

        assert actor_entity.has(
            RoundStatsComponent
        ), f"出牌实体 {actor_entity.name} 缺少 RoundStatsComponent！"

        # 获取当前回合数，用于仲裁提示生成
        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )

        # 获取最新回合的行动信息，供仲裁提示词扩展使用
        latest_round = self._game.current_dungeon_combat_room.combat.latest_round
        assert latest_round is not None, "仲裁阶段最新回合不应为 None"
        round_action_order = latest_round.action_order
        round_completed_actors = latest_round.completed_actors
        round_current_actor = latest_round.current_actor

        # 生成工具化仲裁提示消息（完整版，供 LLM 首轮使用）
        message = _build_combat_arbitration_tool_prompt(
            actor_entity.name,
            play_cards_action.card,
            play_cards_action.targets,
            current_round_number,
            round_action_order,
            round_completed_actors,
            round_current_actor,
        )

        # 仲裁结果容器：handler 通过 partial 绑定写入，避免闭包。
        ctx = _ArbitrationContext()

        try:
            ok = await agent_loop(
                name=stage_entity.name,
                prompt=message,
                messages=self._game.get_agent_memory(stage_entity).messages,
                tools=[
                    GET_ENTITY_STATS_TOOL,
                    APPLY_DAMAGE_TOOL,
                    SUBMIT_ARBITRATION_TOOL,
                ],
                handlers={
                    GET_ENTITY_STATS_TOOL.function.name: partial(
                        _handle_get_entity_stats, self._game
                    ),
                    APPLY_DAMAGE_TOOL.function.name: partial(
                        _handle_apply_damage, self._game, ctx
                    ),
                    SUBMIT_ARBITRATION_TOOL.function.name: partial(
                        _handle_submit_arbitration, ctx
                    ),
                },
                max_rounds=6,
                tool_choice="required",
                terminal_tools=[SUBMIT_ARBITRATION_TOOL],
            )
        except Exception as e:
            logger.error(f"[PlayCardsArbitrationSystem] agent_loop 异常: {e}")
            return

        if not ok or ctx.combat_log is None or ctx.narrative is None:
            logger.error(
                "[PlayCardsArbitrationSystem] 仲裁未正常完成（未提交结果或达到轮次上限）"
            )
            return

        # 通知覆盖保证：行动者 + 所有目标（去重，行动者可能同时是目标）都必须收到通知。
        # 若 LLM 未对某个实体调用「净伤害工具」（例如其 HP 未变化），则补记其当前 HP，
        # 确保下方统一落库时仍会向其发送「生命值已更新」通知。
        notify_names = list(
            dict.fromkeys([actor_entity.name, *play_cards_action.targets])
        )
        for notify_name in notify_names:
            if notify_name in ctx.hp_changes:
                continue
            entity = self._game.get_actor_entity(notify_name)
            if entity is None:
                logger.error(
                    f"[PlayCardsArbitrationSystem] 无法找到需通知角色: {notify_name}"
                )
                return
            ctx.hp_changes[notify_name] = compute_character_stats(entity).hp

        self._apply_tool_arbitration_result(
            stage_entity,
            actor_entity,
            ctx,
        )

    #######################################################################################################################################
    def _apply_tool_arbitration_result(
        self,
        stage_entity: Entity,
        actor_entity: Entity,
        ctx: _ArbitrationContext,
    ) -> None:
        """应用工具化仲裁结果：更新 HP，广播仲裁事件，写入回合记录。"""

        assert ctx.combat_log is not None, "combat_log 不应为 None"
        assert ctx.narrative is not None, "narrative 不应为 None"
        combat_log = ctx.combat_log
        narrative = ctx.narrative
        hp_changes = ctx.hp_changes

        # 校验 HP 变更中的实体名称（handler 已校验存在，此处兜底防御）
        for entity_name in hp_changes:
            if self._game.get_entity_by_name(entity_name) is None:
                logger.error(
                    f"PlayCardsArbitrationSystem: hp_changes 中的实体不存在于游戏中: {entity_name}"
                )
                return

        # agent_loop 已原地写入完整提示词与工具调用轨迹，这里仅补记干净的结构化结果。
        self._game.add_ai_message(
            entity=stage_entity,
            ai_message=AIMessage(
                content=json.dumps(
                    {
                        "combat_log": combat_log,
                        "narrative": narrative,
                        "unsettled_affixes": ctx.unsettled_affixes,
                    },
                    ensure_ascii=False,
                )
            ),
        )

        # 广播当前回合的仲裁结果
        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )
        self._game.broadcast_to_stage(
            entity=stage_entity,
            agent_event=CombatArbitrationEvent(
                message=_build_combat_arbitration_broadcast(
                    combat_log,
                    narrative,
                    current_round_number,
                    actor_entity.name,
                ),
                stage=stage_entity.name,
                combat_log=combat_log,
                narrative=narrative,
            ),
            exclude_entities={stage_entity},
        )

        # 词缀 telemetry：记录仲裁器无法按计算规则结算的词缀
        for affix in ctx.unsettled_affixes:
            logger.warning(
                f"[PlayCardsArbitrationSystem] 词缀无法按计算规则结算（telemetry）: {affix}"
            )

        # 更新每个受影响实体的 HP 状态
        for entity_name, hp in hp_changes.items():
            entity = self._game.get_entity_by_name(entity_name)
            assert entity is not None, f"无法找到 hp_changes 中的实体: {entity_name}"
            assert entity.has(
                CharacterStatsComponent
            ), f"实体 {entity_name} 缺少 CharacterStatsComponent！"

            old_hp = compute_character_stats(entity).hp
            after_stats = set_character_hp(entity, int(hp))
            new_hp = after_stats.hp
            max_hp = after_stats.max_hp
            logger.info(f"更新 {entity_name} HP: {old_hp} → {new_hp}/{max_hp}")

            self._game.add_human_message(
                entity=entity,
                human_message=HumanMessage(
                    content=_build_stats_update_notification(new_hp, max_hp)
                ),
            )

        # 将本回合的战斗日志和叙事内容添加到当前回合的记录中
        latest_round = self._game.current_dungeon_combat_room.combat.latest_round
        assert latest_round is not None, "current_rounds 不应为 None"
        latest_round.record(RoundEntryKind.CARDS, combat_log, narrative)

    #######################################################################################################################################
