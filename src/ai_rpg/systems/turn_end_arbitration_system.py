"""回合结束仲裁系统模块。"""

import json
from functools import partial
from typing import Dict, Final, List, Optional, Set, final

from loguru import logger
from overrides import override
from pydantic import BaseModel, Field

from ..deepseek import ToolDefinition, ToolFunction, agent_loop
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_combat_processor import (
    compute_character_stats,
    get_alive_actors_in_stage,
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
    MonsterComponent,
    PartyMemberComponent,
    PassTurnAction,
    StageDescriptionComponent,
)
from ..utils import prompt_builder
from .arbitration_prompt_builders import (
    CALC_RULES_SECTION,
    NARRATIVE_DESCRIPTION,
    build_arbitration_broadcast,
    build_stats_update_notification,
)

###########################################################################################################################################
# 回合结束仲裁提示词构建器
###########################################################################################################################################
TURN_END_AFFIX_RULES: Final[
    str
] = """## 回合结束词缀

你是这些卡牌的持有者，也是本次回合结束结算的仲裁者。每张卡牌的 `source` 是它的来源（生成/注入者名称）；词缀若提及「非 source 者」，指当前持有者（当其不等于该卡牌 source 时）。依各卡牌词缀描述结算，受影响目标由词缀描述与场上存活角色自行判断；持有者自身也可成为目标。不引入词缀未提及的新机制。"""


@prompt_builder
def _build_turn_end_card_lines(card: Card) -> str:
    """输出一张带回合结束词缀的卡参与仲裁的数据字段。"""
    affixes = "、".join(card.on_turn_end_affixes) if card.on_turn_end_affixes else "无"
    source = card.source or "未知"
    return (
        f"- 卡牌：{card.name}\n"
        f"- source（来源/注入者）：{source}\n"
        f"- 叙事（description）：{card.description}\n"
        f"- damage：{card.damage}（单次伤害）\n"
        f"- hit_count：{card.hit_count}（攻击次数）\n"
        f"- block：{card.block}\n"
        f"- 回合结束词缀：{affixes}"
    )


def _build_alive_actor_lines(alive_actor_names: List[str]) -> str:
    """构建场上存活角色列表。"""
    return (
        "\n".join(f"- {name}" for name in alive_actor_names)
        if alive_actor_names
        else "- 无存活角色"
    )


def _camp_label(actor: Entity) -> str:
    """返回角色的阵营标签，帮助 LLM 判断「敌人/友方」目标。"""
    if actor.has(PartyMemberComponent):
        return "远征队"
    if actor.has(MonsterComponent):
        return "怪物"
    return "未知阵营"


@prompt_builder
def _build_turn_end_arbitration_tool_prompt(
    holder_name: str,
    cards: List[Card],
    alive_actor_names: List[str],
    current_round_number: int,
    current_stage_description: str,
) -> str:
    """生成回合结束仲裁提示词（完整版，供 LLM 首轮使用）。"""
    cards_lines = "\n\n".join(_build_turn_end_card_lines(c) for c in cards)
    alive_lines = _build_alive_actor_lines(alive_actor_names)

    return f"""# 第 {current_round_number} 回合：回合结束结算（工具调用模式）

你是 {holder_name}，你正持有以下带回合结束词缀的卡牌；现在是你的回合结束（pass turn）时刻，由你作为仲裁者结算这些词缀的效果。

## 回合结束词缀卡牌

{cards_lines}

## 场上存活角色

{alive_lines}

## 当前场景环境

{current_stage_description}

{CALC_RULES_SECTION}

{TURN_END_AFFIX_RULES}

## 工具使用流程

1. 调用 get_entity_stats 读取「持有者」与所有可能受影响角色的当前属性（可在同一次回复中并发调用多个）。
2. 依据「计算规则」与各卡牌「回合结束词缀」结算，得出每个受影响角色的最终 HP。
3. 对每个受影响角色（含持有者与所有目标）调用 set_entity_hp 写入最终 HP（可在同一次回复中并发调用多个）。
4. 调用 submit_arbitration 提交最终结果，结束本次仲裁。

## submit_arbitration 字段说明

### combat_log（简名 = 全名最后一段）

示例：`[纸人|回合结束·灼烧→英雄:2伤害] HP:英雄 15→13`

{NARRATIVE_DESCRIPTION}"""


