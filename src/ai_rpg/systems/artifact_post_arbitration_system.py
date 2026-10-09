"""神器·出牌后仲裁系统。

出牌/消耗品仲裁完成后，以作用域内的神器实体为 agent，按其人设中的「神器修正规则」执行覆盖式结算。

关键约束：
- 作用域 = 当前舞台 + 场上存活角色所持有的、挂有 PostArbitrationComponent 的神器，不跨场景。
- 神器自身即 agent（人设 = system_message）；结算写入神器记忆，并写入场景、广播给场上角色。
"""

import json
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
    get_alive_monsters_in_stage,
    get_alive_party_members_in_stage,
    set_character_hp,
)
from ..game.dbg_game import DBGGame
from ..models import (
    AIMessage,
    ArtifactComponent,
    CharacterStatsComponent,
    CombatArbitrationEvent,
    HumanMessage,
    IdentityComponent,
    PlayCardsAction,
    PostArbitrationComponent,
    UseConsumableItemAction,
)
from ..utils import prompt_builder
from .arbitration_prompt_builders import (
    build_arbitration_broadcast,
    build_stats_update_notification,
)


###########################################################################################################################################
# 仲裁提示词构建器
###########################################################################################################################################
@prompt_builder
def _build_artifact_post_arbitration_prompt(
    artifact_name: str,
    holder_name: str,
    current_round_number: int,
    party_names: str,
    monster_names: str,
) -> str:
    """构建一次神器仲裁的任务提示词：只注入本次动态上下文（回合 / 持有者 / 存活阵营）。

    神器人设与「神器修正规则」已在 system_message，此处不重复。
    """
    return f"""# 第 {current_round_number} 回合：神器修正结算（工具调用模式）

一次「战斗结算/消耗品使用结算」已完成。请依据你人设中的「神器修正规则」，执行本次覆盖式修正。

## 本次上下文

- 当前回合数：第 {current_round_number} 回合
- 神器：{artifact_name}（持有者：{holder_name}）
- 队伍方（存活）：{party_names}
- 怪物方（存活）：{monster_names}

## 结算规则

- 规则 = 「触发条件」+「效果」：先按规则原文的触发条件（如「第 N 回合」）与当前回合数判定，只有触发才执行效果；规则未写明的效果不得添加。
- 「无论本次出牌/消耗品如何结算」「必定」「必须」等措辞只强调效果力度/覆盖性，不改变触发条件；未触发时不得产生任何 HP 变更。
- 未触发：不调用 set_entity_hp，直接 submit_arbitration，combat_log 写明「触发条件未满足，无 HP 变更」及各方当前 HP。
- 已触发：对每个受影响角色调用一次 set_entity_hp 写入最终 HP（自动 clamp 到 0~最大HP）。
- 只能通过下方工具读写数据；判定与数值只取自本次 get_entity_stats、当前回合数与规则原文，不得套用记忆中的过往结论或数值。

## 一致性契约

submit_arbitration 的 combat_log / narrative 必须与本次实际调用过的 set_entity_hp 完全一致：改了谁、改成多少就写谁、写多少；未改不得声称已改，已改不得声称未改。

## 工具流程

1. get_entity_stats 读取可能受影响角色（可并发）。
2. 判定触发；触发则 set_entity_hp 写入最终 HP，未触发则跳过本步。
3. submit_arbitration 提交，combat_log / narrative 与第 2 步实际行为一致。

## combat_log 格式（简名 = 全名最后一段）

- 已触发：`[<神器简名>|<当前回合数>] HP:<角色A> a→b <角色B> c→d`
- 未触发：`[<神器简名>|<当前回合数>] 触发条件未满足，无 HP 变更；<角色A> a/a <角色B> c/c`

### narrative

60-120 字，第三人称外部视角，纯感官描写，无数字 / 术语 / 内心。
以你自身人设中的意象为底色，写出「神器修正规则」本次如何显形——作用于谁、以什么样的感官痕迹留下结果；规则未触发时，则写出「无事发生」的克制观感。
描写须与 combat_log 的 HP 变化一致，不得虚构规则之外的效果。"""


