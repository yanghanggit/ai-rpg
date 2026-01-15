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

    status_effects: List[StatusEffect] = []
    reasoning: str = ""  # AI的评估推理过程（用于调试和日志）


#######################################################################################################################################
def _generate_status_effects_evaluation_prompt(
    actor_name: str,
    current_hp: int,
    max_hp: int,
    hp_change: int,
    current_status_effects: List[StatusEffect],
    current_round_number: int,
) -> str:
    """生成状态效果评估提示词"""

    # 格式化当前状态效果
    if len(current_status_effects) == 0:
        status_effects_text = "- 无"
    else:
        status_effects_text = "\n".join(
            [
                f"- {effect.name}: {effect.description}"
                for effect in current_status_effects
            ]
        )

    # 格式化HP变化
    change_symbol = "+" if hp_change > 0 else ""
    hp_change_text = f"{change_symbol}{hp_change}"

    return f"""# 指令！第 {current_round_number} 回合结算完毕，评估你的状态效果

根据刚才的战斗结果（战斗演出、伤害日志、HP变化），评估你当前应该具有的状态效果。

## 当前状态

- 当前HP: {current_hp}/{max_hp}
- HP变化: {hp_change_text}
- 现有状态效果:
{status_effects_text}

## 评估规则

### 1. 保持现有效果
- 检查每个现有状态效果是否应该继续生效
- 考虑战斗结果是否影响了效果的存续

### 2. 移除失效效果
- 被治疗/驱散的效果
- 触发条件消失的效果
- 战斗中明确提到消除的效果

### 3. 添加新效果
基于战斗结果合理推断新状态效果：

**受伤类**
- 流血：被利刃划伤，持续失血
- 骨折：被重击骨骼，降低防御或行动力
- 中毒：接触毒素，降低攻击力或持续损伤
- 灼伤：被火焰伤害，持续疼痛

**增益类**
- 鼓舞：成功攻击或占优势，士气提升
- 专注：进入战斗节奏，提高命中或伤害
- 愤怒：受到伤害反而激发战意，攻击力提升

**削弱类**
- 虚弱：体力大量消耗，降低攻击
- 疲惫：持续战斗耗尽精力，降低防御
- 恐惧：被强敌威慑或受重创，降低全属性

## 约束

1. **基于事实推断**：只根据战斗演出中实际发生的事情推断状态效果
2. **合理性检查**：不要添加不合理或过于夸张的效果
3. **效果上限**：同时存在的状态效果不应超过5个
4. **避免重复**：相同类型的效果不要重复添加（如已有"流血"就不要再添加"流血"）
5. **描述具体**：效果描述要具体说明来源和影响，不要过于抽象

## 输出格式(JSON)

```json
{{
  "status_effects": [
    {{
      "name": "流血",
      "description": "胸口被利爪划伤，伤口持续渗血，每回合损失少量HP"
    }},
    {{
      "name": "愤怒",
      "description": "因受伤而激发战意，攻击力暂时提升"
    }}
  ],
  "reasoning": "基于战斗中被山中虎利爪划伤的事实，判断应该有流血状态；同时作为经验丰富的猎人，受伤后会更加专注，因此添加愤怒状态提升攻击"
}}
```

**注意**：
- status_effects 为空数组表示无状态效果
- reasoning 字段用于说明你的评估逻辑
- 只输出JSON，不要有其他内容"""


#######################################################################################################################################
def _generate_status_effects_change_notification(
    old_effects: List[StatusEffect], new_effects: List[StatusEffect]
) -> str:
    """生成状态效果变化通知"""

    # 提取效果名称集合
    old_names = {effect.name for effect in old_effects}
    new_names = {effect.name for effect in new_effects}

    # 计算变化
    added_names = new_names - old_names
    removed_names = old_names - new_names
    kept_names = old_names & new_names

    # 如果没有任何变化
    if not added_names and not removed_names:
        if len(new_effects) == 0:
            return "# 状态效果评估完毕\n\n当前无状态效果"
        return f"# 状态效果评估完毕\n\n状态效果未发生变化，当前效果数量: {len(new_effects)}"

    # 构建变化消息
    message_parts = ["# 状态效果已更新\n"]

    if added_names:
        message_parts.append(f"**新增效果** ({len(added_names)}个):")
        for effect in new_effects:
            if effect.name in added_names:
                message_parts.append(f"+ {effect.name}: {effect.description}")

    if removed_names:
        message_parts.append(f"\n**移除效果** ({len(removed_names)}个):")
        for effect in old_effects:
            if effect.name in removed_names:
                message_parts.append(f"- {effect.name}")

    if kept_names:
        message_parts.append(f"\n**保持效果** ({len(kept_names)}个)")

    return "\n".join(message_parts)


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
            # and self._game.current_combat_sequence.is_ongoing
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
                actor_name=entity.name,
                current_hp=combat_stats.stats.hp,
                max_hp=combat_stats.stats.max_hp,
                hp_change=0,  # 如果需要可以从上下文中计算
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
        logger.info(f"开始并发评估 {len(chat_clients)} 个角色的状态效果...")
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
            logger.debug(f"[{entity.name}] 状态效果评估原始响应: {ai_response}")

            # 提取 JSON
            json_content = extract_json_from_code_block(ai_response)

            # 解析为 Pydantic 模型
            format_response = StatusEffectsEvaluationResponse.model_validate_json(
                json_content
            )

            logger.info(
                f"[{entity.name}] 状态效果评估成功: {len(format_response.status_effects)} 个效果"
            )
            if format_response.reasoning:
                logger.debug(f"[{entity.name}] 推理: {format_response.reasoning}")

            # 保存旧的状态效果
            old_effects = combat_stats.status_effects.copy()

            # 更新状态效果
            combat_stats.status_effects = format_response.status_effects

            # 生成并添加状态变化通知
            change_notification = _generate_status_effects_change_notification(
                old_effects, format_response.status_effects
            )

            self._game.add_human_message(
                entity=entity,
                message_content=change_notification,
            )

            # 记录详细的状态变化
            old_names = {effect.name for effect in old_effects}
            new_names = {effect.name for effect in format_response.status_effects}
            added = new_names - old_names
            removed = old_names - new_names

            if added or removed:
                logger.info(
                    f"[{entity.name}] 状态效果变化: "
                    f"新增={list(added)}, 移除={list(removed)}"
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
