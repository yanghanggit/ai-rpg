"""神器·出牌后仲裁系统：出牌/消耗品仲裁后，由所在场景（stage）结算其自身及存活角色携带的神器修正规则。"""

from functools import partial
from typing import Dict, Final, List, Tuple, final

from loguru import logger
from overrides import override

from ..deepseek import (
    LOOP_END_ATTR,
    LOOP_ID_ATTR,
    ToolDefinition,
    ToolFunction,
    agent_loop,
)
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_combat_processor import (
    compute_character_stats,
    get_alive_actors_in_stage,
    get_alive_monsters_in_stage,
    get_alive_party_members_in_stage,
    set_character_hp,
)
from ..game.dbg_game import DBGGame
from ..game.rpg_agent_memory import REPLACED_MESSAGES_ATTR
from ..models import (
    Artifact,
    ArtifactPhase,
    CharacterStatsComponent,
    CombatArbitrationEvent,
    HumanMessage,
    PlayCardsAction,
    ReliquaryComponent,
    RoundEntryKind,
    render_labeled_str_list,
)
from ..utils import prompt_builder
from .arbitration_common import (
    ArbitrationContext,
    build_arbitration_broadcast,
    build_loop_summary_memory,
    build_stats_update_notification,
    get_entity_stats,
    make_get_entity_stats_tool,
    make_submit_arbitration_tool,
    submit_arbitration,
)


###########################################################################################################################################
# 仲裁提示词构建器
###########################################################################################################################################
def _build_artifact_blocks(entries: List[Tuple[str, Artifact]]) -> str:
    """把本场待结算的神器逐条渲染为提示词块；source 未显式指定时以携带者为归属。"""
    blocks: List[str] = []
    for holder_name, artifact in entries:

        # 渲染每个神器的修正规则块
        modifiers = (
            render_labeled_str_list(
                "- 修正规则（modifiers，逐条全部结算）",
                artifact.modifiers,
                indent="  ",
            )
            if artifact.modifiers
            else "- 修正规则（modifiers）：（未提供）"
        )

        # 渲染每个神器的基本信息块（名称、来源、描述）
        blocks.append(
            f"### {artifact.name}\n\n"
            f"- source（来源/归属）：{artifact.source or holder_name}\n\n"
            f"{artifact.description}\n\n"
            f"{modifiers}"
        )
    return "\n\n".join(blocks)


@prompt_builder
def _build_artifact_arbitration_prompt(
    entries: List[Tuple[str, Artifact]],
    current_round_number: int,
    party_names: str,
    monster_names: str,
) -> str:
    """构建一次神器仲裁的任务提示词：注入神器规则与本次动态上下文（回合 / 阵营）。"""
    return f"""# 第 {current_round_number} 回合：神器修正结算（工具调用模式）

你作为本场景的仲裁者，依据下列神器的「修正规则」完成本次覆盖式结算。

## 本场景神器

{_build_artifact_blocks(entries)}

## 场上存活

- 队伍方：{party_names}
- 怪物方：{monster_names}

## 结算规则

- 每条规则 = 「触发条件」+「效果」：按规则原文的触发条件（如「第 N 回合」「本回合首次结算」「仅触发一次」）判定，命中才执行效果；未写明的效果不得添加。
- 「无论本次结算如何」「必定」「必须」等措辞只强调效果力度，不改变触发条件。
- 一次性效果（含「仅触发一次」「此后不再触发」或一次性变身）：本场战斗只生效一次；结合你自己在本场战斗中的记忆判断是否已触发过，已触发则本次视为未触发。
- 数值只取自本次 {GET_ENTITY_STATS_TOOL.function.name} 的返回，禁止套用记忆中的数字。
- source 标识该神器的来源/归属实体；触发与叙事应以其立场进行。
- 未触发：不调用 {CHANGE_HP_TOOL.function.name}，直接 {SUBMIT_ARBITRATION_TOOL.function.name}；combat_log 写明未触发原因。
- 已触发：对每个受影响角色各调用一次 {CHANGE_HP_TOOL.function.name}，`delta` 为本次对其 HP 的变化量（负=扣血、正=回复）；系统自动 clamp 到 0~最大HP 并回显「旧→新」。
- 多个神器逐一判定；未触发者不得产生 HP 变更。

## 工具流程

1. {GET_ENTITY_STATS_TOOL.function.name} 读取可能受影响角色（可并发）。
2. 判定触发；触发则 {CHANGE_HP_TOOL.function.name}（delta），未触发则跳过。
3. {SUBMIT_ARBITRATION_TOOL.function.name} 提交；combat_log 按工具说明的格式写，**不要写 HP 数字**（系统会据第 2 步自动补记 `HP:角色 旧→新`）；narrative 与之一致。

### narrative

以神器的意象（description）为底色，写出修正规则本次如何显形（或未触发时的克制观感）；须与 combat_log 的 HP 变化一致，不得虚构规则之外的效果。"""


