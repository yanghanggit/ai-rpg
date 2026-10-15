"""神器·出牌后仲裁系统：出牌/消耗品仲裁后，由所在场景（stage）结算其自身及存活角色携带的神器修正规则。"""

import json
from functools import partial
from typing import Dict, Final, List, Optional, Tuple, final

from loguru import logger
from overrides import override
from pydantic import BaseModel, Field

from ..deepseek import ToolDefinition, ToolFunction, agent_loop
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_combat_processor import (
    compute_character_hand_block,
    compute_character_stats,
    get_alive_actors_in_stage,
    get_alive_monsters_in_stage,
    get_alive_party_members_in_stage,
    set_character_hp,
)
from ..game.dbg_game import DBGGame
from ..models import (
    AIMessage,
    Artifact,
    ArtifactPhase,
    CharacterStatsComponent,
    CombatArbitrationEvent,
    HumanMessage,
    PlayCardsAction,
    ReliquaryComponent,
    render_labeled_str_list,
)
from ..utils import prompt_builder


###########################################################################################################################################
# 仲裁提示词构建器
###########################################################################################################################################
def _build_artifact_blocks(entries: List[Tuple[str, Artifact]]) -> str:
    """把本场待结算的神器逐条渲染为提示词块；source 未显式指定时以携带者为归属。"""
    blocks: List[str] = []
    for holder_name, artifact in entries:
        modifiers = (
            render_labeled_str_list(
                "- 修正规则（modifiers，逐条全部结算）",
                artifact.modifiers,
                indent="  ",
            )
            if artifact.modifiers
            else "- 修正规则（modifiers）：（未提供）"
        )
        blocks.append(
            f"### {artifact.name}\n\n"
            f"- source（来源/归属）：{artifact.source or holder_name}\n\n"
            f"{artifact.description}\n\n"
            f"{modifiers}"
        )
    return "\n\n".join(blocks)


@prompt_builder
def _build_artifact_post_arbitration_prompt(
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
- 未触发：不调用 {SET_ENTITY_HP_TOOL.function.name}，直接 {SUBMIT_ARBITRATION_TOOL.function.name}，combat_log 写明未触发原因与各方当前 HP。
- 已触发：对每个受影响角色各调用一次 {SET_ENTITY_HP_TOOL.function.name} 写入最终 HP（clamp 到 0~最大HP）。
- 多个神器逐一判定；未触发者不得产生 HP 变更。

## 工具流程

1. {GET_ENTITY_STATS_TOOL.function.name} 读取可能受影响角色（可并发）。
2. 判定触发；触发则 {SET_ENTITY_HP_TOOL.function.name} 写入最终 HP，未触发则跳过。
3. {SUBMIT_ARBITRATION_TOOL.function.name} 提交；combat_log / narrative 必须与第 2 步实际调用完全一致。

## combat_log 格式（简名 = 全名最后一段）

- 已触发：`[<神器简名>|<当前回合数>] HP:<角色A> a→b <角色B> c→d`
- 未触发：`[<神器简名>|<当前回合数>] 触发条件未满足／已触发过，无 HP 变更；<角色A> a/a <角色B> c/c`

### narrative

60-120 字，第三人称外部视角，纯感官描写，无数字 / 术语 / 内心。
以神器的意象（description）为底色，写出修正规则本次如何显形（或未触发时的克制观感）；须与 combat_log 的 HP 变化一致，不得虚构规则之外的效果。"""


@prompt_builder
def _build_artifact_arbitration_broadcast(
    combat_log: str, narrative: str, current_round_number: int, stage_name: str
) -> str:
    """神器仲裁的广播消息生成器（第 N 回合 · <场景名> 神器仲裁）。"""
    return f"""# 第 {current_round_number} 回合 · {stage_name} 神器仲裁

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
        description="读取指定战斗角色的当前生命值（HP/最大HP）与总格挡（其手牌 block 之和）。用于获取可能受影响角色当前状态。",
        parameters={
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "角色全名，如 角色.无名 或 怪物.纸人",
                },
            },
            "required": ["entity_name"],
        },
    )
)


SET_ENTITY_HP_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="set_entity_hp",
        description="设置指定战斗角色的当前生命值（自动 clamp 到 0~最大HP）。仅当神器规则在本次回合触发、且该角色确实受影响时，才对其调用一次；未触发时禁止调用本工具。",
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
        description="提交本次神器仲裁的最终结果（战斗日志、演出叙事、无法结算的规则）。"
        f"combat_log/narrative 必须与本次实际调用过的 {SET_ENTITY_HP_TOOL.function.name} 完全一致。"
        "调用后本次仲裁结束。",
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
                "unsettled_affixes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "可选：无法按本次结算规则处理的原始条目列表（如要求抽牌/回能/额外行动，或凭空叠加没有牌承载的标记），仅供系统统计，不计入结算。",
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


