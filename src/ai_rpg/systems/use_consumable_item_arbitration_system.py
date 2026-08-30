"""使用消耗品仲裁系统模块。

借世界实体「世界.消耗品仲裁」作为临时 agent（LLM），在工具边界内结算消耗品使用效果：
读取属性 → 依效果提示词结算 → 写入 HP → 提交仲裁结果（战斗日志/叙事/场景快照）。

临时 agent 的对话上下文仅在本次结算过程中累积，结束后不写回宿主世界实体的持久记忆。
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
    compute_character_stats,
    get_alive_actors_in_stage,
    set_character_hp,
)
from ..game.dbg_game import DBGGame
from ..models import (
    AIMessage,
    CharacterStatsComponent,
    CombatArbitrationEvent,
    ConsumableArbitratorComponent,
    ConsumableItem,
    HumanMessage,
    StageDescriptionComponent,
    UseConsumableItemAction,
    WorldComponent,
)
from ..utils import prompt_builder
from .arbitration_prompt_builders import (
    NARRATIVE_DESCRIPTION,
    STAGE_DESCRIPTION_DESCRIPTION,
    build_arbitration_broadcast,
    build_stats_update_notification,
)


###########################################################################################################################################
# 仲裁提示词构建器
###########################################################################################################################################


@prompt_builder
def _build_consumable_arbitration_prompt(
    actor_name: str,
    item: ConsumableItem,
    targets: List[str],
    current_round_number: int,
    current_stage_description: str,
    stage_actor_names: List[str],
) -> str:
    """构建消耗品仲裁提示词：发起人/目标/场景描述/场景内参与人员/效果提示词全部注入。"""
    target_names = "、".join(targets) if targets else "无"
    stage_actors = "、".join(stage_actor_names) if stage_actor_names else "无"
    effect_prompt = (
        item.on_use_prompt[0]
        if item.on_use_prompt
        else "（未提供额外效果提示，仅依据物品描述合理推断）"
    )

    return f"""# 第 {current_round_number} 回合：消耗品使用结算（工具调用模式）

## 使用发起人

{actor_name}

## 消耗品

- 名称：{item.name}
- 描述：{item.description}
- 效果提示：{effect_prompt}

## 目标

{target_names}

## 场景内参与人员

{stage_actors}

## 当前场景环境

{current_stage_description}

## 结算规则

- 你只能通过下方工具读取/写入数据，禁止引入工具未提供的机制。
- 严格依据「效果提示」与物品「描述」结算本次使用；效果提示未写明的效果不得凭空添加。
- 对每个受影响角色（至少包含发起人与所有目标，即使 HP 无变化也保持原值）调用 set_entity_hp 写入最终 HP。
- 目标 HP = max(0, min(计算后 HP, 最大 HP))。

## 工具使用流程

1. 调用 get_entity_stats 读取「发起人」与「目标」的当前属性（可在同一次回复中并发调用多个）。
2. 依据「效果提示」「描述」结算，得出每个受影响角色的最终 HP。
3. 对每个受影响角色调用 set_entity_hp 写入最终 HP（可在同一次回复中并发调用多个）。
4. 调用 submit_arbitration 提交最终结果，结束本次仲裁。

## submit_arbitration 字段说明

### combat_log（简名 = 全名最后一段）

示例：`[治愈药水→英雄] HP:英雄 8→13`

{NARRATIVE_DESCRIPTION}

