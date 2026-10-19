"""自主运行仲裁系统：由所在场景（stage）结算 pass turn 触发的自主运行词缀（目标可为场上任意角色）。"""

from functools import partial
from typing import Dict, Final, List, final

from loguru import logger
from overrides import override

from ..deepseek import agent_loop
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_combat_processor import (
    get_alive_monsters_in_stage,
    get_alive_party_members_in_stage,
)
from ..game.dbg_game import DBGGame
from ..llm import ToolDefinition
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
    build_on_hit_affix_section,
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

{build_calc_rules_section(GET_ENTITY_STATS_TOOL.function.name, PromptKind.AUTONOMOUS)}

## 目标范围（与回合结束词缀的关键区别）

自主运行词缀**不锁定持有者**：每条词缀的效果目标可以是**场上任意存活角色**（队伍方 / 怪物方 / 持有者本人）。
你必须依词缀文本判定目标——写明「一名随机敌人」「血量最低的敌人」「全体敌人」「一名友方」「持有者」等的词缀，
就按该规则从上方「场上存活」名单中选定 `entity_name`。词缀未写明目标时，按最贴合其文案的解释选取。

{build_on_hit_affix_section()}

> 补充：本时机的自主伤害同样算「命中」，会触发被命中者的受击词缀；受击词缀的结算对象是本次发起自主行动的持有者 {holder_name}。

{build_source_section()}

{build_tool_flow_section(GET_ENTITY_STATS_TOOL.function.name, RESOLVE_DAMAGE_TOOL.function.name, RESOLVE_EFFECT_TOOL.function.name, SUBMIT_ARBITRATION_TOOL.function.name, PromptKind.AUTONOMOUS, holder_name)}"""


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

        # 以 pass turn 实体定位场景；只处理本次发起 pass turn 的行动者
        # （PassTurnActionSystem 保证每帧只有一个过牌动作实体）。
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

        # 以 stage 实体为仲裁者：直接使用其持久记忆，prompt / 工具轨迹 / 结果都写入其记忆。
        stage_memory = self._game.get_agent_memory(stage_entity)
        assert stage_memory.messages, "场景实体缺少首条 SystemMessage"

        # 本次 loop 的身份标记；结束后据 loop_start_index 把整段新增记忆压缩为一条总结。
        loop_id = make_loop_id(
            stage_memory.messages,
            "autonomous",
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
            record_aborted_loop(
                self._game,
                stage_entity,
                kind=RoundKind.AUTONOMOUS,
                loop_id=loop_id,
                reason=f"agent_loop 异常：{e}",
            )
            return

        if not result:
            logger.error(
                f"AutonomousArbitrationSystem: [{pass_turn_entity.name}] 自主运行仲裁未正常完成，跳过落库"
            )
            record_aborted_loop(
                self._game,
                stage_entity,
                kind=RoundKind.AUTONOMOUS,
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
            else build_empty_combat_log(RoundKind.AUTONOMOUS)
        )

        apply_arbitration_result(
            self._game,
            stage_entity,
            ctx,
            kind=RoundKind.AUTONOMOUS,
            title_label=f"{pass_turn_entity.name} 自主运行仲裁",
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
