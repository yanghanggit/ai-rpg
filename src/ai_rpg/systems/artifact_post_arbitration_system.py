"""神器·出牌后仲裁系统模块。

神器是独立实体（其 system_message 即人设）。在一次出牌/消耗品仲裁完成后，本系统找出
当前战斗作用域内（当前舞台 + 场上存活角色所持有）、挂有 PostArbitrationComponent 的神器实体，
逐一以神器实体自身为 agent，依其人设中的「神器修正规则」做覆盖式结算：
读取属性 → 判定规则是否触发（如「第 N 回合」）→ 写入 HP → 提交仲裁结果（战斗日志/叙事）。

神器作为 agent 会在自身记忆中持续积累每次结算（prompt / 工具轨迹 / 结果）；
同时把「发生了什么」写入场景实体记忆，并广播本次事件，使场景与场上角色均获得记忆。
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
    NARRATIVE_DESCRIPTION,
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
    """构建神器仲裁提示词：回合数/神器身份与持有者/场上阵营注入。

    神器自身的修正规则已写入其人设（system_message）的「神器修正规则」段，
    此处只补足本次结算所需的动态上下文。
    """
    return f"""# 第 {current_round_number} 回合：神器修正结算（工具调用模式）

你是在一次「战斗结算/消耗品使用结算」之后被唤醒的神器「{artifact_name}」，负责落实你自身人设中的「神器修正规则」。这些修正规则发生在该次结算之后，属覆盖式修正。

## 当前回合数

第 {current_round_number} 回合

## 你的身份

- 神器全名：{artifact_name}
- 持有者：{holder_name}

## 场上阵营（当前存活）

- 队伍方：{party_names}
- 怪物方：{monster_names}

## 结算规则

- 你只能通过下方工具读取/写入数据，禁止引入工具未提供的机制。
- 严格依据你人设中「神器修正规则」的语义结算；规则未写明的效果不得凭空添加。
- 只有当规则的触发条件满足时（例如「第 N 回合」且当前回合数恰为 N）才执行该规则；条件不满足则本回合不产生任何 HP 变更。
- 对每个受影响角色调用 set_entity_hp 写入最终 HP。
- 目标 HP = max(0, min(计算后 HP, 最大 HP))。

## 工具使用流程

1. 调用 get_entity_stats 读取所有可能受影响角色的当前属性（可在同一次回复中并发调用多个）。
2. 依据「神器修正规则」的触发条件与语义结算，得出每个受影响角色的最终 HP。
3. 对每个受影响角色调用 set_entity_hp 写入最终 HP（可在同一次回复中并发调用多个）。
4. 调用 submit_arbitration 提交最终结果，结束本次仲裁。

## submit_arbitration 字段说明

### combat_log（简名 = 全名最后一段）

示例：`[纸钱方孔|第2回合] HP:英雄 12→0 阿秀 8→0`

{NARRATIVE_DESCRIPTION}"""


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
        description="设置指定战斗角色的当前生命值（自动 clamp 到 0~最大HP）。对每个受影响角色都必须调用一次。",
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
        description="提交本次神器仲裁的最终结果（战斗日志、演出叙事）。调用后本次仲裁结束。",
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
    """处理 get_entity_stats 工具调用：返回角色的 HP 与格挡。"""
    entity = game.get_actor_entity(entity_name)
    if entity is None:
        return f"错误：找不到战斗角色 {entity_name}"

    stats = compute_character_stats(entity)
    hand_block = compute_character_hand_block(entity)
    return f"{entity_name}: HP {stats.hp}/{stats.max_hp} | BLOCK {hand_block}"


def _handle_set_entity_hp(
    game: DBGGame, ctx: _ArbitrationContext, entity_name: str, hp: int
) -> str:
    """处理 set_entity_hp 工具调用：暂存最终 HP，等待仲裁结束后统一落库。"""
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
    """处理 submit_arbitration 工具调用：提交最终仲裁结果。"""
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
        """驱动一次动作后、作用域内所有命中神器的完整临时 agent 仲裁流程。"""

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

        # 神器自身即 agent：直接使用其真实记忆列表，让本次结算（prompt / 工具轨迹 / 结果）
        # 完整写入神器实体记忆，供后续运行点继续积累上下文。
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
        """应用临时 agent 的神器仲裁结果：广播事件、写入 HP、记录回合日志。"""

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

        # 把本次「发生了什么」写入场景实体记忆，供场景与参战角色通过广播获得记忆；
        # 同时把结果补写进神器自身记忆（agent_loop 已写入 prompt 与工具轨迹）。
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