###########################################################################################################################################
# 仲裁工具定义（get/submit 的 schema 结构由 arbitration_common 统一，change_hp 为神器专属）
###########################################################################################################################################
GET_ENTITY_STATS_TOOL: Final[ToolDefinition] = make_get_entity_stats_tool(
    "读取指定战斗角色的当前生命值（HP/最大HP）与总格挡（其手牌 block 之和）。用于获取可能受影响角色当前状态。"
)


CHANGE_HP_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="change_hp",
        description="变更指定战斗角色的 HP：delta 为本次结算对其 HP 的变化量（负=扣血、正=回复），系统自动 clamp 到 0~最大HP 并回显规范化「旧→新」。仅当神器规则在本次触发、且该角色确实受影响时才调用一次；未触发时禁止调用本工具。",
        parameters={
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "角色全名",
                },
                "delta": {
                    "type": "integer",
                    "description": "本次对 HP 的变化量：负=扣血、正=回复（如 −4 表示造成 4 点伤害）",
                },
            },
            "required": ["entity_name", "delta"],
        },
    )
)


SUBMIT_ARBITRATION_TOOL: Final[ToolDefinition] = make_submit_arbitration_tool(
    "提交本次神器仲裁的最终结果（战斗日志、演出叙事、无法结算的规则）。"
    f"combat_log 写效果说明，HP 变化由系统据实际 {CHANGE_HP_TOOL.function.name} 调用自动补记。"
    "调用后本次仲裁结束。",
    combat_log_desc=(
        "战斗数据日志（简名 = 全名最后一段）。只写 `[<神器简名>|<当前回合数>] <效果说明>`，"
        "不要写 HP 数字；系统会自动追加 `；HP:<角色A> a→b <角色B> c→d`（仅在有 HP 变化时）。"
        "未触发写 `[<神器简名>|<当前回合数>] 触发条件未满足／已触发过，无 HP 变更`。"
    ),
)


###########################################################################################################################################
# 仲裁工具 handler（get/submit 核心在 arbitration_common；change_hp 为神器专属 delta 结算）
###########################################################################################################################################
def _handle_get_entity_stats(game: DBGGame, entity_name: str) -> str:
    """读取角色当前 HP 与总格挡。"""
    return get_entity_stats(game, entity_name)


def _handle_change_hp(
    game: DBGGame, ctx: ArbitrationContext, entity_name: str, delta: int
) -> str:
    """按有符号 delta 变更 HP（自动 clamp），并累积规范化「旧→新」；待仲裁结束后统一落库。"""
    entity = game.get_actor_entity(entity_name)
    if entity is None:
        return f"错误：找不到战斗角色 {entity_name}"

    # 读取角色当前属性，准备计算 HP 变化
    stats = compute_character_stats(entity)
    old_hp = ctx.pending_hp.get(entity_name, stats.hp)
    new_hp = max(0, min(old_hp + int(delta), stats.max_hp))

    # 记录初始 HP，如果尚未记录
    if entity_name not in ctx.hp_initial:
        ctx.hp_initial[entity_name] = old_hp

    # 更新待仲裁的 HP 状态和本次变化量
    ctx.pending_hp[entity_name] = new_hp
    ctx.hp_changes[entity_name] = new_hp

    # 计算本次 HP 变化的方向和描述动词
    changed = old_hp - new_hp  # 正=扣减

    # 根据 HP 变化量确定描述动词
    verb = "扣减" if changed > 0 else ("回复" if changed < 0 else "无变化")

    return (
        f"{entity_name} HP 将更新为 {new_hp}/{stats.max_hp}"
        f"（{old_hp} → {new_hp}，本次{verb} {abs(changed)}）"
    )


