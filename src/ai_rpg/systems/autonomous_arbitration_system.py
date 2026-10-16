"""卡牌自主运行仲裁系统模块。"""

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
from ..game.dbg_combat_processor import (
    compute_character_stats,
    get_alive_monsters_in_stage,
    get_alive_party_members_in_stage,
    set_character_hp,
)
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
    build_on_hit_affix_section,
    build_stats_update_notification,
    build_summary_section,
    build_tool_flow_section,
    collect_hand_cards_with,
    get_entity_stats,
    make_get_entity_stats_tool,
    make_resolve_damage_tool,
    make_resolve_effect_tool,
    make_submit_arbitration_tool,
    resolve_damage,
    resolve_effect,
    submit_arbitration,
)


###########################################################################################################################################
# 自主运行仲裁提示词构建器
###########################################################################################################################################
@prompt_builder
def _build_autonomous_card_lines(card: Card) -> str:
    """输出一张带自主运行词缀的卡参与仲裁的数据字段。"""
    source = card.source or "未知"
    lines = [
        f"- 卡牌：{card.name}",
        f"- source（来源/注入者）：{source}",
        f"- 叙事（description）：{card.description}",
        f"- damage（单卡单次伤害）：{card.damage}",
        f"- hit_count（单卡攻击次数）：{card.hit_count}",
        f"- block（本卡单牌格挡值）：{card.block}",
        render_labeled_str_list(
            "- 自主运行词缀", card.on_autonomous_affixes, indent="    "
        ),
    ]
    return "\n".join(lines)


@prompt_builder
def _build_autonomous_arbitration_tool_prompt(
    holder_name: str,
    cards: List[Card],
    current_round_number: int,
    party_names: str,
    monster_names: str,
) -> str:
    """生成卡牌自主运行仲裁提示词（完整版，供 LLM 首轮使用）。"""
    cards_lines = "\n\n".join(_build_autonomous_card_lines(c) for c in cards)

    return f"""# 第 {current_round_number} 回合：卡牌自主运行结算（工具调用模式）

## 持有者

{holder_name}

{holder_name} 已结束本回合行动（pass turn）。其手牌中带「自主运行词缀」的卡牌在此刻**自主行动一次**：
卡牌作为主体，可影响场上任意角色——攻击敌人、援助我方、或作用于持有者本人。

## 自主运行词缀卡牌

{cards_lines}

## 场上存活

- 队伍方：{party_names}
- 怪物方：{monster_names}

{build_calc_rules_section(GET_ENTITY_STATS_TOOL.function.name, ArbitrationKind.AUTONOMOUS)}

## 目标范围（与回合结束词缀的关键区别）

自主运行词缀**不锁定持有者**：每条词缀的效果目标可以是**场上任意存活角色**（队伍方 / 怪物方 / 持有者本人）。
你必须依词缀文本判定目标——写明「一名随机敌人」「血量最低的敌人」「全体敌人」「一名友方」「持有者」等的词缀，
就按该规则从上方「场上存活」名单中选定 `entity_name`。词缀未写明目标时，按最贴合其文案的解释选取。

{build_on_hit_affix_section(GET_ENTITY_STATS_TOOL.function.name)}

> 补充：本时机的自主伤害同样算「命中」，会触发被命中者的受击词缀；受击词缀的结算对象是本次发起自主行动的持有者 {holder_name}。

## source 字段

`source` = 卡牌来源（生成 / 注入者），空串表示未知；副本保留原 `source`。词缀可据持有者与 `source` 的关系设生效条件：`本卡持有者` 无条件；`source 者` 仅当持有者 == 本卡 `source` 时结算；`非 source 者` 仅当持有者 != 本卡 `source` 时结算；条件不成立则整条跳过。

{build_tool_flow_section(GET_ENTITY_STATS_TOOL.function.name, RESOLVE_DAMAGE_TOOL.function.name, RESOLVE_EFFECT_TOOL.function.name, SUBMIT_ARBITRATION_TOOL.function.name, ArbitrationKind.AUTONOMOUS, holder_name)}

## {SUBMIT_ARBITRATION_TOOL.function.name} 字段说明

{build_narrative_section()}

{build_summary_section()}"""


