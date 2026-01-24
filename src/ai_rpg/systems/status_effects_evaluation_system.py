"""状态效果评估系统模块

在战斗裁决后，让每个参战角色根据上下文（战斗广播、HP变化等）
自主评估并添加新的状态效果。

执行时机：
- 通过 combat_status_evaluation_pipeline 手动调用
- 建议在战斗裁决后（ArbitrationActionSystem）按需触发
- 用于战斗过程中的状态效果动态生成
"""

from typing import Final, List, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..chat_client.client import ChatClient
from ..entitas import Entity, ExecuteProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    CombatStatsComponent,
    StatusEffect,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class StatusEffectsEvaluationResponse(BaseModel):
    """状态效果评估响应"""

    add_effects: List[StatusEffect] = []  # 要添加的新效果列表


#######################################################################################################################################
def _generate_status_effects_evaluation_prompt(
    current_status_effects: List[StatusEffect],
    current_round_number: int,
    max_effects: int = 2,
) -> str:
    """生成状态效果评估提示词

    根据战斗结果评估应添加的新状态效果，避免重复添加已有效果。

    Args:
        current_status_effects: 当前已有的状态效果列表
        current_round_number: 当前回合数
        max_effects: 最多生成的状态效果数量，默认2

    Returns:
        格式化的提示词字符串
    """

    # 格式化当前状态效果（智能压缩，减少token）
    if len(current_status_effects) == 0:
        effects_list = "无"
    elif len(current_status_effects) <= 3:
        # 效果少时展示完整信息
        effects_list = "\n".join(
            [
                f"- {effect.name}: {effect.description}"
                for effect in current_status_effects
            ]
        )
    else:
        # 效果多时只展示名称列表，节省token
        effects_list = "、".join([effect.name for effect in current_status_effects])

    return f"""# 指令！第 {current_round_number} 回合结算完毕，评估新增状态效果

## 现有状态效果

{effects_list}

## 任务

根据上文的**战斗演出**(narrative)和**数据日志**(combat_log)，判断应添加的新状态效果（战斗受伤、增益削弱、战术效果、环境影响等）。

**状态效果要求**：
- name: 简洁的效果名称（<8字）
- description: 三段式（含标记）：
  1. **【分类】** 选择一个：增益 | 减益 | 复合 | 条件触发 | 环境
  2. **【表现】** 第一人称描述具体表现（1句话）
  3. **【效果】** 数值影响（不要 HP上限/时间词）："±X点攻击力/防御力"

**示例**：
```
【分类】减益
【表现】肩背皮开肉绽，鲜血浸透衣物，每次移动都牵扯伤口。
【效果】防御力降低2点。
```

**约束**: 不重复现有效果，最多生成 {max_effects} 个

**输出JSON**:

```json
{{
  "add_effects": [
    {{"name": "状态效果名", "description": "【分类】类型\n【表现】具体表现\n【效果】战斗影响"}}
  ]
}}
```

无新增状态时输出空数组，只输出JSON。"""


#######################################################################################################################################
@final
class StatusEffectsEvaluationSystem(ExecuteProcessor):
    """
    状态效果评估系统

    在战斗裁决后，让每个参战角色根据战斗结果评估并添加新的状态效果。
    角色通过阅读上下文中的战斗广播、HP变化通知等信息，
    判断应该添加哪些新状态效果（如受伤、增益、削弱等）。

    执行机制：
    - 手动调用（ExecuteProcessor），通过 combat_status_evaluation_pipeline 触发
    - 按需执行，而非每回合自动触发（节省 LLM 调用成本）
    - 建议在关键战斗节点或需要评估状态变化时调用

    执行条件：
    - 战斗状态为 ONGOING（is_ongoing=True）
    - 自动获取当前场景上的所有存活角色
    - 每个角色需有 CombatStatsComponent（战斗属性）
    """

    def __init__(self, game_context: TCGGame) -> None:
        self._game: Final[TCGGame] = game_context

    #######################################################################################################################################
    @override
    async def execute(self) -> None:
        """
        为每个参战角色评估新增状态效果

        流程：
        1. 并发创建所有角色的评估任务
        2. 调用 LLM 生成新状态效果
        3. 解析响应并追加到 CombatStatsComponent.status_effects
        4. 添加新增状态效果通知到角色上下文
        """
        if not (
            self._game.current_combat_sequence.is_ongoing
            or self._game.current_combat_sequence.is_completed
        ):
            # 战斗未进行中，跳过，或者已经结束了，也结束。
            return

        # 获取当前回合数
        current_round_number = len(self._game.current_combat_sequence.current_rounds)

        # 获取玩家实体, player在的场景就是战斗发生的场景！
        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        # 获取当前场景实体
        current_stage_entity = self._game.resolve_stage_entity(player_entity)
        assert current_stage_entity is not None

        # 参与战斗的角色实体列表
        actor_entities = self._game.get_alive_actors_on_stage(player_entity)
        assert len(actor_entities) > 0, "不可能出现没人参与战斗的情况！"

        # 为每个参战角色创建评估任务
        chat_clients: List[ChatClient] = []

        for entity in actor_entities:
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
                max_effects=2,
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
        # logger.debug(f"开始并发评估 {len(chat_clients)} 个角色的状态效果...")
        await ChatClient.batch_chat(clients=chat_clients)

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
        """处理单个角色的状态效果评估响应，追加新状态效果"""

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

            # logger.debug(
            #     f"[{entity.name}] 状态效果评估成功: "
            #     f"添加{len(format_response.add_effects)}个"
            # )

            # 添加新效果到现有列表
            if format_response.add_effects:
                combat_stats.status_effects.extend(format_response.add_effects)

                # 通知角色新增的效果
                added_msg = "# 通知！新增状态效果\n\n" + "\n".join(
                    [
                        f"+ {effect.name}: {effect.description}"
                        for effect in format_response.add_effects
                    ]
                )
                self._game.add_human_message(entity=entity, message_content=added_msg)

                # 记录日志
                # logger.debug(
                #     f"[{entity.name}] 新增状态效果: "
                #     f"{[e.name for e in format_response.add_effects]}"
                # )
            else:
                logger.debug(f"[{entity.name}] 本回合无新增状态效果")

        except Exception as e:
            logger.error(f"[{entity.name}] 解析状态效果评估失败: {e}")
            logger.error(f"原始响应: {chat_client.response_content}")


#######################################################################################################################################