@prompt_builder
def _build_condensed_turn_end_arbitration_tool_prompt(
    holder_name: str,
    cards: List[Card],
    alive_actor_names: List[str],
    current_round_number: int,
    current_stage_description: str,
) -> str:
    """生成回合结束仲裁提示词（精简版，写入对话历史减少重复 token）。"""
    cards_lines = "\n\n".join(_build_turn_end_card_lines(c) for c in cards)
    alive_lines = _build_alive_actor_lines(alive_actor_names)

    return f"""# 第 {current_round_number} 回合：回合结束结算（工具调用模式）

你是 {holder_name}（持有者/仲裁者），回合结束时结算下列卡牌的词缀效果。

## 回合结束词缀卡牌

{cards_lines}

## 场上存活角色

{alive_lines}

## 当前场景环境

{current_stage_description}"""


@prompt_builder
def _build_turn_end_arbitration_broadcast(
    combat_log: str, narrative: str, current_round_number: int, holder_name: str
) -> str:
    return build_arbitration_broadcast(
        combat_log,
        narrative,
        current_round_number,
        f"{holder_name} 回合结束仲裁",
    )


###########################################################################################################################################
# 仲裁工具定义（本系统独立定义，与 PlayCardsArbitrationSystem 同名但互不共享）
###########################################################################################################################################
GET_ENTITY_STATS_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="get_entity_stats",
        description="读取指定战斗角色的最终有效属性（HP/最大HP/攻击/防御）。用于获取持有者与目标当前状态。",
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


SET_ENTITY_HP_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="set_entity_hp",
        description="设置指定战斗角色的当前生命值（自动 clamp 到 0~最大HP）。对每个受影响角色（含持有者与所有目标）都必须调用一次。",
        parameters={
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "角色全名",
                },
                "hp": {
                    "type": "integer",
                    "description": "结算后的新生命值（0 ≤ hp ≤ 最大HP）",
                },
            },
            "required": ["entity_name", "hp"],
        },
    )
)


SUBMIT_ARBITRATION_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="submit_arbitration",
        description="提交本次回合结束仲裁的最终结果（战斗日志、演出叙事）。调用后本次仲裁结束。",
        parameters={
            "type": "object",
            "properties": {
                "combat_log": {
                    "type": "string",
                    "description": "战斗数据日志",
                },
                "narrative": {
                    "type": "string",
                    "description": "60-120 字第三人称演出叙事",
                },
            },
            "required": ["combat_log", "narrative"],
        },
    )
)


###########################################################################################################################################
# 仲裁工具 handler
###########################################################################################################################################
class _TurnEndArbitrationContext(BaseModel):
    """单个持有者回合结束仲裁的共享结果容器。"""

    hp_changes: Dict[str, int] = Field(default_factory=dict)
    combat_log: Optional[str] = None
    narrative: Optional[str] = None


def _handle_get_entity_stats(game: DBGGame, entity_name: str) -> str:
    """处理 get_entity_stats 工具调用：返回指定角色的最终有效属性。"""
    entity = game.get_actor_entity(entity_name)
    if entity is None:
        return f"错误：找不到战斗角色 {entity_name}"
    stats = compute_character_stats(entity)
    return (
        f"{entity_name}: HP {stats.hp}/{stats.max_hp} | "
        f"ATK {stats.attack} | DEF {stats.defense}"
    )


