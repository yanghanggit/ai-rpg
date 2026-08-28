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
    collect_hand_on_hit_cards,
    compute_character_stats,
    set_character_hp,
)
from ..game.dbg_game import DBGGame
from ..models import (
    AIMessage,
    Card,
    CharacterStatsComponent,
    CombatArbitrationEvent,
    GearItem,
    HumanMessage,
    PlayCardsAction,
    RoundStatsComponent,
    StageDescriptionComponent,
    TargetType,
)
from ..utils import prompt_builder
from .arbitration_prompt_builders import (
    CALC_RULES_SECTION,
    NARRATIVE_DESCRIPTION,
    STAGE_DESCRIPTION_DESCRIPTION,
    build_arbitration_broadcast,
    build_instant_affix_section,
    build_stats_update_notification,
)

###########################################################################################################################################
# 仲裁提示词构建器（play_cards 专属）
###########################################################################################################################################
ON_HIT_AFFIX_RULES: Final[
    str
] = """## 受击词缀

get_entity_stats 返回的「受击词缀」仅在**该实体是本次出牌的目标**时触发；出牌者自身的受击词缀不触发（除非出牌者也同时是目标）。依词缀描述结算（如 [反伤] 对出牌者造成伤害），不引入词缀未提及的新机制。"""


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
        f"按上方命中分配逐段结算，final_stats 须包含**所有被命中过的不重复目标**。"
    )
    log_example = "\nspread 示例：`[英雄|回旋镖→随机:3×3段,敌A×2伤害5,敌B×1伤害3] HP:敌A 15→10 敌B 12→9`"
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
def _build_gear_play_section(gear_item: GearItem | None) -> str:
    """构建出牌者装备段落（含装备即时词缀）；无装备时返回空字符串。"""
    if gear_item is None:
        return ""
    section = (
        f"\n\n## 出牌者装备\n\n"
        f"- 名称：{gear_item.name}\n"
        f"- 描述：{gear_item.description}"
    )
    return section + build_instant_affix_section(
        "装备即时词缀", gear_item.on_play_affixes
    )


@prompt_builder
def _build_card_data_lines(card: Card) -> str:
    """输出一张卡参与仲裁的全部数据字段（出牌侧：含即时词缀，排除系统管理字段）。"""
    on_play = "、".join(card.on_play_affixes) if card.on_play_affixes else "无"
    return (
        f"- 卡牌：{card.name}\n"
        f"- 叙事（description）：{card.description}\n"
        f"- cost：{card.cost}\n"
        f"- damage：{card.damage}（单次伤害）\n"
        f"- hit_count：{card.hit_count}（攻击次数）\n"
        f"- block：{card.block}\n"
        f"- 即时词缀：{on_play}"
    )


@prompt_builder
def _build_combat_arbitration_tool_prompt(
    actor_name: str,
    card: Card,
    targets: List[str],
    current_round_number: int,
    current_stage_description: str,
    gear_item: GearItem | None = None,
    action_order: List[str] | None = None,
    completed_actors: List[str] | None = None,
    current_actor: str | None = None,
) -> str:
    unique_targets = list(dict.fromkeys(targets))
    target_names = "、".join(unique_targets) if unique_targets else "无"
    round_action_info = _build_round_action_info_lines(
        action_order, completed_actors, current_actor
    )
    spread = _build_spread_sections(card, targets)

    return f"""# 第 {current_round_number} 回合：战斗结算（工具调用模式）

## 出牌者

{actor_name}

## 出牌

{_build_card_data_lines(card)}
{spread.hit_assignment}{_build_gear_play_section(gear_item)}

## 目标

{target_names}

## 当前场景环境

{current_stage_description}

## 回合行动信息（背景信息，不改变结算规则）

{round_action_info}

{CALC_RULES_SECTION}

{ON_HIT_AFFIX_RULES}

## 工具使用流程

1. 调用 get_entity_stats 读取「出牌者」与所有「目标」的当前属性与受击词缀（可在同一次回复中并发调用多个）。
2. 依据「计算规则」结算，得出每个受影响角色的最终 HP。
3. 对每个受影响角色（含出牌者与所有目标）调用 set_entity_hp 写入最终 HP（可在同一次回复中并发调用多个）。
4. 调用 submit_arbitration 提交最终结果，结束本次仲裁。

## submit_arbitration 字段说明

### combat_log（简名 = 全名最后一段）

正常：`[出牌者简名|卡牌→目标:damage Xx击_count次,伤害Z] HP:目标简名 旧→新`
多段示例：`[英雄|回旋镖→石缝蜥:3x3次,伤害7] HP:石缝蜥 15→8`{spread.log_example}
阵亡跳过：`[出牌者简名|已阵亡，卡牌无法执行]`

{NARRATIVE_DESCRIPTION}

{STAGE_DESCRIPTION_DESCRIPTION}"""


