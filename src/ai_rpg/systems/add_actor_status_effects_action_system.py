"""战斗状态效果追加系统模块

为参战角色动态评估并追加状态效果（增益/减益）；监听 AddStatusEffectsAction.ADDED。
"""

from typing import Final, List, final, Dict
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    ActorComponent,
    AddStatusEffectsAction,
    StatusEffectsComponent,
    StatusEffect,
    EffectPhase,
    DeathComponent,
    MonsterComponent,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class AddStatusEffectsResponse(BaseModel):
    """追加状态效果响应"""

    add_effects: List[StatusEffect] = []  # 本次追加的新效果列表


#######################################################################################################################################
def _generate_compressed_add_status_effects_prompt(
    current_status_effects: List[StatusEffect],
    current_round_number: int,
    task_hint: str,
    max_effects: int,
) -> str:
    """生成压缩版追加状态效果提示词（仅动态感知部分，省略静态 phase 说明与 JSON 示例）"""

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

    return f"""# 第 {current_round_number} 回合 — 追加状态效果

回顾上下文历史，结合当前已有状态效果，追加本回合应有的新状态效果。

> {task_hint}

## 当前状态效果

{effects_list}

**要求**：不重复现有效果，最多追加 {max_effects} 个；无新增时输出空数组。"""


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
## 生效阶段（phase）

| phase | 触发时机 | 典型效果 |
|---|---|---|
| `{EffectPhase.DRAW}` | 本回合抽牌时 | 「虚弱」生成的卡牌伤害偏低 |
| `{EffectPhase.ARBITRATION}` | 每次出牌结算时 | 「破甲」防御降低；「荆棘」反伤；条件计数型词条（`counter` 字段） |
| `{EffectPhase.ROUND_END}` | 每回合末自动 tick | 「中毒」扣血；「燃烧」持续伤害；「再生」回血（DOT/HOT） |"""

    return f"""# 第 {current_round_number} 回合 — 追加状态效果

回顾上下文历史，结合当前已有状态效果，追加本回合应有的新状态效果。

> {task_hint}

## 当前状态效果

{effects_list}
{phase_desc}

**要求**：不重复现有效果，最多追加 {max_effects} 个；无新增时输出空数组，只输出 JSON。

```json
{{
  "add_effects": [
    {{
      "name": "效果名（≤8字）",
      "description": "规则说明（客观描述效果机制与数值，如：每回合末损失 2 HP；前3次受击伤害变为 1）",
      "duration": 3,
      "phase": "round_end",
      "speed": 0,
      "defense": 0,
      "counter": 0
    }}
  ]
}}
```