###########################################################################################################################################
# 仲裁工具定义
###########################################################################################################################################
GET_ENTITY_STATS_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="get_entity_stats",
        description="读取指定战斗角色的当前生命值（HP/最大HP）与格挡（BLOCK，手牌 block 之和）。用于获取可能受影响角色当前状态。",
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
        description="设置指定战斗角色的当前生命值（自动 clamp 到 0~最大HP）。仅当你的人设规则在本次回合触发、且该角色确实受影响时，才对其调用一次；未触发时禁止调用本工具。",
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
        description="提交本次神器仲裁的最终结果（战斗日志、演出叙事）。combat_log/narrative 必须与本次实际调用过的 set_entity_hp 完全一致。调用后本次仲裁结束。",
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
class _ArbitrationContext(BaseModel):
    """仲裁工具 handler 的共享结果容器。"""

    hp_changes: Dict[str, int] = Field(default_factory=dict)
    combat_log: Optional[str] = None
    narrative: Optional[str] = None


def _handle_get_entity_stats(game: DBGGame, entity_name: str) -> str:
    """读取角色当前 HP 与格挡。"""
    entity = game.get_actor_entity(entity_name)
    if entity is None:
        return f"错误：找不到战斗角色 {entity_name}"

    stats = compute_character_stats(entity)
    hand_block = compute_character_hand_block(entity)
    return f"{entity_name}: HP {stats.hp}/{stats.max_hp} | BLOCK {hand_block}"


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
) -> str:
    """记录最终仲裁结果。"""
    ctx.combat_log = combat_log
    ctx.narrative = narrative
    return "仲裁结果已提交"


