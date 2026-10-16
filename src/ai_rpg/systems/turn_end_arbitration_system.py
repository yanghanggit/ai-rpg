"""回合结束仲裁系统模块。

仲裁者与出牌仲裁一致：由**所在场景（stage）**担任，结果写入 stage 记忆并全场景广播；
被结算的是发起 pass turn 的行动者（持有者）手牌中带回合结束词缀的卡牌。
"""

from functools import partial
from typing import Dict, Final, List, final

from loguru import logger
from overrides import override

from ..deepseek import (
    LOOP_END_ATTR,
    LOOP_ID_ATTR,
    ToolDefinition,
    agent_loop,
)
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_combat_processor import compute_character_stats, set_character_hp
from ..game.dbg_game import DBGGame
from ..game.rpg_agent_memory import REPLACED_MESSAGES_ATTR
from ..models import (
    Card,
    CharacterStatsComponent,
    CombatArbitrationEvent,
    HumanMessage,
    PassTurnAction,
    RoundEntryKind,
    render_labeled_str_list,
)
from ..utils import prompt_builder
from .arbitration_common import (
    ArbitrationContext,
    ArbitrationKind,
    build_arbitration_broadcast,
    build_calc_rules_section,
    build_loop_summary_memory,
    build_narrative_section,
    build_stats_update_notification,
    build_summary_section,
    build_tool_flow_section,
    collect_hand_cards_with,
    get_entity_stats_result,
    handle_submit_arbitration,
    make_get_entity_stats_tool,
    make_resolve_damage_tool,
    make_resolve_effect_tool,
    make_submit_arbitration_tool,
    resolve_damage_core,
    resolve_effect_core,
)


###########################################################################################################################################
# 回合结束仲裁提示词构建器
###########################################################################################################################################
@prompt_builder
def _build_turn_end_card_lines(card: Card) -> str:
    """输出一张带回合结束词缀的卡参与仲裁的数据字段。"""
    source = card.source or "未知"
    lines = [
        f"- 卡牌：{card.name}",
        f"- source（来源/注入者）：{source}",
        f"- 叙事（description）：{card.description}",
        f"- damage（单卡单次伤害）：{card.damage}",
        f"- hit_count（单卡攻击次数）：{card.hit_count}",
        f"- block（本卡单牌格挡值）：{card.block}",
        render_labeled_str_list(
            "- 回合结束词缀", card.on_turn_end_affixes, indent="    "
        ),
    ]
    return "\n".join(lines)


@prompt_builder
def _build_turn_end_arbitration_tool_prompt(
    holder_name: str,
    cards: List[Card],
    current_round_number: int,
) -> str:
    """生成回合结束仲裁提示词（完整版，供 LLM 首轮使用）。"""
    cards_lines = "\n\n".join(_build_turn_end_card_lines(c) for c in cards)

    return f"""# 第 {current_round_number} 回合：回合结束结算（工具调用模式）

## 回合结束的持有者

{holder_name}

其回合结束（pass turn）时，由你结算以下带回合结束词缀的卡牌的效果；**这些效果的目标恒为持有者本人 {holder_name}**。

## 回合结束词缀卡牌

{cards_lines}

{build_calc_rules_section(GET_ENTITY_STATS_TOOL.function.name, ArbitrationKind.TURN_END)}

## 回合结束词缀

{holder_name} 是这些卡牌的持有者；每张卡的 `source` 是它的来源（生成 / 注入者），副本保留原 `source`。词缀的生效条件按持有者与 `source` 的关系判定：`本卡持有者` 无条件（效果落在 {holder_name}）；`source 者` 仅当 {holder_name} == 该卡 `source` 时结算；`非 source 者` 仅当 {holder_name} != 该卡 `source` 时结算；条件不成立则整条跳过。回合结束词缀是逐条独立规则：**逐条全部读取**，判断它为哪些系数取值，用于后续判定；**所有效果只作用于持有者 {holder_name} 本人**，不得指向其他角色，不得合并、省略或引入词缀外机制。

{build_tool_flow_section(GET_ENTITY_STATS_TOOL.function.name, RESOLVE_DAMAGE_TOOL.function.name, RESOLVE_EFFECT_TOOL.function.name, SUBMIT_ARBITRATION_TOOL.function.name, ArbitrationKind.TURN_END, holder_name)}

## {SUBMIT_ARBITRATION_TOOL.function.name} 字段说明

{build_narrative_section()}

{build_summary_section()}"""