- `duration`：-1=永久，>0=剩余回合数，默认 3
- `phase`：`{EffectPhase.DRAW}` / `{EffectPhase.ARBITRATION}` / `{EffectPhase.ROUND_END}` 三选一（见上表）
- `speed`：+1 / 0 / -1；持续叠加到角色出手速度，与 phase 无关，默认 0
- `defense`：整数；持续叠加到角色防御值（正值增防，负值破甲），与 phase 无关，默认 0
- `counter`：整数初始值；`{EffectPhase.ARBITRATION}` 阶段特殊计数器词条（如"前3次受击"设 3），默认 0
- 禁止修改 `max_hp`"""


#######################################################################################################################################
@final
class AddActorStatusEffectsActionSystem(ReactiveProcessor):
    """让每个参战 Actor 根据战斗上下文评估并追加新的状态效果（增益/减益/削弱等）。

    约束：实体须同时具有 ActorComponent + StatusEffectsComponent；仅战斗 ongoing 时生效。
    """

    def __init__(
        self,
        game: TCGGame,
        max_effects: int = 2,
        use_compressed_prompt: bool = True,
    ) -> None:
        super().__init__(game)
        assert max_effects > 0, "max_effects 必须为正整数"
        self._game: Final[TCGGame] = game
        self._max_effects: Final[int] = max_effects
        self._use_compressed_prompt: Final[bool] = use_compressed_prompt

    #######################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(AddStatusEffectsAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(AddStatusEffectsAction)
            and entity.has(StatusEffectsComponent)
            and entity.has(ActorComponent)
            and not entity.has(DeathComponent)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        """并发为所有实体调用 LLM 评估并追加状态效果。"""

        # 仅在战斗进行中时触发
        if not self._game.current_dungeon.is_ongoing:
            return

        logger.debug(
            f"触发 AddActorStatusEffectsActionSystem，处理 {len(entities)} 个实体"
        )

        # 获取当前回合数
        current_round_number = len(self._game.current_dungeon.current_rounds or [])

        # 直接使用 filter() 已过滤的实体列表，避免重新查询导致对未添加 AddStatusEffectsAction 的角色 assert 失败
        # 为每个参战角色创建评估任务
        chat_clients: List[DeepSeekClient] = []

        for entity in entities:

            combat_status_effects = entity.get(StatusEffectsComponent)
            assert (
                combat_status_effects is not None
            ), f"角色 {entity.name} 缺少 StatusEffectsComponent！"

            # 从 action 组件读取任务说明
            add_status_effects_action = entity.get(AddStatusEffectsAction)
            assert (
                add_status_effects_action is not None
            ), f"角色 {entity.name} 缺少 AddStatusEffectsAction 组件！"

            # 生成追加状态效果提示词
            prompt = _generate_add_status_effects_prompt(
                current_status_effects=combat_status_effects.status_effects,
                current_round_number=current_round_number,
                task_hint=add_status_effects_action.task_hint,
                max_effects=self._max_effects,
            )

            compressed_message: str | None = None
            if self._use_compressed_prompt:
                compressed_message = _generate_compressed_add_status_effects_prompt(
                    current_status_effects=combat_status_effects.status_effects,
                    current_round_number=current_round_number,
                    task_hint=add_status_effects_action.task_hint,
                    max_effects=self._max_effects,
                )

            # 创建聊天客户端
            chat_clients.append(
                DeepSeekClient(
                    name=entity.name,
                    prompt=prompt,
                    compressed_prompt=compressed_message,
                    context=self._game.get_agent_context(entity).context,
                )
            )

        # 并发调用所有 LLM
        logger.debug(f"开始并发评估 {len(chat_clients)} 个角色的状态效果...")
        await DeepSeekClient.batch_chat(clients=chat_clients)

        # 处理每个角色的响应
        for chat_client in chat_clients:
            found_entity = self._game.get_entity_by_name(chat_client.name)
            assert found_entity is not None, f"无法找到角色实体: {chat_client.name}"
            self._process_status_effects_response(found_entity, chat_client)
            # self._mock_inject_counter_effect(found_entity)  # [测试用]

    #######################################################################################################################################
    def _mock_inject_counter_effect(self, entity: Entity) -> None:
        """[测试用] 若实体为怪物，强制注入一个计数型状态效果，用于验证 counter 机制。

        规则：前3次受击伤害锁定为1；counter 初始为 3，仲裁 LLM 每次受击后将其递减 1，
        counter 归零后效果不再触发。已注入则跳过（避免重复）。
        """
        if not entity.has(MonsterComponent):
            return

        combat_status_effects = entity.get(StatusEffectsComponent)
        assert combat_status_effects is not None

        mock_effect_name = "伤害锁定"
        if any(
            e.name == mock_effect_name for e in combat_status_effects.status_effects
        ):
            return

        mock_effect = StatusEffect(
            name=mock_effect_name,
            description="前3次受击伤害锁定为1；每次受击后 counter 递减1，counter 归零后效果失效",
            duration=-1,
            phase=EffectPhase.ARBITRATION,
            counter=3,
            source="[mock]",
        )
        combat_status_effects.status_effects.append(mock_effect)
        logger.debug(
            f"[{entity.name}] [mock] 注入测试效果: 「{mock_effect.name}」counter={mock_effect.counter}"
        )

    #######################################################################################################################################
    def _process_status_effects_response(
        self, entity: Entity, chat_client: DeepSeekClient
    ) -> None:
        """解析 LLM 响应并追加新状态效果；将本轮对话写入实体上下文。"""

        assert entity.has(
            StatusEffectsComponent
        ), f"Entity {entity.name} must have StatusEffectsComponent"

        # 解析 LLM 响应，追加状态效果
        try:
            json_content = extract_json_from_code_block(chat_client.response_content)
            format_response = AddStatusEffectsResponse.model_validate_json(json_content)

            # 将本轮 prompt 写入角色上下文（Human 端）
            if self._use_compressed_prompt:
                self._game.add_human_message(
                    entity=entity,
                    message_content=chat_client.compressed_prompt,
                    add_status_effects_full_prompt=chat_client.prompt,
                )
            else:
                self._game.add_human_message(
                    entity=entity, message_content=chat_client.prompt
                )

            # 将 LLM 回复写入角色上下文（AI 端），完成本轮对话
            assert chat_client.response_ai_message is not None
            self._game.add_ai_message(
                entity=entity, ai_message=chat_client.response_ai_message
            )

            # 添加新效果到现有列表
            if format_response.add_effects:

                # 将新增效果的 source 字段设置为角色名称，便于后续追踪来源
                for effect in format_response.add_effects:
                    effect.source = entity.name

                # 追加新效果到 CombatStatusEffectsComponent
                combat_status_effects = entity.get(StatusEffectsComponent)
                combat_status_effects.status_effects.extend(format_response.add_effects)
                logger.debug(
                    f"[{entity.name}] 新增 {len(format_response.add_effects)} 个状态效果"
                )
                for effect in format_response.add_effects:
                    logger.info(
                        f"[{entity.name}] 新增效果: 「{effect.name}」 phase={effect.phase} duration={effect.duration}"
                    )

            else:
                logger.debug(f"[{entity.name}] 本回合无新增状态效果")

        except Exception as e:
            logger.error(f"[{entity.name}] 解析状态效果评估失败: {e}")
            logger.error(f"原始响应: {chat_client.response_content}")


#######################################################################################################################################
