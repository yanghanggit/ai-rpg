"""战斗仲裁动作系统模块。"""

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
    PlayCardsAction,
    RoundEntryKind,
    RoundStatsComponent,
    TargetType,
    render_labeled_str_list,
)
from ..utils import prompt_builder
from .arbitration_common import (
    ArbitrationContext,
    ArbitrationKind,
    build_arbitration_broadcast,
    build_calc_rules_section,
    build_loop_summary_memory,
    build_on_hit_affix_section,
    build_source_section,
    build_stats_update_notification,
    build_tool_flow_section,
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
# 仲裁提示词构建器（play_cards 专属）
###########################################################################################################################################
def _build_spread_sections(card: Card, targets: List[str]) -> str:
    """为 SPREAD 卡牌构建仲裁 prompt 中的专属片段（非 SPREAD 卡返回空串）。

    命中分配由系统预先随机确定，每个 `resolve_damage` 调用的 `hits` 应填该目标
    在此分配中的出现次数。
    """
    if card.target_type != TargetType.SPREAD:
        return ""

    hit_lines = "\n".join(f"  第{i + 1}击 → {t}" for i, t in enumerate(targets))
    return (
        f"\n## 命中分配（系统预先随机确定，共 {card.hit_count} 击）\n\n"
        f"{hit_lines}\n\n"
        f"对每个被命中的不重复目标调用一次 {RESOLVE_DAMAGE_TOOL.function.name}，`hits` 填该目标在上表中的出现次数。"
    )


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
        f"- damage（本卡单次伤害）：{card.damage}",
        f"- hit_count（本卡攻击次数）：{card.hit_count}",
        f"- block（本卡单牌格挡值）：{card.block}",
    ]
    return "\n".join(lines)