###########################################################################################################################################
# 仲裁工具定义（schema 结构由 arbitration_common 统一，工具级描述各自传入）
###########################################################################################################################################
GET_ENTITY_STATS_TOOL: Final[ToolDefinition] = make_get_entity_stats_tool(
    "读取指定战斗角色的当前生命值（HP/最大HP）与总格挡（其手牌 block 之和）及其手牌中带受击词缀的卡牌（含这些卡牌的 source/damage/hit_count/block 等数据）。用于获取持有者与自主行动的目标当前状态。"
)


RESOLVE_DAMAGE_TOOL: Final[ToolDefinition] = make_resolve_damage_tool(
    "结算某目标承受的自主伤害：系统按 max(0, base_damage×damage_mult − 该目标总格挡×block_mult) 逐击计算（共 hits 次）并落库。你只需选定 base 与系数。对每个承伤目标调用一次。"
)


RESOLVE_EFFECT_TOOL: Final[ToolDefinition] = make_resolve_effect_tool(
    "结算某受效角色的反伤 / 吸血 / 治疗（均按每击 ×hits，不过格挡）：系统按「各分量 = 四舍五入(base × 对应系数)」计算净扣减并落库。对每个受效角色调用一次。"
)


SUBMIT_ARBITRATION_TOOL: Final[ToolDefinition] = make_submit_arbitration_tool(
    "提交本次卡牌自主运行仲裁的最终结果（战斗日志、演出叙事、无法结算的词缀）。调用后本次仲裁结束。"
)


###########################################################################################################################################
# 仲裁工具 handler（核心在 arbitration_common，此处仅绑定自主运行专属标签）
###########################################################################################################################################
def _handle_get_entity_stats(game: DBGGame, entity_name: str) -> str:
    """处理「获取状态工具」调用：返回 HP/总格挡 + 参与受击仲裁的手牌卡牌数据。"""
    return get_entity_stats(game, entity_name, on_hit_cards=True)


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
    """处理「承伤结算」：绑定持有者标签后交由仲裁公共核心结算；不锁定目标。"""
    return resolve_damage(
        game,
        ctx,
        actor_label=f"{holder_name}|自主运行",
        entity_name=entity_name,
        base_damage=base_damage,
        hits=hits,
        damage_mult=damage_mult,
        block_mult=block_mult,
        rationale=rationale,
    )


def _handle_resolve_effect(
    game: DBGGame,
    ctx: ArbitrationContext,
    entity_name: str,
    base: int,
    hits: int,
    reflect_mult: float = 0.0,
    lifesteal_mult: float = 0.0,
    heal_mult: float = 0.0,
    rationale: str = "",
) -> str:
    """处理「受效结算」：交由仲裁公共核心结算；不锁定目标。"""
    return resolve_effect(
        game,
        ctx,
        entity_name=entity_name,
        base=base,
        hits=hits,
        reflect_mult=reflect_mult,
        lifesteal_mult=lifesteal_mult,
        heal_mult=heal_mult,
        rationale=rationale,
    )