def _compose_artifact_combat_log(ctx: ArbitrationContext) -> str:
    """据实际 change_hp 结果渲染 HP 段（DM 只写效果说明），使日志的 HP 部分不可能与落库不符。"""
    assert ctx.combat_log is not None, "combat_log 不应为 None"
    hp_tail = " ".join(
        f"{name} {ctx.hp_initial[name]}→{ctx.hp_changes[name]}"
        for name in ctx.hp_initial
    )

    # 拼接 HP 变化段，确保日志与实际落库一致
    return f"{ctx.combat_log}；HP:{hp_tail}" if hp_tail else ctx.combat_log


###########################################################################################################################################
@final
class ArtifactPostArbitrationSystem(ReactiveProcessor):
    """响应 PlayCardsAction，由所在场景（stage）结算其携带的神器修正规则。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    #######################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {
            Matcher(PlayCardsAction): GroupEvent.ADDED,
        }

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(PlayCardsAction)

    #######################################################################################################################################
    async def react(self, entities: List[Entity]) -> None:

        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("ArtifactPostArbitrationSystem: 战斗未进行中，跳过神器仲裁")
            return

        # 同一帧可能有多个动作实体命中本运行点；逐个 await，串行结算，避免并发争夺
        for action_entity in entities:
            await self._run_arbitration(action_entity)

    #######################################################################################################################################
    async def _run_arbitration(self, action_entity: Entity) -> None:
        """对一次动作触发的场景神器执行一次仲裁。"""

        # 场景实体（当前战斗舞台），同时即本次仲裁者
        stage_entity = self._game.resolve_stage_entity(action_entity)
        assert (
            stage_entity is not None
        ), f"ArtifactPostArbitrationSystem: 无法找到 {action_entity.name} 所在的场景实体"

        # 作用域：当前战斗舞台 + 场上存活角色携带、且命中 POST_ARBITRATION 的神器（按 uuid 去重）
        holder_entities = [
            stage_entity,
            *sorted(
                get_alive_actors_in_stage(self._game, action_entity),
                key=lambda e: e.name,
            ),
        ]

        entries: List[Tuple[str, Artifact]] = []
        seen_uuids: set[str] = set()
        for holder_entity in holder_entities:
            if not holder_entity.has(ReliquaryComponent):
                continue
            for artifact in holder_entity.get(ReliquaryComponent).artifacts:
                if ArtifactPhase.POST_ARBITRATION not in artifact.phases:
                    continue
                if artifact.uuid in seen_uuids:
                    continue
                seen_uuids.add(artifact.uuid)
                entries.append((holder_entity.name, artifact))

        if not entries:
            logger.debug(
                "ArtifactPostArbitrationSystem: 当前战斗无命中运行点的神器，跳过仲裁"
            )
            return

        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )

        # 场上存活阵营（供 agent 判断「队伍方/怪物方」）
        party_members = get_alive_party_members_in_stage(stage_entity, self._game)
        monsters = get_alive_monsters_in_stage(stage_entity, self._game)
        party_names = (
            "、".join(e.name for e in party_members) if party_members else "无"
        )
        monster_names = "、".join(e.name for e in monsters) if monsters else "无"

        prompt = _build_artifact_arbitration_prompt(
            entries=entries,
            current_round_number=current_round_number,
            party_names=party_names,
            monster_names=monster_names,
        )

        # 仲裁结果容器：handler 通过 partial 绑定写入，避免闭包。
        ctx = ArbitrationContext()

        # 以 stage 实体为仲裁者：直接使用其持久记忆，使 prompt / 工具轨迹 / 结果都写入其记忆。
        stage_memory = self._game.get_agent_memory(stage_entity)
        assert stage_memory.messages, "场景实体缺少首条 SystemMessage"
        messages = stage_memory.messages

        # 本次 loop 的身份标记；结束后据 result 的区间把整段新增记忆压缩为一条总结。
        loop_id = f"artifact:{current_round_number}:{action_entity.name}"
        loop_start_index = len(messages)

        try:
            result = await agent_loop(
                name=stage_entity.name,
                input_message=prompt,
                messages=messages,
                tools=[
                    GET_ENTITY_STATS_TOOL,
                    CHANGE_HP_TOOL,
                    SUBMIT_ARBITRATION_TOOL,
                ],
                handlers={
                    GET_ENTITY_STATS_TOOL.function.name: partial(
                        _handle_get_entity_stats, self._game
                    ),
                    CHANGE_HP_TOOL.function.name: partial(
                        _handle_change_hp, self._game, ctx
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
                f"[ArtifactPostArbitrationSystem] {stage_entity.name} agent_loop 异常: {e}"
            )
            # 回滚本次 loop 已追加的记忆，避免失败轨迹污染上下文。
            self._game.replace_span(
                stage_entity, loop_start_index, len(stage_memory.messages), []
            )
            return

        if (
            not result
            or ctx.combat_log is None
            or ctx.narrative is None
            or ctx.summary is None
        ):
            logger.error(
                f"[ArtifactPostArbitrationSystem] {stage_entity.name} 未正常完成（未提交结果或达到轮次上限）"
            )
            # 回滚本次 loop 追加的记忆。
            self._game.replace_span(
                stage_entity, result.start_index, result.end_index, []
            )
            return

        # 成功：把本次 loop 新增的整段记忆压缩为一条「总结 + 数据日志」，并标记 loop_id。
        combat_log = _compose_artifact_combat_log(ctx)
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

        # 应用仲裁结果
        self._apply_arbitration_result(
            stage_entity=stage_entity,
            ctx=ctx,
            combat_log=combat_log,
        )

    #######################################################################################################################################
    def _apply_arbitration_result(
        self,
        stage_entity: Entity,
        ctx: ArbitrationContext,
        combat_log: str,
    ) -> None:
        """落库本次仲裁结果：HP / 广播 / 回合日志。"""

        assert ctx.narrative is not None, "narrative 不应为 None"
        narrative = ctx.narrative
        hp_changes = ctx.hp_changes

        # 校验 HP 变更中的实体名称（handler 已校验存在，此处兜底防御）
        for entity_name in hp_changes:
            if self._game.get_entity_by_name(entity_name) is None:
                logger.error(
                    f"ArtifactPostArbitrationSystem: hp_changes 中的实体不存在于游戏中: {entity_name}"
                )
                return

        # 广播本次神器仲裁结果给场景内角色
        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )

        # 广播仲裁结果给场景内的所有角色（除场景自身）
        self._game.broadcast_to_stage(
            entity=stage_entity,
            agent_event=CombatArbitrationEvent(
                message=build_arbitration_broadcast(
                    current_round_number,
                    f"{stage_entity.name} 神器仲裁",
                    narrative,
                    combat_log,
                ),
                stage=stage_entity.name,
                combat_log=combat_log,
                narrative=narrative,
            ),
            exclude_entities={stage_entity},
        )

        # 规则 telemetry：记录仲裁器无法按计算规则结算的条目
        for affix in ctx.unsettled_affixes:
            logger.warning(
                f"[ArtifactPostArbitrationSystem] 规则无法按计算规则结算（telemetry）: {affix}"
            )

        # 落库每个受影响角色的最终 HP 并发送「生命值已更新」通知
        for entity_name, hp in hp_changes.items():

            # 获取当前受影响的实体并校验其存在性与组件完整性
            entity = self._game.get_entity_by_name(entity_name)
            assert entity is not None, f"无法找到 hp_changes 中的实体: {entity_name}"
            assert entity.has(
                CharacterStatsComponent
            ), f"实体 {entity_name} 缺少 CharacterStatsComponent！"

            # 记录更新前的 HP
            old_hp = compute_character_stats(entity).hp
            after_stats = set_character_hp(entity, int(hp))
            logger.info(
                f"更新 {entity_name} HP: {old_hp} → {after_stats.hp}/{after_stats.max_hp}"
            )

            # 发送「生命值已更新」通知给当前受影响的实体
            self._game.add_human_message(
                entity=entity,
                human_message=HumanMessage(
                    content=build_stats_update_notification(
                        after_stats.hp, after_stats.max_hp
                    )
                ),
            )

        # 更新本回合的神器仲裁日志
        latest_round = self._game.current_dungeon_combat_room.combat.latest_round
        assert latest_round is not None, "latest_round 不应为 None"
        latest_round.record(RoundEntryKind.ARTIFACT, combat_log, narrative)
