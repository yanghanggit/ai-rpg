"""场景神器仲裁系统模块。

借世界实体「世界.神器仲裁」作为临时 agent（LLM），在一次出牌/消耗品仲裁完成后，
依本场景神器的修正规则（modifiers）做覆盖式结算：
读取属性 → 判定规则是否触发（如「第 N 回合」）→ 写入 HP → 提交仲裁结果（战斗日志/叙事）。

临时 agent 的对话上下文仅在本次结算过程中累积，结束后不写回宿主世界实体的持久记忆。
注意：本系统借用世界实体作为临时 agent，不直接改写场景的环境快照（StageDescriptionComponent）；
仅把「发生了什么」写入场景实体记忆，由场景自身后续推理更新。
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
    Artifact,
    ArtifactArbitratorComponent,
    CharacterStatsComponent,
    CombatArbitrationEvent,
    HumanMessage,
    PlayCardsAction,
    StageDescriptionComponent,
    UseConsumableItemAction,
    WorldComponent,
)
from ..utils import prompt_builder
from .arbitration_prompt_builders import (
    NARRATIVE_DESCRIPTION,
    build_arbitration_broadcast,
    build_stats_update_notification,
)


###########################################################################################################################################
# 硬编码神器（数据注入落地前的临时承载；后续改为从场景/副本数据读取）
###########################################################################################################################################
_HARDCODED_ARTIFACTS: Final[List[Artifact]] = [
    Artifact(
        name="纸钱方孔",
        description="散落满院的纸钱，其方孔总像在暗中调转方向；据说被它们「看过」第二回合的人，会在一瞬间失了全部气力。",
        modifiers=[
            "第 2 回合时，满院纸钱将夺走闯入者的生气：本回合仲裁中，队伍方所有角色生命耗尽（HP 归零），"
            "无论本次出牌如何结算，最终结果都必须体现队伍方全员倒下、无力再战。",
        ],
    ),
]


###########################################################################################################################################
# 仲裁提示词构建器
###########################################################################################################################################
def _build_artifact_lines(artifacts: List[Artifact]) -> str:
    """把神器清单格式化为提示词片段。"""
    if not artifacts:
        return "无"
    lines: List[str] = []
    for artifact in artifacts:
        lines.append(f"- **{artifact.name}**：{artifact.description}")
        for modifier in artifact.modifiers:
            lines.append(f"  - 修正规则：{modifier}")
    return "\n".join(lines)


@prompt_builder
def _build_artifact_arbitration_prompt(
    current_round_number: int,
    artifacts: List[Artifact],
    party_names: str,
    monster_names: str,
    current_stage_description: str,
) -> str:
    """构建神器仲裁提示词：回合数/神器修正规则/场上阵营/场景环境全部注入。"""
    return f"""# 第 {current_round_number} 回合：场景神器修正结算（工具调用模式）

你是一次出牌/消耗品仲裁完成之后被临时唤醒的场景神器仲裁者，负责落实本场景神器的修正规则。

## 当前回合数

第 {current_round_number} 回合

## 当前场景神器

{_build_artifact_lines(artifacts)}

## 场上阵营（当前存活）

- 队伍方：{party_names}
- 怪物方：{monster_names}

## 当前场景环境

{current_stage_description}

## 结算规则

- 你只能通过下方工具读取/写入数据，禁止引入工具未提供的机制。
- 严格依据各神器的「修正规则」结算；规则未写明的效果不得凭空添加。
- 只有当规则的触发条件满足时（例如「第 N 回合」且当前回合数恰为 N）才执行该规则；条件不满足则本回合不产生任何 HP 变更。
- 对每个受影响角色调用 set_entity_hp 写入最终 HP。
- 目标 HP = max(0, min(计算后 HP, 最大 HP))。

## 工具使用流程