def _handle_set_entity_hp(
    game: DBGGame, ctx: _TurnEndArbitrationContext, entity_name: str, hp: int
) -> str:
    """处理 set_entity_hp 工具调用。"""
    entity = game.get_actor_entity(entity_name)
    if entity is None:
        return f"错误：找不到战斗角色 {entity_name}"
    stats = compute_character_stats(entity)
    clamped = max(0, min(int(hp), stats.max_hp))
    ctx.hp_changes[entity_name] = clamped
    return f"{entity_name} HP 将更新为 {clamped}/{stats.max_hp}"


def _handle_submit_arbitration(
    ctx: _TurnEndArbitrationContext,
    combat_log: str,
    narrative: str,
) -> str:
    """处理 submit_arbitration 工具调用。"""
    ctx.combat_log = combat_log
    ctx.narrative = narrative
    return "仲裁结果已提交"


###########################################################################################################################################
@final
class TurnEndArbitrationSystem(ReactiveProcessor):
    """响应 PassTurnAction 事件，对发起 pass turn 的行动者持有回合结束词缀卡牌进行仲裁结算。"""

    def __init__(self, game: DBGGame, use_condensed_prompt: bool = True) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game
        self._use_condensed_prompt: Final[bool] = use_condensed_prompt

    #######################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(PassTurnAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(PassTurnAction)

    #######################################################################################################################################
    def _collect_hand_turn_end_cards(self, entity: Entity) -> List[Card]:
        """收集角色手牌中所有带回合结束词缀的卡牌（持有期间在回合结束时触发）。"""
        hand = entity.get(HandComponent) if entity.has(HandComponent) else None
        if hand is None:
            return []
        return [card for card in hand.cards if card.on_turn_end_affixes]

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("TurnEndArbitrationSystem: 战斗未进行中，跳过回合结束仲裁")
            return

        if not entities:
            return

        # 以 pass turn 实体定位场景；只处理本次发起 pass turn 的行动者（entities）
        pass_turn_entity = entities[0]
        stage_entity = self._game.resolve_stage_entity(pass_turn_entity)
        assert (
            stage_entity is not None
        ), f"TurnEndArbitrationSystem: 无法找到 {pass_turn_entity.name} 所在的场景实体"

        assert stage_entity.has(
            StageDescriptionComponent
        ), "当前场景实体缺少 StageDescriptionComponent 组件！"
        current_stage_description = stage_entity.get(
            StageDescriptionComponent
        ).narrative

        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )

        # 仅处理本次发起 pass turn 的行动者（PassTurnActionSystem 一次只处理一个）
        turn_end_cards = self._collect_hand_turn_end_cards(pass_turn_entity)
        if not turn_end_cards:
            logger.debug(
                "TurnEndArbitrationSystem: 本次 pass turn 的行动者无回合结束词缀卡牌，跳过"
            )
            return

        # 场上存活角色（含阵营标签，供 LLM 判断目标）
        alive_actors = get_alive_actors_in_stage(self._game, pass_turn_entity)
        alive_actor_names = sorted(
            f"{actor.name}（{_camp_label(actor)}）" for actor in alive_actors
        )

        full_prompt = _build_turn_end_arbitration_tool_prompt(
            pass_turn_entity.name,
            turn_end_cards,
            alive_actor_names,
            current_round_number,
            current_stage_description,
        )
        condensed_prompt = (
            _build_condensed_turn_end_arbitration_tool_prompt(
                pass_turn_entity.name,
                turn_end_cards,
                alive_actor_names,
                current_round_number,
                current_stage_description,
            )
            if self._use_condensed_prompt
            else None
        )

        ctx = _TurnEndArbitrationContext()

        try:
            ok = await agent_loop(
                name=pass_turn_entity.name,
                prompt=full_prompt,
                messages=list(self._game.get_agent_memory(pass_turn_entity).messages),
                tools=[
                    GET_ENTITY_STATS_TOOL,
                    SET_ENTITY_HP_TOOL,
                    SUBMIT_ARBITRATION_TOOL,
                ],
                handlers={
                    "get_entity_stats": partial(_handle_get_entity_stats, self._game),
                    "set_entity_hp": partial(_handle_set_entity_hp, self._game, ctx),
                    "submit_arbitration": partial(_handle_submit_arbitration, ctx),
                },
                max_rounds=6,
                tool_choice="auto",
                terminal_tool=SUBMIT_ARBITRATION_TOOL,
            )
        except Exception as e:
            logger.error(
                f"TurnEndArbitrationSystem: [{pass_turn_entity.name}] agent_loop 异常: {e}"
            )
            return

        if not ok or ctx.combat_log is None or ctx.narrative is None:
            logger.error(
                f"TurnEndArbitrationSystem: [{pass_turn_entity.name}] 回合结束仲裁未正常完成，跳过落库"
            )
            return

        self._apply_turn_end_arbitration_result(
            stage_entity,
            pass_turn_entity,
            ctx,
            full_prompt,
            condensed_prompt,
        )

    #######################################################################################################################################
    def _apply_turn_end_arbitration_result(
        self,
        stage_entity: Entity,
        holder: Entity,
        ctx: _TurnEndArbitrationContext,
        full_prompt: str,
        condensed_prompt: Optional[str],
    ) -> None:
        """应用单个持有者的回合结束仲裁结果：写持有者记忆、更新受影响角色 HP、定向广播。"""

        assert ctx.combat_log is not None, "combat_log 不应为 None"
        assert ctx.narrative is not None, "narrative 不应为 None"
        combat_log = ctx.combat_log
        narrative = ctx.narrative
        hp_changes = ctx.hp_changes

        # 校验 HP 变更中的实体名称（handler 已校验存在，此处兜底防御）
        for entity_name in hp_changes:
            if self._game.get_entity_by_name(entity_name) is None:
                logger.error(
                    f"TurnEndArbitrationSystem: hp_changes 中的实体不存在于游戏中: {entity_name}"
                )
                return

        # 仲裁者是持卡人（holder），结果写入 holder 自身记忆，而非 stage。
        if self._use_condensed_prompt and condensed_prompt is not None:
            self._game.add_human_message(
                entity=holder,
                human_message=HumanMessage(
                    content=condensed_prompt,
                    full_prompt=full_prompt,
                ),
            )
        else:
            self._game.add_human_message(
                entity=holder,
                human_message=HumanMessage(content=full_prompt),
            )

        self._game.add_ai_message(
            entity=holder,
            ai_message=AIMessage(
                content=json.dumps(
                    {
                        "combat_log": combat_log,
                        "narrative": narrative,
                    },
                    ensure_ascii=False,
                )
            ),
        )

        # 受影响实体 = 被 LLM 调用 set_entity_hp 的角色（去重）
        affected_entities: Set[Entity] = set()
        for entity_name in hp_changes:
            entity = self._game.get_actor_entity(entity_name)
            if entity is None:
                logger.error(
                    f"TurnEndArbitrationSystem: 无法找到受影响角色: {entity_name}"
                )
                return
            affected_entities.add(entity)

        # 定向广播：只通知受影响实体（不走 broadcast_to_stage 的全场景广播）
        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )
        self._game.notify_entities(
            affected_entities,
            CombatArbitrationEvent(
                message=_build_turn_end_arbitration_broadcast(
                    combat_log,
                    narrative,
                    current_round_number,
                    holder.name,
                ),
                stage=stage_entity.name,
                combat_log=combat_log,
                narrative=narrative,
            ),
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
                    content=build_stats_update_notification(new_hp, max_hp)
                ),
            )

        # 将本回合的战斗日志和叙事内容添加到当前回合的记录中
        latest_round = self._game.current_dungeon_combat_room.combat.latest_round
        assert latest_round is not None, "current_rounds 不应为 None"
        latest_round.cards_combat_log.append(combat_log)
        latest_round.cards_narrative.append(narrative)

    #######################################################################################################################################
