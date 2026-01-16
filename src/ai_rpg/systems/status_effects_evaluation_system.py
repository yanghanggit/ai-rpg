"""状态效果评估系统模块

在战斗裁决后，让每个参战角色根据上下文（战斗广播、HP变化等）
自主评估并更新自己的状态效果。

执行时机：
- ArbitrationActionSystem 之后（已有战斗结果上下文）
- ActionCleanupSystem 之前（PlayCardsAction 仍存在）
"""

from typing import Final, List, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..chat_services.client import ChatClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    PlayCardsAction,
    CombatStatsComponent,
    StatusEffect,
    DeathComponent,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class StatusEffectsEvaluationResponse(BaseModel):
    """状态效果评估响应"""

    remove_effects: List[str] = []  # 要移除的效果名称列表
    add_effects: List[StatusEffect] = []  # 要添加的新效果列表


#######################################################################################################################################
def _generate_status_effects_evaluation_prompt(
    current_status_effects: List[StatusEffect],
    current_round_number: int,
) -> str:
    """生成状态效果评估提示词（精简版）"""

    # 格式化当前状态效果（仅名称）
    if len(current_status_effects) == 0:
        effects_list = "无"
    else:
        effects_list = ", ".join([effect.name for effect in current_status_effects])

    return f"""# 指令！第 {current_round_number} 回合结算完毕，更新状态效果

**现有效果**: {effects_list}

**任务**: 根据上文的**战斗演出**和**数据日志**

1. **移除(remove_effects)**: 列出要移除的现有效果名称（战斗中已失效/被治愈/被消除）
2. **添加(add_effects)**: 列出要添加的新效果（战斗中受伤/获得增益/遭受削弱等）

**约束**: 基于战斗演出与数据日志推断

**输出JSON**:

```json
{{
  "remove_effects": ["效果名1", "效果名2"],
  "add_effects": [
    {{"name": "新效果名", "description": "简述来源与影响"}}
  ]
}}
```

空数组表示无操作，只输出JSON"""


#######################################################################################################################################
@final
class StatusEffectsEvaluationSystem(ReactiveProcessor):
    """
    状态效果评估系统

    在战斗裁决后，让每个参战角色根据战斗结果自主评估状态效果。
    角色通过阅读上下文中的战斗广播、HP变化通知等信息，
    决定应该保持、移除或添加哪些状态效果。

    执行时机：ArbitrationActionSystem 之后，ActionCleanupSystem 之前

    触发条件：
    - 检测到 PlayCardsAction 组件（标识参战者）
    - 实体有 CombatStatsComponent（战斗属性）
    - 实体没有 DeathComponent（存活角色）
    - 战斗状态为 ONGOING
    """

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: Final[TCGGame] = game_context

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(PlayCardsAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        """过滤：存活的参战角色"""
        return (
            entity.has(PlayCardsAction)
            and entity.has(CombatStatsComponent)
            and not entity.has(DeathComponent)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        """
        为每个参战角色评估状态效果

        流程：
        1. 并发创建所有角色的评估任务
        2. 调用 LLM 生成状态效果评估
        3. 解析响应并更新 CombatStatsComponent.status_effects
        4. 添加状态效果变化通知到角色上下文
        """
        if not self._game.current_combat_sequence.is_ongoing:
            return

        # 获取当前回合数
        current_round_number = len(self._game.current_combat_sequence.current_rounds)

        # 为每个参战角色创建评估任务
        chat_clients: List[ChatClient] = []

        for entity in entities:
            combat_stats = entity.get(CombatStatsComponent)
            if combat_stats is None:
                logger.warning(
                    f"角色 {entity.name} 缺少 CombatStatsComponent，跳过状态评估"
                )
                continue

            # 生成评估提示词
            prompt = _generate_status_effects_evaluation_prompt(
                current_status_effects=combat_stats.status_effects,
                current_round_number=current_round_number,
            )

            # 添加评估指令到角色上下文
            self._game.add_human_message(
                entity=entity,
                message_content=prompt,
            )

            # 创建聊天客户端
            chat_clients.append(
                ChatClient(
                    name=entity.name,
                    prompt=prompt,
                    context=self._game.get_agent_context(entity).context,
                )
            )

        # 并发调用所有 LLM
        logger.debug(f"开始并发评估 {len(chat_clients)} 个角色的状态效果...")
        await ChatClient.gather_request_post(clients=chat_clients)

        # 处理每个角色的响应
        for chat_client in chat_clients:
            found_entity = self._game.get_entity_by_name(chat_client.name)
            if found_entity is None:
                logger.warning(f"无法找到角色实体: {chat_client.name}")
                continue

            self._process_status_effects_response(found_entity, chat_client)

    #######################################################################################################################################
    def _process_status_effects_response(
        self, entity: Entity, chat_client: ChatClient
    ) -> None:
        """处理单个角色的状态效果评估响应"""

        combat_stats = entity.get(CombatStatsComponent)
        if combat_stats is None:
            logger.warning(f"角色 {entity.name} 缺少 CombatStatsComponent")
            return

        try:
            # 获取 LLM 响应
            ai_response = chat_client.response_content
            # logger.debug(f"[{entity.name}] 状态效果评估原始响应: {ai_response}")

            # 提取 JSON
            json_content = extract_json_from_code_block(ai_response)

            # 解析为 Pydantic 模型
            format_response = StatusEffectsEvaluationResponse.model_validate_json(
                json_content
            )

            logger.debug(
                f"[{entity.name}] 状态效果评估成功: "
                f"移除{len(format_response.remove_effects)}个, "
                f"添加{len(format_response.add_effects)}个"
            )

            # 第一步：移除指定的效果（按名称匹配）
            remaining_effects = [
                effect
                for effect in combat_stats.status_effects
                if effect.name not in format_response.remove_effects
            ]

            # 第二步：添加新效果
            new_effects = remaining_effects + format_response.add_effects

            # 第三步：更新到组件
            combat_stats.status_effects = new_effects

            # 第四步：通报移除的效果
            if format_response.remove_effects:
                removed_msg = "# 通知！移除状态效果\n\n" + "\n".join(
                    [f"- {name}" for name in format_response.remove_effects]
                )
                self._game.add_human_message(entity=entity, message_content=removed_msg)

            # 第五步：通报添加的效果
            if format_response.add_effects:
                added_msg = "# 通知！新增状态效果\n\n" + "\n".join(
                    [
                        f"+ {effect.name}: {effect.description}"
                        for effect in format_response.add_effects
                    ]
                )
                self._game.add_human_message(entity=entity, message_content=added_msg)

            # 记录日志
            if format_response.remove_effects or format_response.add_effects:
                logger.debug(
                    f"[{entity.name}] 状态效果变化: "
                    f"移除={format_response.remove_effects}, "
                    f"添加={[e.name for e in format_response.add_effects]}"
                )

        except Exception as e:
            logger.error(f"[{entity.name}] 解析状态效果评估失败: {e}")
            logger.error(f"原始响应: {chat_client.response_content}")

            # 解析失败时保持原有状态效果不变
            self._game.add_human_message(
                entity=entity,
                message_content="# 状态效果评估失败\n\n保持现有状态效果不变",
            )


#######################################################################################################################################