###########################################################################################################################################
# 仲裁工具定义（schema 结构由 arbitration_common 统一，工具级描述各自传入）
###########################################################################################################################################
GET_ENTITY_STATS_TOOL: Final[ToolDefinition] = make_get_entity_stats_tool(
    "读取指定战斗角色的当前生命值（HP/最大HP）与总格挡（其手牌 block 之和）。用于获取持有者当前状态。"
)


RESOLVE_DAMAGE_TOOL: Final[ToolDefinition] = make_resolve_damage_tool(
    "结算持有者承受的伤害：系统按 max(0, base_damage×damage_mult − 持有者总格挡×block_mult) 逐击计算（共 hits 次）并落库。你只需选定 base 与系数。对持有者调用一次；目标恒为持有者本人。"
)


RESOLVE_EFFECT_TOOL: Final[ToolDefinition] = make_resolve_effect_tool(
    "结算持有者的反伤 / 吸血 / 治疗（均按每击 ×hits，不过格挡）：系统按「各分量 = 四舍五入(base × 对应系数)」计算净扣减并落库。对持有者调用一次；目标恒为持有者本人。"
)


SUBMIT_ARBITRATION_TOOL: Final[ToolDefinition] = make_submit_arbitration_tool(
    "提交本次回合结束仲裁的最终结果（战斗日志、演出叙事、无法结算的词缀）。调用后本次仲裁结束。"
)


###########################################################################################################################################
# 仲裁工具 handler（核心在 arbitration_common，此处仅绑定回合结束专属标签 / 目标约束）
###########################################################################################################################################
# 兼容别名：回合结束仲裁历史上使用独立的 context 类名
_TurnEndArbitrationContext = ArbitrationContext


def _handle_get_entity_stats(game: DBGGame, entity_name: str) -> str:
    """处理「获取状态工具」调用：返回 HP/总格挡。"""
    return get_entity_stats_result(game, entity_name)


def _handle_resolve_damage(
    game: DBGGame,
    ctx: ArbitrationContext,
    holder_name: str,
    entity_name: str,
    base_damage: int,
    hits: int,
    damage_mult: float = 1.0,
    block_mult: float = 1.0,
    rationale: str = "",
) -> str:
    """处理「承伤结算」：目标恒为持有者，交由仲裁公共核心结算。"""
    return resolve_damage_core(
        game,
        ctx,
        actor_label=holder_name,
        entity_name=entity_name,
        base_damage=base_damage,
        hits=hits,
        damage_mult=damage_mult,
        block_mult=block_mult,
        rationale=rationale,
        require_entity=holder_name,
    )


def _handle_resolve_effect(
    game: DBGGame,
    ctx: ArbitrationContext,
    holder_name: str,
    entity_name: str,
    base: int,
    hits: int,
    reflect_mult: float = 0.0,
    lifesteal_mult: float = 0.0,
    heal_mult: float = 0.0,
    rationale: str = "",
) -> str:
    """处理「受效结算」：目标恒为持有者，交由仲裁公共核心结算。"""
    return resolve_effect_core(
        game,
        ctx,
        entity_name=entity_name,
        base=base,
        hits=hits,
        reflect_mult=reflect_mult,
        lifesteal_mult=lifesteal_mult,
        heal_mult=heal_mult,
        rationale=rationale,
        require_entity=holder_name,
    )