{STAGE_DESCRIPTION_DESCRIPTION}"""


###########################################################################################################################################
# 仲裁工具定义
###########################################################################################################################################
GET_ENTITY_STATS_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="get_entity_stats",
        description="读取指定战斗角色的最终有效属性（HP/最大HP/攻击/防御）。用于获取发起者与目标当前状态。",
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
        description="设置指定战斗角色的当前生命值（自动 clamp 到 0~最大HP）。对每个受影响角色（含发起者与所有目标）都必须调用一次。",
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
        description="提交本次仲裁的最终结果（战斗日志、演出叙事、场景环境快照）。调用后本次仲裁结束。",
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
                "stage_description": {
                    "type": "string",
                    "description": "仲裁后的场景环境快照",
                },
            },
            "required": ["combat_log", "narrative", "stage_description"],
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
    stage_description: Optional[str] = None


###########################################################################################################################################
def _handle_get_entity_stats(game: DBGGame, entity_name: str) -> str:
    """处理 get_entity_stats 工具调用：返回角色的最终有效属性。"""
    entity = game.get_actor_entity(entity_name)
    if entity is None:
        return f"错误：找不到战斗角色 {entity_name}"

    stats = compute_character_stats(entity)
    return (
        f"{entity_name}: HP {stats.hp}/{stats.max_hp} | "
        f"ATK {stats.attack} | DEF {stats.defense}"
    )


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
    stage_description: str,
) -> str:
    """处理 submit_arbitration 工具调用：提交最终仲裁结果。"""
    ctx.combat_log = combat_log
    ctx.narrative = narrative
    ctx.stage_description = stage_description
    return "仲裁结果已提交"


###########################################################################################################################################
@final
class UseConsumableItemArbitrationSystem(ReactiveProcessor):
    """响应 UseConsumableItemAction 事件，借世界实体「世界.消耗品仲裁」作为临时 agent 结算消耗品效果。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    #######################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(UseConsumableItemAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(UseConsumableItemAction)

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("UseConsumableItemArbitrationSystem: 战斗未进行中，跳过仲裁")
            return

        assert (
            len(entities) == 1
        ), "UseConsumableItemArbitrationSystem 期望每次仅处理一个 UseConsumableItemAction 实体"
        await self._run_consumable_arbitration(entities[0])

    #######################################################################################################################################
    async def _run_consumable_arbitration(self, actor_entity: Entity) -> None:
        """驱动单次消耗品使用的完整临时 agent 仲裁流程。"""

        action = actor_entity.get(UseConsumableItemAction)

        # 宿主：专用的「世界.消耗品仲裁」世界实体（其 SystemMessage 即临时 agent 的「设定」）
        arbitrator_entities = self._game.get_group(
            Matcher(all_of=[WorldComponent, ConsumableArbitratorComponent])
        ).entities
        assert (
            len(arbitrator_entities) == 1
        ), f"UseConsumableItemArbitrationSystem: 应恰好存在一个消耗品仲裁世界实体，实际={len(arbitrator_entities)}"
        arbitrator_entity = next(iter(arbitrator_entities))

        # 场景实体与当前场景环境快照
        stage_entity = self._game.resolve_stage_entity(actor_entity)
        assert (
            stage_entity is not None
        ), f"UseConsumableItemArbitrationSystem: 无法找到 {actor_entity.name} 所在的场景实体"
        assert stage_entity.has(
            StageDescriptionComponent
        ), "当前场景实体缺少 StageDescriptionComponent 组件！"
        current_stage_description = stage_entity.get(
            StageDescriptionComponent
        ).narrative

        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )

        # 场景内参与人员（存活角色），供 agent 感知战场全貌
        stage_actor_names = sorted(
            e.name for e in get_alive_actors_in_stage(self._game, actor_entity)
        )

        prompt = _build_consumable_arbitration_prompt(
            actor_name=actor_entity.name,
            item=action.item,
            targets=action.targets,
            current_round_number=current_round_number,
            current_stage_description=current_stage_description,
            stage_actor_names=stage_actor_names,
        )

        # 仲裁结果容器：handler 通过 partial 绑定写入，避免闭包。
        ctx = _ArbitrationContext()

        # 上下文隔离：仅取世界实体的首条 SystemMessage 作为「设定」，
        # 传入全新列表（agent_loop 原地追加），结束后不写回宿主实体持久记忆。
        arbitrator_memory = self._game.get_agent_memory(arbitrator_entity)
        assert arbitrator_memory.messages, "消耗品仲裁世界实体缺少首条 SystemMessage"
        # 仅取首条消息（SystemMessage，即「设定」），构造全新列表供 agent_loop 原地追加
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
            logger.error(f"[UseConsumableItemArbitrationSystem] agent_loop 异常: {e}")
            return

        if (
            not ok
            or ctx.combat_log is None
            or ctx.narrative is None
            or ctx.stage_description is None
        ):
            logger.error(
                "[UseConsumableItemArbitrationSystem] 仲裁未正常完成（未提交结果或达到轮次上限）"
            )
            return

        # 通知覆盖保证：发起人 + 所有目标（去重）都必须收到通知；
        # 若 LLM 未对某个实体调用 set_entity_hp（例如其 HP 未变化），则补记其当前 HP。
        notify_names = list(dict.fromkeys([actor_entity.name, *action.targets]))
        for notify_name in notify_names:
            if notify_name in ctx.hp_changes:
                continue
            entity = self._game.get_actor_entity(notify_name)
            if entity is None:
                logger.error(
                    f"[UseConsumableItemArbitrationSystem] 无法找到需通知角色: {notify_name}"
                )
                return
            ctx.hp_changes[notify_name] = compute_character_stats(entity).hp

        self._apply_arbitration_result(stage_entity, ctx, prompt, action.item)

    #######################################################################################################################################
    def _apply_arbitration_result(
        self,
        stage_entity: Entity,
        ctx: _ArbitrationContext,
        prompt: str,
        item: ConsumableItem,
    ) -> None:
        """应用临时 agent 的仲裁结果：更新场景快照、广播事件、写入 HP、记录回合日志。"""

        assert ctx.combat_log is not None, "combat_log 不应为 None"
        assert ctx.narrative is not None, "narrative 不应为 None"
        assert ctx.stage_description is not None, "stage_description 不应为 None"
        combat_log = ctx.combat_log
        narrative = ctx.narrative
        stage_description = ctx.stage_description
        hp_changes = ctx.hp_changes

        # 校验 HP 变更中的实体名称（handler 已校验存在，此处兜底防御）
        for entity_name in hp_changes:
            if self._game.get_entity_by_name(entity_name) is None:
                logger.error(
                    f"UseConsumableItemArbitrationSystem: hp_changes 中的实体不存在于游戏中: {entity_name}"
                )
                return

        # 仲裁结果更新场景环境快照（若 agent 判定本次使用影响了场景）
        if stage_description.strip():
            stage_entity.replace(
                StageDescriptionComponent,
                stage_entity.name,
                stage_description,
            )

        # 将本轮仲裁记录进场景实体记忆（供后续场景叙事/塞牌等系统复用），
        # 临时 agent 自身的对话上下文不写回世界实体。
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
                        "stage_description": stage_description,
                    },
                    ensure_ascii=False,
                )
            ),
        )

        # 广播本次仲裁结果给场景内角色
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
                    f"使用消耗品「{item.name}」",
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

        # 更新本回合的消耗品仲裁日志与计数
        latest_round = self._game.current_dungeon_combat_room.combat.latest_round
        assert latest_round is not None, "latest_round 不应为 None"
        latest_round.consumable_combat_log.append(combat_log)
        latest_round.consumable_narrative.append(narrative)
        latest_round.consumable_use_count += 1