def _handle_get_entity_stats(game: DBGGame, entity_name: str) -> str:
    """读取角色当前 HP 与总格挡。"""
    entity = game.get_actor_entity(entity_name)
    if entity is None:
        return f"错误：找不到战斗角色 {entity_name}"

    stats = compute_character_stats(entity)
    hand_block = compute_character_hand_block(entity)
    return f"{entity_name}: HP {stats.hp}/{stats.max_hp} | 总格挡 {hand_block}"


def _handle_set_entity_hp(
    game: DBGGame, ctx: _ArbitrationContext, entity_name: str, hp: int
) -> str:
    """暂存最终 HP，待仲裁结束后统一落库。"""
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
    unsettled_affixes: Optional[List[str]] = None,
) -> str:
    """记录最终仲裁结果。"""
    ctx.combat_log = combat_log
    ctx.narrative = narrative
    if unsettled_affixes:
        ctx.unsettled_affixes = [str(a) for a in unsettled_affixes if str(a).strip()]
    return "仲裁结果已提交"


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
            await self._run_artifact_arbitration(action_entity)

    #######################################################################################################################################
    async def _run_artifact_arbitration(self, action_entity: Entity) -> None:
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

        prompt = _build_artifact_post_arbitration_prompt(
            entries=entries,
            current_round_number=current_round_number,
            party_names=party_names,
            monster_names=monster_names,
        )

        # 仲裁结果容器：handler 通过 partial 绑定写入，避免闭包。
        ctx = _ArbitrationContext()

        # 以 stage 实体为仲裁者：直接使用其持久记忆，使 prompt / 工具轨迹 / 结果都写入其记忆。
        stage_memory = self._game.get_agent_memory(stage_entity)
        assert stage_memory.messages, "场景实体缺少首条 SystemMessage"
        messages = stage_memory.messages

        try:
            ok = await agent_loop(
                name=stage_entity.name,
                prompt=prompt,
                messages=messages,
                tools=[
                    GET_ENTITY_STATS_TOOL,
                    SET_ENTITY_HP_TOOL,
                    SUBMIT_ARBITRATION_TOOL,
                ],
                handlers={
                    GET_ENTITY_STATS_TOOL.function.name: partial(
                        _handle_get_entity_stats, self._game
                    ),
                    SET_ENTITY_HP_TOOL.function.name: partial(
                        _handle_set_entity_hp, self._game, ctx
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
            logger.error(
                f"[ArtifactPostArbitrationSystem] {stage_entity.name} agent_loop 异常: {e}"
            )
            return

        if not ok or ctx.combat_log is None or ctx.narrative is None:
            logger.error(
                f"[ArtifactPostArbitrationSystem] {stage_entity.name} 未正常完成（未提交结果或达到轮次上限）"
            )
            return

        # 应用仲裁结果
        self._apply_artifact_arbitration_result(
            stage_entity=stage_entity,
            ctx=ctx,
        )

    #######################################################################################################################################
    def _apply_artifact_arbitration_result(
        self,
        stage_entity: Entity,
        ctx: _ArbitrationContext,
    ) -> None:
        """落库本次仲裁结果：HP / 广播 / 回合日志。"""

        assert ctx.combat_log is not None, "combat_log 不应为 None"
        assert ctx.narrative is not None, "narrative 不应为 None"
        combat_log = ctx.combat_log
        narrative = ctx.narrative
        hp_changes = ctx.hp_changes

        # 校验 HP 变更中的实体名称（handler 已校验存在，此处兜底防御）
        for entity_name in hp_changes:
            if self._game.get_entity_by_name(entity_name) is None:
                logger.error(
                    f"ArtifactPostArbitrationSystem: hp_changes 中的实体不存在于游戏中: {entity_name}"
                )
                return

        # 仲裁者是场景（stage）：agent_loop 已原地写 prompt 与工具轨迹，这里仅补记结构化结果。
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

        # 广播本次神器仲裁结果给场景内角色
        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )

        # 广播仲裁结果给场景内的所有角色（除场景自身）
        self._game.broadcast_to_stage(
            entity=stage_entity,
            agent_event=CombatArbitrationEvent(
                message=_build_artifact_arbitration_broadcast(
                    combat_log,
                    narrative,
                    current_round_number,
                    stage_entity.name,
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
                    content=_build_stats_update_notification(
                        after_stats.hp, after_stats.max_hp
                    )
                ),
            )

        # 更新本回合的神器仲裁日志
        latest_round = self._game.current_dungeon_combat_room.combat.latest_round
        assert latest_round is not None, "latest_round 不应为 None"
        latest_round.artifact_log.append(combat_log)
        latest_round.artifact_narrative.append(narrative)