@prompt_builder
def _build_play_cards_arbitration_prompt(
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
    spread_hit_assignment = _build_spread_sections(card, targets)

    return f"""# 第 {current_round_number} 回合：战斗结算（工具调用模式）

## 出牌者

{actor_name}

## 本卡数据（本卡 = 本次实际打出的牌）

{_build_card_data_lines(card)}
{spread_hit_assignment}

## 即时词缀（共 {len(card.on_play_affixes)} 条，逐条结算，一条都不能漏）

{render_labeled_str_list("- 即时词缀", card.on_play_affixes, indent="    ")}

即时词缀是逐条独立规则：**逐条全部读取**，判断它如何影响 base 与系数；不得合并、省略，也不引入词缀未提及的新机制。

## 目标

{target_names}

## 回合行动信息（背景信息，不改变结算规则）

{round_action_info}

{build_calc_rules_section(GET_ENTITY_STATS_TOOL.function.name, ArbitrationKind.PLAY_CARDS)}

{build_on_hit_affix_section()}

{build_source_section()}

{build_tool_flow_section(GET_ENTITY_STATS_TOOL.function.name, RESOLVE_DAMAGE_TOOL.function.name, RESOLVE_EFFECT_TOOL.function.name, SUBMIT_ARBITRATION_TOOL.function.name, ArbitrationKind.PLAY_CARDS)}"""


###########################################################################################################################################
# 仲裁工具定义（schema 结构由 arbitration_common 统一，工具级描述各自传入）
###########################################################################################################################################
GET_ENTITY_STATS_TOOL: Final[ToolDefinition] = make_get_entity_stats_tool(
    "读取指定战斗角色的当前生命值（HP/最大HP）与总格挡（其手牌 block 之和）及其手牌中带受击词缀的卡牌（含这些卡牌的 source/damage/hit_count/block 等数据）。用于获取发起者与目标当前状态。"
)


RESOLVE_DAMAGE_TOOL: Final[ToolDefinition] = make_resolve_damage_tool(
    "结算某目标承受的伤害：系统按 max(0, base_damage×damage_mult − 该目标总格挡×block_mult) 逐击计算（共 hits 次）并落库。你只需选定 base 与系数。对每个承伤目标调用一次。"
)


RESOLVE_EFFECT_TOOL: Final[ToolDefinition] = make_resolve_effect_tool(
    "结算某受效角色的反伤 / 吸血 / 治疗（均按每击 ×hits，不过格挡）：系统按「各分量 = 四舍五入(base × 对应系数)」计算净扣减并落库。对每个受效角色调用一次。"
)


SUBMIT_ARBITRATION_TOOL: Final[ToolDefinition] = make_submit_arbitration_tool(
    "提交本次仲裁的最终结果（战斗日志、演出叙事、无法结算的词缀）。调用后本次仲裁结束。"
)


###########################################################################################################################################
# 仲裁工具 handler（核心在 arbitration_common，此处仅绑定出牌专属标签）
###########################################################################################################################################
def _handle_get_entity_stats(game: DBGGame, entity_name: str) -> str:
    """处理「获取状态工具」调用：返回 HP/总格挡 + 参与受击仲裁的手牌卡牌数据。"""
    return get_entity_stats(game, entity_name, on_hit_cards=True)


def _handle_resolve_damage(
    game: DBGGame,
    ctx: ArbitrationContext,
    card: Card,
    actor_name: str,
    entity_name: str,
    base_damage: int,
    hits: int,
    damage_mult: float = 1.0,
    block_mult: float = 1.0,
    rationale: str = "",
) -> str:
    """处理「承伤结算」：绑定出牌者/卡牌标签后交由仲裁公共核心结算。"""
    return resolve_damage(
        game,
        ctx,
        actor_label=f"{actor_name}|{card.name}",
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
    """处理「受效结算」：交由仲裁公共核心结算。"""
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

        await self._run_arbitration(entities[0])

    #######################################################################################################################################
    async def _run_arbitration(self, actor_entity: Entity) -> None:
        """驱动单次出牌的完整仲裁流程。"""

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
        message = _build_play_cards_arbitration_prompt(
            actor_entity.name,
            play_cards_action.card,
            play_cards_action.targets,
            current_round_number,
            round_action_order,
            round_completed_actors,
            round_current_actor,
        )

        # 仲裁结果容器：handler 通过 partial 绑定写入，避免闭包。
        ctx = ArbitrationContext()

        # 本次 loop 的身份标记；结束后据 result 的区间把整段新增记忆压缩为一条总结。
        stage_memory = self._game.get_agent_memory(stage_entity)
        loop_id = (
            f"play_cards:{current_round_number}:"
            f"{actor_entity.name}:{play_cards_action.card.name}"
        )
        loop_start_index = len(stage_memory.messages)

        try:
            result = await agent_loop(
                name=stage_entity.name,
                input_message=message,
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
                        play_cards_action.card,
                        actor_entity.name,
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
            logger.error(f"[PlayCardsArbitrationSystem] agent_loop 异常: {e}")
            # 回滚本次 loop 已追加的记忆，避免失败轨迹污染上下文。
            self._game.replace_span(
                stage_entity, loop_start_index, len(stage_memory.messages), []
            )
            return

        if not result or ctx.narrative is None or ctx.summary is None:
            logger.error(
                "[PlayCardsArbitrationSystem] 仲裁未正常完成（未提交结果或达到轮次上限）"
            )
            # 回滚本次 loop 追加的记忆。
            self._game.replace_span(
                stage_entity, result.start_index, result.end_index, []
            )
            return

        # 成功：把本次 loop 新增的整段记忆（prompt + 工具调用轨迹）压缩为一条「总结 + 数据日志」，
        # 并以 loop_id / loop_id_end 标记该总结，供未来反查（如神器「累计伤害到 X」类玩法）。
        combat_log = "；".join(ctx.segments) if ctx.segments else "本回合无 HP 变化"
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

        # 通知覆盖保证：行动者 + 所有目标（去重，行动者可能同时是目标）都必须收到通知。
        # 若 LLM 未对某个实体调用结算工具（例如其 HP 未变化），则补记其当前 HP，
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

        self._apply_arbitration_result(
            stage_entity,
            actor_entity,
            ctx,
            combat_log,
        )

    #######################################################################################################################################
    def _apply_arbitration_result(
        self,
        stage_entity: Entity,
        actor_entity: Entity,
        ctx: ArbitrationContext,
        combat_log: str,
    ) -> None:
        """应用工具化仲裁结果：更新 HP，广播仲裁事件，写入回合记录。"""

        assert ctx.narrative is not None, "narrative 不应为 None"
        narrative = ctx.narrative
        hp_changes = ctx.hp_changes

        # 校验 HP 变更中的实体名称（handler 已校验存在，此处兜底防御）
        for entity_name in hp_changes:
            if self._game.get_entity_by_name(entity_name) is None:
                logger.error(
                    f"PlayCardsArbitrationSystem: hp_changes 中的实体不存在于游戏中: {entity_name}"
                )
                return

        # 广播当前回合的仲裁结果
        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )
        self._game.broadcast_to_stage(
            entity=stage_entity,
            agent_event=CombatArbitrationEvent(
                message=build_arbitration_broadcast(
                    current_round_number,
                    f"{actor_entity.name} 出牌仲裁",
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
                    content=build_stats_update_notification(new_hp, max_hp)
                ),
            )

        # 将本回合的战斗日志和叙事内容添加到当前回合的记录中
        latest_round = self._game.current_dungeon_combat_room.combat.latest_round
        assert latest_round is not None, "current_rounds 不应为 None"
        latest_round.record(RoundEntryKind.CARDS, combat_log, narrative)

    #######################################################################################################################################