@prompt_builder
def _build_condensed_combat_arbitration_tool_prompt(
    actor_name: str,
    card: Card,
    targets: List[str],
    current_round_number: int,
    current_stage_description: str,
    gear_item: GearItem | None = None,
    action_order: List[str] | None = None,
    completed_actors: List[str] | None = None,
    current_actor: str | None = None,
) -> str:
    """精简版工具化仲裁提示词，省略静态规则与工具流程说明，用于写入对话历史减少重复 token。"""
    unique_targets = list(dict.fromkeys(targets))
    target_names = "、".join(unique_targets) if unique_targets else "无"
    round_action_info = _build_round_action_info_lines(
        action_order, completed_actors, current_actor
    )
    spread = _build_spread_sections(card, targets)

    return f"""# 第 {current_round_number} 回合：战斗结算（工具调用模式）

## 出牌者

{actor_name}

## 出牌

{_build_card_data_lines(card)}
{spread.hit_assignment}{_build_gear_play_section(gear_item)}

## 目标

{target_names}

## 当前场景环境

{current_stage_description}

## 回合行动信息（背景信息，不改变结算规则）

{round_action_info}"""


@prompt_builder
def _build_combat_arbitration_broadcast(
    combat_log: str, narrative: str, current_round_number: int, actor_name: str
) -> str:
    return build_arbitration_broadcast(
        combat_log,
        narrative,
        current_round_number,
        f"{actor_name} 出牌仲裁",
    )


###########################################################################################################################################
# 仲裁工具定义
###########################################################################################################################################
GET_ENTITY_STATS_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="get_entity_stats",
        description="读取指定战斗角色的最终有效属性（HP/最大HP/攻击/防御）与其手牌中带受击词缀的卡牌（含这些卡牌的 damage/hit_count/block 等数据）。用于获取发起者与目标当前状态。",
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
        description="设置指定战斗角色的当前生命值（自动 clamp 到 0~最大HP）。对每个受影响角色（含发起者与所有目标）都必须调用一次。",
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
        description="提交本次仲裁的最终结果（战斗日志、演出叙事、场景环境快照）。调用后本次仲裁结束。",
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
                "stage_description": {
                    "type": "string",
                    "description": "仲裁后的场景环境快照",
                },
            },
            "required": ["combat_log", "narrative", "stage_description"],
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
    stage_description: Optional[str] = None


def _handle_get_entity_stats(game: DBGGame, entity_name: str) -> str:
    """处理 get_entity_stats 工具调用：返回 stats + 参与受击仲裁的手牌卡牌数据。"""
    entity = game.get_actor_entity(entity_name)
    if entity is None:
        return f"错误：找不到战斗角色 {entity_name}"
    stats = compute_character_stats(entity)
    hit_cards = collect_hand_on_hit_cards(entity)
    if hit_cards:
        cards_str = "；".join(
            f"{c.name}(description={c.description}, cost={c.cost}, damage={c.damage}, "
            f"hit_count={c.hit_count}, block={c.block}, 受击词缀={c.on_hit_affixes})"
            for c in hit_cards
        )
    else:
        cards_str = "无"
    return (
        f"{entity_name}: HP {stats.hp}/{stats.max_hp} | "
        f"ATK {stats.attack} | DEF {stats.defense} | "
        f"受击卡牌: {cards_str}"
    )


def _handle_set_entity_hp(
    game: DBGGame, ctx: _ArbitrationContext, entity_name: str, hp: int
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
    ctx: _ArbitrationContext,
    combat_log: str,
    narrative: str,
    stage_description: str,
) -> str:
    """处理 submit_arbitration 工具调用。"""
    ctx.combat_log = combat_log
    ctx.narrative = narrative
    ctx.stage_description = stage_description
    return "仲裁结果已提交"