###########################################################################################################################################
@final
class ArtifactPostArbitrationSystem(ReactiveProcessor):
    """响应 PlayCardsAction / UseConsumableItemAction，驱动作用域内命中运行点的神器实体各自完成修正结算。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    #######################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {
            Matcher(PlayCardsAction): GroupEvent.ADDED,
            Matcher(UseConsumableItemAction): GroupEvent.ADDED,
        }

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(PlayCardsAction) or entity.has(UseConsumableItemAction)

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("ArtifactPostArbitrationSystem: 战斗未进行中，跳过神器仲裁")
            return

        # 同一帧可能有多个动作实体命中本运行点；逐个 await，串行结算，避免并发争夺
        for action_entity in entities:
            await self._run_artifact_arbitration(action_entity)

    #######################################################################################################################################
    async def _run_artifact_arbitration(self, action_entity: Entity) -> None:
        """对一次动作触发的、作用域内所有命中神器逐一仲裁。"""

        # 场景实体（当前战斗舞台）
        stage_entity = self._game.resolve_stage_entity(action_entity)
        assert (
            stage_entity is not None
        ), f"ArtifactPostArbitrationSystem: 无法找到 {action_entity.name} 所在的场景实体"

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

        # 收敛作用域：只取持有者为当前战斗舞台或本场存活角色的神器，不跨场景
        scoped_holder_names = {
            stage_entity.name,
            *(e.name for e in party_members),
            *(e.name for e in monsters),
        }
        artifact_entities: List[Entity] = [
            entity
            for entity in self._game.get_group(
                Matcher(all_of=[ArtifactComponent, PostArbitrationComponent])
            ).entities
            if entity.get(ArtifactComponent).holder in scoped_holder_names
        ]

        if not artifact_entities:
            logger.debug(
                "ArtifactPostArbitrationSystem: 当前战斗舞台与参战角色无命中运行点的神器，跳过仲裁"
            )
            return

        # 稳定顺序：按实体创建顺序依次仲裁；逐个结算，后者可读到前者已落库的 HP
        artifact_entities.sort(
            key=lambda entity: entity.get(IdentityComponent).creation_order
        )

        for artifact_entity in artifact_entities:
            await self._run_single_artifact_arbitration(
                artifact_entity=artifact_entity,
                stage_entity=stage_entity,
                current_round_number=current_round_number,
                party_names=party_names,
                monster_names=monster_names,
            )

    #######################################################################################################################################
    async def _run_single_artifact_arbitration(
        self,
        artifact_entity: Entity,
        stage_entity: Entity,
        current_round_number: int,
        party_names: str,
        monster_names: str,
    ) -> None:
        """以单个神器实体为宿主，驱动一次临时 agent 仲裁。"""

        holder_name = artifact_entity.get(ArtifactComponent).holder

        prompt = _build_artifact_post_arbitration_prompt(
            artifact_name=artifact_entity.name,
            holder_name=holder_name,
            current_round_number=current_round_number,
            party_names=party_names,
            monster_names=monster_names,
        )

        # 仲裁结果容器：handler 通过 partial 绑定写入，避免闭包。
        ctx = _ArbitrationContext()

        # 直接使用神器真实记忆，使本次 prompt / 工具轨迹 / 结果都写入其记忆。
        artifact_memory = self._game.get_agent_memory(artifact_entity)
        assert artifact_memory.messages, "神器实体缺少首条 SystemMessage"
        messages = artifact_memory.messages

        try:
            ok = await agent_loop(
                name=artifact_entity.name,
                prompt=prompt,
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
                terminal_tools=[SUBMIT_ARBITRATION_TOOL],
            )
        except Exception as e:
            logger.error(
                f"[ArtifactPostArbitrationSystem] {artifact_entity.name} agent_loop 异常: {e}"
            )
            return

        # agent_loop 直接追加记忆，绕过 add_ai_message，这里手动同步上下文占比
        self._game.sync_latest_context_usage_ratio(artifact_entity)

        if not ok or ctx.combat_log is None or ctx.narrative is None:
            logger.error(
                f"[ArtifactPostArbitrationSystem] {artifact_entity.name} 未正常完成（未提交结果或达到轮次上限）"
            )
            return

        # 应用仲裁结果
        self._apply_artifact_arbitration_result(
            artifact_entity=artifact_entity,
            stage_entity=stage_entity,
            ctx=ctx,
            prompt=prompt,
        )

    #######################################################################################################################################
    def _apply_artifact_arbitration_result(
        self,
        artifact_entity: Entity,
        stage_entity: Entity,
        ctx: _ArbitrationContext,
        prompt: str,
    ) -> None:
        """落库本次仲裁结果：HP / 记忆 / 广播 / 回合日志。"""

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

        # 写入场景记忆并补写神器记忆（agent_loop 已写 prompt 与工具轨迹）。
        result_content = json.dumps(
            {
                "combat_log": combat_log,
                "narrative": narrative,
            },
            ensure_ascii=False,
        )
        self._game.add_human_message(
            entity=stage_entity,
            human_message=HumanMessage(content=prompt),
        )
        self._game.add_ai_message(
            entity=stage_entity,
            ai_message=AIMessage(content=result_content),
        )
        self._game.add_ai_message(
            entity=artifact_entity,
            ai_message=AIMessage(content=result_content),
        )

        # 广播本次神器仲裁结果给场景内角色
        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )
        title = f"神器·{artifact_entity.name}"
        self._game.broadcast_to_stage(
            entity=stage_entity,
            agent_event=CombatArbitrationEvent(
                message=build_arbitration_broadcast(
                    combat_log,
                    narrative,
                    current_round_number,
                    title,
                ),
                stage=stage_entity.name,
                combat_log=combat_log,
                narrative=narrative,
            ),
            exclude_entities={stage_entity},
        )

        # 落库每个受影响角色的最终 HP 并发送「生命值已更新」通知
        for entity_name, hp in hp_changes.items():
            entity = self._game.get_entity_by_name(entity_name)
            assert entity is not None, f"无法找到 hp_changes 中的实体: {entity_name}"
            assert entity.has(
                CharacterStatsComponent
            ), f"实体 {entity_name} 缺少 CharacterStatsComponent！"

            old_hp = compute_character_stats(entity).hp
            after_stats = set_character_hp(entity, int(hp))
            logger.info(
                f"更新 {entity_name} HP: {old_hp} → {after_stats.hp}/{after_stats.max_hp}"
            )
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
        latest_round.artifact_log.append(combat_log)
        latest_round.artifact_narrative.append(narrative)
