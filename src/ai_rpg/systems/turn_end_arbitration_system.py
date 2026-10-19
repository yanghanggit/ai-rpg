"""回合结束仲裁系统：由所在场景（stage）结算本次 pass turn 的持有者手牌中带回合结束词缀的卡牌。"""

from functools import partial
from typing import Dict, Final, List, final

from loguru import logger
from overrides import override

from ..deepseek import (
    ToolDefinition,
    agent_loop,
)
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    Card,
    PassTurnAction,
    render_labeled_str_list,
)
from ..utils import prompt_builder
from .arbitration_common import (
    ArbitrationContext,
    PromptKind,
    RoundKind,
    apply_arbitration_result,
    build_calc_rules_section,
    build_empty_combat_log,
    build_source_section,
    build_tool_flow_section,
    collect_hand_cards_with,
    compress_loop_to_summary,
    get_entity_stats,
    make_get_entity_stats_tool,
    make_loop_id,
    make_resolve_damage_tool,
    make_resolve_effect_tool,
    make_submit_arbitration_tool,
    record_aborted_loop,
    resolve_damage,
    resolve_effect,
    submit_arbitration,
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
def _build_turn_end_arbitration_prompt(
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

{build_calc_rules_section(GET_ENTITY_STATS_TOOL.function.name, PromptKind.TURN_END)}

回合结束词缀是逐条独立规则：逐条全部读取，不得合并、省略或引入词缀外机制。

{build_source_section()}

{build_tool_flow_section(GET_ENTITY_STATS_TOOL.function.name, RESOLVE_DAMAGE_TOOL.function.name, RESOLVE_EFFECT_TOOL.function.name, SUBMIT_ARBITRATION_TOOL.function.name, PromptKind.TURN_END, holder_name)}"""


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
def _handle_get_entity_stats(game: DBGGame, entity_name: str) -> str:
    """处理「获取状态工具」调用：返回 HP/总格挡。"""
    return get_entity_stats(game, entity_name)


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
    return resolve_damage(
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

        # 一次只处理发起 pass turn 的那个行动者：PassTurnActionSystem 保证每帧只有一个
        # 过牌动作实体（其 react 里有 len(entities) == 1 的断言）。
        await self._run_arbitration(entities[0])

    #######################################################################################################################################
    async def _run_arbitration(self, pass_turn_entity: Entity) -> None:
        """驱动单个持有者的完整回合结束仲裁流程。"""

        # 以 pass turn 实体定位场景
        stage_entity = self._game.resolve_stage_entity(pass_turn_entity)
        assert (
            stage_entity is not None
        ), f"TurnEndArbitrationSystem: 无法找到 {pass_turn_entity.name} 所在的场景实体"

        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )

        turn_end_cards = self._collect_hand_turn_end_cards(pass_turn_entity)
        if not turn_end_cards:
            logger.debug(
                "TurnEndArbitrationSystem: 本次 pass turn 的行动者无回合结束词缀卡牌，跳过"
            )
            return

        prompt = _build_turn_end_arbitration_prompt(
            pass_turn_entity.name,
            turn_end_cards,
            current_round_number,
        )
        ctx = ArbitrationContext()

        # 以 stage 实体为仲裁者：直接使用其持久记忆，prompt / 工具轨迹 / 结果都写入其记忆。
        stage_memory = self._game.get_agent_memory(stage_entity)
        assert stage_memory.messages, "场景实体缺少首条 SystemMessage"

        # 本次 loop 的身份标记；结束后据 loop_start_index 把整段新增记忆压缩为一条总结。
        loop_id = make_loop_id(
            stage_memory.messages,
            "turn_end",
            current_round_number,
            pass_turn_entity.name,
        )
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
                f"TurnEndArbitrationSystem: [{pass_turn_entity.name}] agent_loop 异常: {e}"
            )
            record_aborted_loop(
                self._game,
                stage_entity,
                kind=RoundKind.TURN_END,
                loop_id=loop_id,
                reason=f"agent_loop 异常：{e}",
            )
            return

        if not result:
            logger.error(
                f"TurnEndArbitrationSystem: [{pass_turn_entity.name}] 回合结束仲裁未正常完成，跳过落库"
            )
            record_aborted_loop(
                self._game,
                stage_entity,
                kind=RoundKind.TURN_END,
                loop_id=loop_id,
                reason="模型未在轮次上限内提交结算结果（未调用 submit_arbitration）",
            )
            return

        # 仅类型收窄：submit 成功即已写入。
        assert ctx.narrative is not None, "submit 成功时 narrative 必定存在"
        assert ctx.summary is not None, "submit 成功时 summary 必定存在"

        combat_log = (
            "；".join(ctx.segments)
            if ctx.segments
            else build_empty_combat_log(RoundKind.TURN_END)
        )

        apply_arbitration_result(
            self._game,
            stage_entity,
            ctx,
            kind=RoundKind.TURN_END,
            title_label=f"{pass_turn_entity.name} 回合结束仲裁",
            combat_log=combat_log,
        )

        compress_loop_to_summary(
            self._game,
            stage_entity,
            loop_start_index,
            summary=ctx.summary,
            combat_log=combat_log,
            loop_id=loop_id,
        )

    #######################################################################################################################################