###########################################################################################################################################
@final
class TurnEndArbitrationSystem(ReactiveProcessor):
    """响应 PassTurnAction，由所在场景（stage）仲裁行动者手牌中的回合结束词缀。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

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
        return collect_hand_cards_with(entity, "on_turn_end_affixes")

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

        prompt = _build_turn_end_arbitration_tool_prompt(
            pass_turn_entity.name,
            turn_end_cards,
            current_round_number,
        )
        ctx = ArbitrationContext()

        # 本次 loop 的身份标记；结束后据 result 的区间把整段新增记忆压缩为一条总结。
        stage_memory = self._game.get_agent_memory(stage_entity)
        loop_id = f"turn_end:{current_round_number}:{pass_turn_entity.name}"
        loop_start_index = len(stage_memory.messages)

        try:
            result = await agent_loop(
                name=stage_entity.name,
                input_message=prompt,
                messages=stage_memory.messages,
                tools=[
                    GET_ENTITY_STATS_TOOL,
                    RESOLVE_DAMAGE_TOOL,
                    RESOLVE_EFFECT_TOOL,
                    SUBMIT_ARBITRATION_TOOL,
                ],
                handlers={
                    GET_ENTITY_STATS_TOOL.function.name: partial(
                        _handle_get_entity_stats, self._game
                    ),
                    RESOLVE_DAMAGE_TOOL.function.name: partial(
                        _handle_resolve_damage,
                        self._game,
                        ctx,
                        pass_turn_entity.name,
                    ),
                    RESOLVE_EFFECT_TOOL.function.name: partial(
                        _handle_resolve_effect,
                        self._game,
                        ctx,
                        pass_turn_entity.name,
                    ),
                    SUBMIT_ARBITRATION_TOOL.function.name: partial(
                        handle_submit_arbitration, ctx
                    ),
                },
                max_rounds=6,
                tool_choice="required",
                terminal_tools=[SUBMIT_ARBITRATION_TOOL],
                loop_id=loop_id,
            )
        except Exception as e:
            logger.error(
                f"TurnEndArbitrationSystem: [{pass_turn_entity.name}] agent_loop 异常: {e}"
            )
            # 回滚本次 loop 已追加的记忆，避免失败轨迹污染上下文。
            self._game.replace_span(
                stage_entity, loop_start_index, len(stage_memory.messages), []
            )
            return

        if not result or ctx.narrative is None or ctx.summary is None:
            logger.error(
                f"TurnEndArbitrationSystem: [{pass_turn_entity.name}] 回合结束仲裁未正常完成，跳过落库"
            )
            # 回滚本次 loop 追加的记忆。
            self._game.replace_span(
                stage_entity, result.start_index, result.end_index, []
            )
            return

        # 成功：把本次 loop 新增的整段记忆压缩为一条「总结 + 数据日志」，并标记 loop_id。
        combat_log = (
            "；".join(ctx.segments) if ctx.segments else "本次回合结束无 HP 变化"
        )
        self._game.replace_span(
            stage_entity,
            result.start_index,
            result.end_index,
            [
                HumanMessage(
                    content=build_loop_summary_memory(ctx.summary, combat_log),
                    **{LOOP_ID_ATTR: loop_id, LOOP_END_ATTR: loop_id},
                )
            ],
            dump_attr=REPLACED_MESSAGES_ATTR,
        )

        self._apply_turn_end_arbitration_result(
            stage_entity,
            pass_turn_entity,
            ctx,
            combat_log,
        )

    #######################################################################################################################################
    def _apply_turn_end_arbitration_result(
        self,
        stage_entity: Entity,
        holder: Entity,
        ctx: ArbitrationContext,
        combat_log: str,
    ) -> None:
        """应用单个持有者的回合结束仲裁结果：更新受影响角色 HP、全场景广播、写回合记录。"""

        assert ctx.narrative is not None, "narrative 不应为 None"
        narrative = ctx.narrative
        hp_changes = ctx.hp_changes

        # 校验 HP 变更中的实体名称（handler 已校验存在，此处兜底防御）
        for entity_name in hp_changes:
            if self._game.get_entity_by_name(entity_name) is None:
                logger.error(
                    f"TurnEndArbitrationSystem: hp_changes 中的实体不存在于游戏中: {entity_name}"
                )
                return

        # 全场景广播（与出牌仲裁一致）：除受影响角色外，持有者与旁观者也需知道回合结束
        # 发生了什么——持有者自身 HP 未必变化（如只伤害对手的词缀）。
        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )
        self._game.broadcast_to_stage(
            entity=stage_entity,
            agent_event=CombatArbitrationEvent(
                message=build_arbitration_broadcast(
                    current_round_number,
                    f"{holder.name} 回合结束仲裁",
                    narrative,
                    combat_log,
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
                f"[TurnEndArbitrationSystem] 词缀无法按计算规则结算（telemetry）: {affix}"
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
        latest_round.record(RoundEntryKind.CARDS, combat_log, narrative)

    #######################################################################################################################################