1. 调用 get_entity_stats 读取所有可能受影响角色的当前属性（可在同一次回复中并发调用多个）。
2. 依据各神器「修正规则」的触发条件与语义结算，得出每个受影响角色的最终 HP。
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
class ArtifactArbitrationSystem(ReactiveProcessor):
    """响应 PlayCardsAction / UseConsumableItemAction 事件，借世界实体「世界.神器仲裁」作为临时 agent 结算神器修正规则。"""

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
            logger.debug("ArtifactArbitrationSystem: 战斗未进行中，跳过神器仲裁")
            return

        if not _HARDCODED_ARTIFACTS:
            logger.debug("ArtifactArbitrationSystem: 无神器规则，跳过神器仲裁")
            return

        assert (
            len(entities) == 1
        ), "ArtifactArbitrationSystem 期望每次仅处理一个动作实体"
        await self._run_artifact_arbitration(entities[0])

    #######################################################################################################################################
    async def _run_artifact_arbitration(self, actor_entity: Entity) -> None:
        """驱动单次神器修正的完整临时 agent 仲裁流程。"""

        # 宿主：专用的「世界.神器仲裁」世界实体（其 SystemMessage 即临时 agent 的「设定」）
        arbitrator_entities = self._game.get_group(
            Matcher(all_of=[WorldComponent, ArtifactArbitratorComponent])
        ).entities
        assert (
            len(arbitrator_entities) == 1
        ), f"ArtifactArbitrationSystem: 应恰好存在一个神器仲裁世界实体，实际={len(arbitrator_entities)}"
        arbitrator_entity = next(iter(arbitrator_entities))

        # 场景实体与当前场景环境快照
        stage_entity = self._game.resolve_stage_entity(actor_entity)
        assert (
            stage_entity is not None
        ), f"ArtifactArbitrationSystem: 无法找到 {actor_entity.name} 所在的场景实体"
        assert stage_entity.has(
            StageDescriptionComponent
        ), "当前场景实体缺少 StageDescriptionComponent 组件！"
        current_stage_description = stage_entity.get(
            StageDescriptionComponent
        ).narrative

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
            current_round_number=current_round_number,
            artifacts=list(_HARDCODED_ARTIFACTS),
            party_names=party_names,
            monster_names=monster_names,
            current_stage_description=current_stage_description,
        )

        # 仲裁结果容器：handler 通过 partial 绑定写入，避免闭包。
        ctx = _ArbitrationContext()

        # 上下文隔离：仅取世界实体的首条 SystemMessage 作为「设定」，
        # 传入全新列表（agent_loop 原地追加），结束后不写回宿主实体持久记忆。
        arbitrator_memory = self._game.get_agent_memory(arbitrator_entity)
        assert arbitrator_memory.messages, "神器仲裁世界实体缺少首条 SystemMessage"
        messages = [arbitrator_memory.messages[0]]

        try:
            ok = await agent_loop(
                name=arbitrator_entity.name,
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
            logger.error(f"[ArtifactArbitrationSystem] agent_loop 异常: {e}")
            return

        if not ok or ctx.combat_log is None or ctx.narrative is None:
            logger.error(
                "[ArtifactArbitrationSystem] 神器仲裁未正常完成（未提交结果或达到轮次上限）"
            )
            return

        # 应用仲裁结果
        self._apply_artifact_arbitration_result(stage_entity, ctx, prompt)

    #######################################################################################################################################
    def _apply_artifact_arbitration_result(
        self,
        stage_entity: Entity,
        ctx: _ArbitrationContext,
        prompt: str,
    ) -> None:
        """应用临时 agent 的神器仲裁结果：广播事件、写入 HP、记录回合日志（不直接改场景环境快照）。"""

        assert ctx.combat_log is not None, "combat_log 不应为 None"
        assert ctx.narrative is not None, "narrative 不应为 None"
        combat_log = ctx.combat_log
        narrative = ctx.narrative
        hp_changes = ctx.hp_changes

        # 校验 HP 变更中的实体名称（handler 已校验存在，此处兜底防御）
        for entity_name in hp_changes:
            if self._game.get_entity_by_name(entity_name) is None:
                logger.error(
                    f"ArtifactArbitrationSystem: hp_changes 中的实体不存在于游戏中: {entity_name}"
                )
                return

        # 仅把「发生了什么」记录进场景实体记忆（供场景后续推理更新自身环境快照），
        # 临时 agent 自身的对话上下文不写回世界实体。本系统不改写 StageDescriptionComponent。
        self._game.add_human_message(
            entity=stage_entity,
            human_message=HumanMessage(content=prompt),
        )
        self._game.add_ai_message(
            entity=stage_entity,
            ai_message=AIMessage(
                content=json.dumps(
                    {
                        "combat_log": combat_log,
                        "narrative": narrative,
                    },
                    ensure_ascii=False,
                )
            ),
        )

        # 广播本次神器仲裁结果给场景内角色
        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )
        self._game.broadcast_to_stage(
            entity=stage_entity,
            agent_event=CombatArbitrationEvent(
                message=build_arbitration_broadcast(
                    combat_log,
                    narrative,
                    current_round_number,
                    "场景神器仲裁",
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
