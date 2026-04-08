"""战斗状态效果追加系统模块

监听 AddStatusEffectsAction.ADDED，让每个参战角色根据上下文（战斗广播、HP变化等）
评估并追加新的状态效果。

执行时机：
- 监听 AddStatusEffectsAction.ADDED（ReactiveProcessor）
- 目前由 CombatInitializationSystem 在初始化末尾为所有参战角色添加 AddStatusEffectsAction 触发
- 后续裁决系统完成后，也将在回合结算后触发
"""

from typing import Final, List, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..chat_client.client import ChatClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    ActorComponent,
    AddStatusEffectsAction,
    StatusEffectsComponent,
    StatusEffect,
    StatusEffectPhase,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class AddStatusEffectsResponse(BaseModel):
    """追加状态效果响应"""

    add_effects: List[StatusEffect] = []  # 本次追加的新效果列表


#######################################################################################################################################
def _generate_add_status_effects_prompt(
    current_status_effects: List[StatusEffect],
    current_round_number: int,
    task_hint: str,
    max_effects: int,
) -> str:
    """生成追加状态效果提示词

    要求 agent 回顾上下文历史并结合当前已有状态，追加本回合应有的新状态效果。

    Args:
        current_status_effects: 当前已有的状态效果列表
        current_round_number: 当前回合数
        task_hint: 任务说明，补充本次评估的背景与意图
        max_effects: 最多追加的状态效果数量，默认2

    Returns:
        格式化的提示词字符串
    """

    # 效果少时展示完整描述；过多时仅列名称以节省 token
    def _fmt_duration(d: int) -> str:
        return "永久" if d == -1 else f"剩余{d}回合"

    if len(current_status_effects) == 0:
        effects_list = "无"
    elif len(current_status_effects) <= 3:
        effects_list = "\n".join(
            [
                f"- {effect.name}（{_fmt_duration(effect.duration)}）: {effect.description}"
                for effect in current_status_effects
            ]
        )
    else:
        effects_list = "、".join(
            [
                f"{effect.name}（{_fmt_duration(effect.duration)}）"
                for effect in current_status_effects
            ]
        )

    phase_desc = f"""
## 生效阶段（phase）说明

每个状态效果必须指定 `phase` 字段，决定它在战斗流程的哪个阶段起效：

| phase | 对应阶段 | 可影响的属性 | 典型效果举例 |
|---|---|---|---|
| `{StatusEffectPhase.DRAW}` | 抽牌阶段 | attack、defense（换算为卡牌的 damage_dealt / block_gain / hit_count） | 「虚弱」攻击力−2，本回合生成卡牌的 damage_dealt 偏低；「沉重」防御力−1，生成卡牌的 block_gain 偏低 |
| `{StatusEffectPhase.PLAY}` | 出牌阶段 | damage_dealt、block_gain、hit_count（附加到本回合出的牌上） | 「淬毒」为本回合打出的牌附加 damage_dealt+2；「护盾祝福」为本回合出的牌附加 block_gain+2 |
| `{StatusEffectPhase.ARBITRATION}` | 仲裁结算阶段 | hp、damage_dealt、block_gain | 「燃烧」本回合结算时扣 hp 3；「坚甲」格挡+3；「中毒」造成伤害+2 |

**属性约束（所有阶段均适用）**：
- 禁止修改 max_hp（最大生命值不可通过状态效果改变）
- `{StatusEffectPhase.DRAW}` 阶段使用 attack / defense 描述，不直接写 damage_dealt / block_gain
- `{StatusEffectPhase.ARBITRATION}` 阶段直接使用 hp / damage_dealt / block_gain，不使用 attack / defense

绝大多数伤害/防御类效果选 `{StatusEffectPhase.ARBITRATION}`。"""

    return f"""# 第 {current_round_number} 回合 — 追加状态效果

回顾上下文历史，结合当前已有状态效果，追加本回合应有的新状态效果。

> {task_hint}

## 当前状态效果

{effects_list}
{phase_desc}

**要求**：不重复现有效果，最多追加 {max_effects} 个；无新增时输出空数组。

```json
{{
  "add_effects": [
    {{
      "name": "效果名（<8字）",
      "description": "第一人称，含表现与数值影响，1句话（如：我感到手臂刺痛，攻击力−2）",
      "duration": 持续回合数（-1=永久，正整数=剩余回合，默认3）,
      "phase": "{StatusEffectPhase.ARBITRATION}"
    }}
  ]
}}
```

无新增状态时输出空数组，只输出JSON."""