###########################################################################################################################################
@final
class AutonomousArbitrationSystem(ReactiveProcessor):
    """响应 PassTurnAction，在回合结束仲裁之后，由所在场景结算行动者手牌中的自主运行词缀。"""

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
        return entity.has(PassTurnAction) and bool(
            self._collect_hand_autonomous_cards(entity)
        )

    #######################################################################################################################################
    def _collect_hand_autonomous_cards(self, entity: Entity) -> List[Card]:
        """收集角色手牌中所有带自主运行词缀的卡牌（持有期间在 pass turn 后自主触发）。"""
        return collect_hand_cards_with(entity, "on_autonomous_affixes")

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("AutonomousArbitrationSystem: 战斗未进行中，跳过自主运行仲裁")
            return

        if not entities:
            return

        # 以 pass turn 实体定位场景；只处理本次发起 pass turn 的行动者（entities）
        pass_turn_entity = entities[0]
        stage_entity = self._game.resolve_stage_entity(pass_turn_entity)
        assert (
            stage_entity is not None
        ), f"AutonomousArbitrationSystem: 无法找到 {pass_turn_entity.name} 所在的场景实体"

        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )

        autonomous_cards = self._collect_hand_autonomous_cards(pass_turn_entity)
        if not autonomous_cards:
            logger.debug(
                "AutonomousArbitrationSystem: 本次 pass turn 的行动者无自主运行词缀卡牌，跳过"
            )
            return

        # 场上存活阵营（供 agent 选取目标）
        party_members = get_alive_party_members_in_stage(pass_turn_entity, self._game)
        monsters = get_alive_monsters_in_stage(pass_turn_entity, self._game)
        party_names = (
            "、".join(e.name for e in party_members) if party_members else "无"
        )
        monster_names = "、".join(e.name for e in monsters) if monsters else "无"

        prompt = _build_autonomous_arbitration_tool_prompt(
            pass_turn_entity.name,
            autonomous_cards,
            current_round_number,
            party_names,
            monster_names,
        )
        ctx = ArbitrationContext()

        # 本次 loop 的身份标记；结束后据 result 的区间把整段新增记忆压缩为一条总结。
        stage_memory = self._game.get_agent_memory(stage_entity)
        loop_id = f"autonomous:{current_round_number}:{pass_turn_entity.name}"
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
                        _handle_resolve_effect, self._game, ctx
                    ),
                    SUBMIT_ARBITRATION_TOOL.function.name: partial(
                        submit_arbitration, ctx
                    ),
                },
                max_rounds=6,
                tool_choice="required",
                terminal_tools=[SUBMIT_ARBITRATION_TOOL],
                loop_id=loop_id,
            )
        except Exception as e:
            logger.error(
                f"AutonomousArbitrationSystem: [{pass_turn_entity.name}] agent_loop 异常: {e}"
            )
            # 回滚本次 loop 已追加的记忆，避免失败轨迹污染上下文。
            self._game.replace_span(
                stage_entity, loop_start_index, len(stage_memory.messages), []
            )
            return

        if not result or ctx.narrative is None or ctx.summary is None:
            logger.error(
                f"AutonomousArbitrationSystem: [{pass_turn_entity.name}] 自主运行仲裁未正常完成，跳过落库"
            )
            # 回滚本次 loop 追加的记忆。
            self._game.replace_span(
                stage_entity, result.start_index, result.end_index, []
            )
            return

        # 成功：把本次 loop 新增的整段记忆压缩为一条「总结 + 数据日志」，并标记 loop_id。
        combat_log = (
            "；".join(ctx.segments) if ctx.segments else "本次自主运行无 HP 变化"
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

        self._apply_arbitration_result(
            stage_entity,
            pass_turn_entity,
            ctx,
            combat_log,
        )

    #######################################################################################################################################
    def _apply_arbitration_result(
        self,
        stage_entity: Entity,
        holder: Entity,
        ctx: ArbitrationContext,
        combat_log: str,
    ) -> None:
        """应用自主运行仲裁结果：更新受影响角色 HP、全场景广播、写回合记录。"""

        assert ctx.narrative is not None, "narrative 不应为 None"
        narrative = ctx.narrative
        hp_changes = ctx.hp_changes

        # 校验 HP 变更中的实体名称（handler 已校验存在，此处兜底防御）
        for entity_name in hp_changes:
            if self._game.get_entity_by_name(entity_name) is None:
                logger.error(
                    f"AutonomousArbitrationSystem: hp_changes 中的实体不存在于游戏中: {entity_name}"
                )
                return

        # 全场景广播（与出牌 / 回合结束仲裁一致）
        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )
        self._game.broadcast_to_stage(
            entity=stage_entity,
            agent_event=CombatArbitrationEvent(
                message=build_arbitration_broadcast(
                    current_round_number,
                    f"{holder.name} 自主运行仲裁",
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
                f"[AutonomousArbitrationSystem] 词缀无法按计算规则结算（telemetry）: {affix}"
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

        # 将本次自主运行的战斗日志和叙事内容添加到当前回合的记录中
        latest_round = self._game.current_dungeon_combat_room.combat.latest_round
        assert latest_round is not None, "current_rounds 不应为 None"
        latest_round.record(RoundEntryKind.AUTONOMOUS, combat_log, narrative)

    #######################################################################################################################################