###########################################################################################################################################
@final
class PlayCardsArbitrationSystem(ReactiveProcessor):
    """响应 PlayCardsAction 事件，对单张出牌立即进行 AI 仲裁结算（工具调用模式）。"""

    def __init__(self, game: DBGGame, use_condensed_prompt: bool = True) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game
        self._use_condensed_prompt: Final[bool] = use_condensed_prompt

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

        assert stage_entity.has(
            StageDescriptionComponent
        ), "当前场景实体缺少 StageDescriptionComponent 组件！"
        current_stage_description = stage_entity.get(
            StageDescriptionComponent
        ).narrative

        # 生成工具化仲裁提示消息（完整版，供 LLM 首轮使用）
        message = _build_combat_arbitration_tool_prompt(
            actor_entity.name,
            play_cards_action.card,
            play_cards_action.targets,
            current_round_number,
            current_stage_description,
            play_cards_action.gear_item,
            round_action_order,
            round_completed_actors,
            round_current_actor,
        )

        # 生成精简后的仲裁提示消息（写入对话历史）
        condensed_message = (
            _build_condensed_combat_arbitration_tool_prompt(
                actor_entity.name,
                play_cards_action.card,
                play_cards_action.targets,
                current_round_number,
                current_stage_description,
                play_cards_action.gear_item,
                round_action_order,
                round_completed_actors,
                round_current_actor,
            )
            if self._use_condensed_prompt
            else None
        )

        # 仲裁结果容器：handler 通过 partial 绑定写入，避免闭包。
        ctx = _ArbitrationContext()

        # agent_loop 会原地追加消息，因此传入副本，避免工具调用痕迹污染持久记忆。
        messages = list(self._game.get_agent_memory(stage_entity).messages)

        try:
            ok = await agent_loop(
                name=stage_entity.name,
                prompt=message,
                messages=messages,
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
            logger.error(f"[PlayCardsArbitrationSystem] agent_loop 异常: {e}")
            return

        if (
            not ok
            or ctx.combat_log is None
            or ctx.narrative is None
            or ctx.stage_description is None
        ):
            logger.error(
                "[PlayCardsArbitrationSystem] 仲裁未正常完成（未提交结果或达到轮次上限）"
            )
            return

        # 通知覆盖保证：行动者 + 所有目标（去重，行动者可能同时是目标）都必须收到通知。
        # 若 LLM 未对某个实体调用 set_entity_hp（例如其 HP 未变化），则补记其当前 HP，
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
            message,
            condensed_message,
        )

    #######################################################################################################################################
    def _apply_tool_arbitration_result(
        self,
        stage_entity: Entity,
        actor_entity: Entity,
        ctx: _ArbitrationContext,
        full_prompt: str,
        condensed_prompt: Optional[str],
    ) -> None:
        """应用工具化仲裁结果：更新 HP，广播仲裁事件，写入回合记录。"""

        assert ctx.combat_log is not None, "combat_log 不应为 None"
        assert ctx.narrative is not None, "narrative 不应为 None"
        assert ctx.stage_description is not None, "stage_description 不应为 None"
        combat_log = ctx.combat_log
        narrative = ctx.narrative
        stage_description = ctx.stage_description
        hp_changes = ctx.hp_changes

        # 校验 HP 变更中的实体名称（handler 已校验存在，此处兜底防御）
        for entity_name in hp_changes:
            if self._game.get_entity_by_name(entity_name) is None:
                logger.error(
                    f"PlayCardsArbitrationSystem: hp_changes 中的实体不存在于游戏中: {entity_name}"
                )
                return

        # 仲裁者（combat stage）更新自身场景环境快照
        if stage_description.strip():
            stage_entity.replace(
                StageDescriptionComponent,
                stage_entity.name,
                stage_description,
            )

        # 根据是否使用精简提示，添加消息。
        if self._use_condensed_prompt and condensed_prompt is not None:
            self._game.add_human_message(
                entity=stage_entity,
                human_message=HumanMessage(
                    content=condensed_prompt,
                    full_prompt=full_prompt,
                ),
            )
        else:
            self._game.add_human_message(
                entity=stage_entity,
                human_message=HumanMessage(content=full_prompt),
            )

        # 将 AI 的最终结果写入对话历史（等价于旧流程的 response_ai_message）
        self._game.add_ai_message(
            entity=stage_entity,
            ai_message=AIMessage(
                content=json.dumps(
                    {
                        "combat_log": combat_log,
                        "narrative": narrative,
                        "stage_description": stage_description,
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