#######################################################################################################################################
@final
class AddStatusEffectsActionSystem(ReactiveProcessor):
    """战斗状态效果追加系统

    监听 AddStatusEffectsAction.ADDED，让每个参战角色根据上下文
    （战斗广播、HP变化等）评估并追加新的状态效果（受伤、增益、削弱等）。

    执行机制：
    - 监听 AddStatusEffectsAction.ADDED（ReactiveProcessor）
    - 目前由 CombatInitializationSystem 在初始化末尾触发，覆盖第一回合初始状态
    - 仅在战斗进行中时触发（is_ongoing 守卫）

    执行条件：
    - 战斗状态为 ONGOING（is_ongoing=True）
    - 自动获取当前场景上的所有存活角色
    - 每个角色需有 CombatStatusEffectsComponent
    """

    def __init__(self, game: TCGGame, max_effects: int = 2) -> None:
        super().__init__(game)
        assert max_effects > 0, "max_effects 必须为正整数"
        self._game: Final[TCGGame] = game
        self._max_effects: Final[int] = max_effects

    #######################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(AddStatusEffectsAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(AddStatusEffectsAction)
            and entity.has(StatusEffectsComponent)
            and entity.has(ActorComponent)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        """
        为每个参战角色追加状态效果

        流程：
        1. 为所有参战角色并发创建 LLM 评估任务
        2. 调用 LLM 生成新状态效果
        3. 解析响应并追加到 CombatStatusEffectsComponent.status_effects
        4. 将新增状态效果通知写入角色上下文
        """

        # 仅在战斗进行中时触发
        if not self._game.current_dungeon.is_ongoing:
            return

        logger.debug(f"触发 AddStatusEffectsActionSystem，处理 {len(entities)} 个实体")

        # 获取当前回合数
        current_round_number = len(self._game.current_dungeon.current_rounds or [])

        # 获取玩家实体, player在的场景就是战斗发生的场景！
        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "无法找到玩家实体！"

        # 获取当前场景实体
        current_stage_entity = self._game.resolve_stage_entity(player_entity)
        assert current_stage_entity is not None, "无法找到当前场景实体！"

        # 参与战斗的角色实体列表
        actor_entities = self._game.get_alive_actors_in_stage(player_entity)
        assert len(actor_entities) > 0, "不可能出现没人参与战斗的情况！"

        # 为每个参战角色创建评估任务
        chat_clients: List[ChatClient] = []

        for entity in actor_entities:

            combat_status_effects = entity.get(StatusEffectsComponent)
            assert (
                combat_status_effects is not None
            ), f"角色 {entity.name} 缺少 CombatStatusEffectsComponent！"

            # 从 action 组件读取任务说明
            add_status_effects_action = entity.get(AddStatusEffectsAction)
            assert add_status_effects_action is not None

            # 生成追加状态效果提示词
            prompt = _generate_add_status_effects_prompt(
                current_status_effects=combat_status_effects.status_effects,
                current_round_number=current_round_number,
                task_hint=add_status_effects_action.task_hint,
                max_effects=self._max_effects,
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
        await ChatClient.batch_chat(clients=chat_clients)

        # 处理每个角色的响应
        for chat_client in chat_clients:
            found_entity = self._game.get_entity_by_name(chat_client.name)
            assert found_entity is not None, f"无法找到角色实体: {chat_client.name}"
            self._process_status_effects_response(found_entity, chat_client)

    #######################################################################################################################################
    def _process_status_effects_response(
        self, entity: Entity, chat_client: ChatClient
    ) -> None:
        """处理单个角色的状态效果评估响应，完成本轮对话并追加新状态效果

        将本轮 prompt 以 add_human_message 写入角色上下文，
        将 LLM 回复以 add_ai_message 写入角色上下文，
        从而在 entity context 中形成完整的一轮 Human↔AI 对话。
        """

        assert entity.has(
            StatusEffectsComponent
        ), f"Entity {entity.name} must have CombatStatusEffectsComponent"

        # 解析 LLM 响应，追加状态效果
        try:
            json_content = extract_json_from_code_block(chat_client.response_content)
            format_response = AddStatusEffectsResponse.model_validate_json(json_content)

            # 将本轮 prompt 写入角色上下文（Human 端）
            self._game.add_human_message(
                entity=entity, message_content=chat_client.prompt
            )

            # 将 LLM 回复写入角色上下文（AI 端），完成本轮对话
            self._game.add_ai_message(
                entity=entity, ai_messages=chat_client.response_ai_messages
            )

            # 添加新效果到现有列表
            if format_response.add_effects:
                combat_status_effects = entity.get(StatusEffectsComponent)
                combat_status_effects.status_effects.extend(format_response.add_effects)
                logger.debug(
                    f"[{entity.name}] 新增 {len(format_response.add_effects)} 个状态效果"
                )
            else:
                logger.debug(f"[{entity.name}] 本回合无新增状态效果")

        except Exception as e:
            logger.error(f"[{entity.name}] 解析状态效果评估失败: {e}")
            logger.error(f"原始响应: {chat_client.response_content}")


#######################################################################################################################################
