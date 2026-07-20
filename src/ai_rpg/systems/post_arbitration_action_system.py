"""仲裁后效果系统模块"""

from typing import Final, List, Optional, Set, final, Dict
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..game.dbg_combat_processor import get_alive_actors_in_stage
from ..game.dbg_combat_processor import compute_character_stats
from ..models import (
    Card,
    TargetType,
    CharacterStatsComponent,
    DungeonComponent,
    HandComponent,
    HumanMessage,
    StageComponent,
    PostArbitrationAction,
    StatusEffect,
    PhaseType,
    StatusEffectsComponent,
)
from ..utils import extract_json_from_code_block
from .arbitration_prompt_builders import fmt_duration
from .card_prompt_builders import build_card_field_description
from .status_effect_prompt_builders import build_status_effect_field_description


#######################################################################################################################################
@final
class ActorPostArbitrationDirective(BaseModel):
    """单个角色的仲裁后指令"""

    target: str  # 目标角色名称
    add_effects: List[StatusEffect] = []  # 追加的状态效果
    inject_cards: List[Card] = []  # 注入到手牌的卡牌


#######################################################################################################################################
@final
class StagePostArbitrationResponse(BaseModel):
    """仲裁后场景效果响应"""

    per_actor: List[ActorPostArbitrationDirective] = []  # 每个被影响角色的指令


#######################################################################################################################################
def _build_actors_summary(game: DBGGame, actor_entities: Set[Entity]) -> str:
    """格式化场内存活角色状态摘要，供 prompt 函数复用。"""
    actor_lines: List[str] = []
    for entity in actor_entities:

        assert entity.has(
            CharacterStatsComponent
        ), f"角色 {entity.name} 缺少 CharacterStatsComponent"
        assert entity.has(
            StatusEffectsComponent
        ), f"角色 {entity.name} 缺少 StatusEffectsComponent"
        assert entity.has(HandComponent), f"角色 {entity.name} 缺少 HandComponent"

        final_stats = compute_character_stats(entity)

        effects_comp = entity.get(StatusEffectsComponent)

        hp_str = f"HP: {final_stats.hp}/{final_stats.max_hp}"

        if len(effects_comp.status_effects) > 0:
            effects_str = "、".join(
                f"{e.name}（{fmt_duration(e.duration)}）"
                for e in effects_comp.status_effects
            )
        else:
            effects_str = "无"

        actor_lines.append(
            f"- **{entity.name}**  {hp_str}  " f"状态效果: {effects_str}"
        )
    return "\n".join(actor_lines) if actor_lines else "  （无存活角色）"


#######################################################################################################################################
def _generate_compressed_stage_post_arbitration_prompt(
    game: DBGGame,
    actor_entities: Set[Entity],
    current_turn_actor_name: str,
    current_round_number: int,
    interaction_summary: str,
) -> str:
    """生成压缩版仲裁后场景效果提示词（仅动态感知部分，省略静态规则/格式说明）"""

    actors_summary = _build_actors_summary(game, actor_entities)

    return f"""# 第 {current_round_number} 回合 — 仲裁后场景干预

**{current_turn_actor_name}** 刚刚完成出牌，仲裁结算已在上下文中记录。

## 本次触发依据（仲裁阶段提取的场景交互摘要）

{interaction_summary}

## 场内存活角色当前状态

{actors_summary}"""


#######################################################################################################################################
def _generate_stage_post_arbitration_prompt(
    game: DBGGame,
    actor_entities: Set[Entity],
    current_turn_actor_name: str,
    current_round_number: int,
    interaction_summary: str,
) -> str:
    """生成仲裁后场景效果提示词

    Args:
        actor_entities: 场内所有存活角色实体集合
        current_turn_actor_name: 本回合出牌者名称（当前行动角色）
        current_round_number: 当前回合数
        interaction_summary: 仲裁阶段提取的场景交互摘要，作为本次干预的明确依据

    Returns:
        格式化的提示词字符串
    """

    actors_summary = _build_actors_summary(game, actor_entities)

    return f"""# 第 {current_round_number} 回合 — 仲裁后场景干预

**{current_turn_actor_name}** 刚刚完成出牌，仲裁结算已在上下文中记录。

## 本次触发依据（仲裁阶段提取的场景交互摘要）

{interaction_summary}

## 场内存活角色当前状态

{actors_summary}

**干预原则**：
- ✅ 塞牌/加状态效果均须有据：仅可将上下文叙事中已明确描述的环境要素（沙尘入眼、热浪灼烧、松软地面失稳、碎石可用、断柱可借力等）转化为卡牌或状态效果，不得凭空引入场景中未出现的物件
- ✅ 干预前先推断该物件当前状态（完好/部分损耗/已触发/已取走/仍可操作…），仅状态允许进一步交互时才可转化；若当前不可用，需在 `description` 中体现，并将对应卡牌的 `playable` 设为 `false`
- ❌ 禁止：勇气、恐惧、神圣、复仇、祝福、诅咒等角色内在情绪或来源不明的魔法效果
- 不滥用：若无明显可利用的环境要素，**必须输出空数组**；状态效果与卡牌可同时施加于同一目标
- 塞牌字段（`inject_cards`）：`exhaust` 通常设为 `true`（一次性机遇，用后不再出现）；`cost` 由你自行判断，轻微动作（如随手投掷碎石）可设为 0，需专注/耗时的复杂互动可设为 1 或更高

{build_status_effect_field_description()}

{build_card_field_description()}

## 输出格式

`source` 字段由系统自动设置，无需填写。

```json
{{
  "per_actor": [
    {{
      "target": "角色名称",
      "add_effects": [
        {{
          "name": "沙尘入眼",
          "description": "战斗搅起的沙尘钻入眼中，视线模糊，造成伤害减少",
          "duration": 2,
          "phase": "{PhaseType.ARBITRATION}",
          "speed": 0,
          "defense": 0,
          "counter": 0
        }}
      ],
      "inject_cards": [
        {{
          "name": "碎柱投掷",
          "description": "抓起地面的断柱碎块用力掷向对方，造成钝击伤害",
          "affixes": [],
          "modifiers": [],
          "playable": true,
          "exhaust": true,
          "cost": 0,
          "damage_dealt": 2,
          "energy_delta": 0,
          "hit_count": 1,
          "target_type": "{TargetType.ENEMY_SINGLE}"
        }}
      ]
    }}
  ]
}}
```

**无干预时输出空的 per_actor 数组，只输出 JSON。**"""


#######################################################################################################################################
@final
class PostArbitrationActionSystem(ReactiveProcessor):
    """仲裁后效果系统"""

    def __init__(
        self,
        game: DBGGame,
        use_compressed_prompt: bool = True,
    ) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game
        self._use_compressed_prompt: Final[bool] = use_compressed_prompt

    #######################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(PostArbitrationAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(PostArbitrationAction)
            and entity.has(StageComponent)
            and entity.has(DungeonComponent)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        if not self._game.current_combat_room.combat.is_ongoing:
            logger.debug("PostArbitrationActionSystem: 战斗未进行中，跳过")
            return

        logger.debug("PostArbitrationActionSystem: 处理仲裁后效果动作")
        for stage_entity in entities:
            await self._process_stage(stage_entity)

    #######################################################################################################################################
    async def _process_stage(self, stage_entity: Entity) -> None:
        """为单个 stage entity 执行仲裁后场景干预逻辑"""

        action = stage_entity.get(PostArbitrationAction)
        assert (
            action is not None
        ), "PostArbitrationActionSystem: 无法获取 PostArbitrationAction 组件！"

        actor_entities = get_alive_actors_in_stage(self._game, stage_entity)
        if not actor_entities:
            logger.debug("PostArbitrationActionSystem: 无存活角色，跳过")
            return

        current_round_number = len(self._game.current_combat_room.combat.rounds or [])

        prompt = _generate_stage_post_arbitration_prompt(
            game=self._game,
            actor_entities=actor_entities,
            current_turn_actor_name=action.current_turn_actor_name,
            current_round_number=current_round_number,
            interaction_summary=action.interaction_summary,
        )

        compressed_message: Optional[str] = None
        if self._use_compressed_prompt:
            compressed_message = _generate_compressed_stage_post_arbitration_prompt(
                game=self._game,
                actor_entities=actor_entities,
                current_turn_actor_name=action.current_turn_actor_name,
                current_round_number=current_round_number,
                interaction_summary=action.interaction_summary,
            )

        chat_client = DeepSeekClient(
            name=stage_entity.name,
            prompt=prompt,
            compressed_prompt=compressed_message,
            context=self._game.get_agent_context(stage_entity).context,
        )

        logger.debug(
            f"PostArbitrationActionSystem: [{stage_entity.name}] 进行仲裁后干预评估"
        )

        # 发起 LLM 请求，捕获异常以防止整个流程崩溃
        try:
            await chat_client.chat()
        except Exception as e:
            logger.error(
                f"PostArbitrationActionSystem: [{stage_entity.name}] LLM 请求失败: {e}"
            )
            return

        if chat_client.response_ai_message is None:
            logger.warning(
                f"PostArbitrationActionSystem: [{stage_entity.name}] LLM 响应为空，跳过"
            )
            return

        self._apply_response(chat_client)

    #######################################################################################################################################
    def _apply_response(self, chat_client: DeepSeekClient) -> None:
        """解析 LLM 响应并应用状态效果与塞牌"""

        stage_entity = self._game.get_entity_by_name(chat_client.name)
        assert stage_entity is not None, f"找不到舞台实体: {chat_client.name}"

        if chat_client.response_ai_message is None:
            logger.warning(
                f"PostArbitrationActionSystem: [{chat_client.name}] LLM 响应为空，跳过"
            )
            return

        try:

            # 解析 LLM 响应为 StagePostArbitrationResponse
            response = StagePostArbitrationResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

        except Exception as e:
            logger.error(f"[{stage_entity.name}] 解析仲裁后干预响应失败: {e}")
            logger.error(f"原始响应: {chat_client.response_content}")
            return

        # 预验证所有目标角色是否存在，避免部分指令生效导致的状态不一致
        for directive in response.per_actor:
            target_entity = self._game.get_entity_by_name(directive.target)
            if target_entity is None:
                logger.warning(
                    f"[{stage_entity.name}] 找不到目标角色: {directive.target}，跳过"
                )
                return

            assert target_entity.has(
                StatusEffectsComponent
            ), f"目标角色 {directive.target} 缺少 StatusEffectsComponent"
            assert target_entity.has(
                HandComponent
            ), f"目标角色 {directive.target} 缺少 HandComponent"

        # 添加上下文消息到 stage entity 的对话历史，便于后续回顾与调试
        if self._use_compressed_prompt:
            self._game.add_human_message(
                entity=stage_entity,
                human_message=HumanMessage(
                    content=chat_client.compressed_prompt,
                    stage_post_arbitration_full_prompt=chat_client.prompt,
                ),
            )
        else:
            self._game.add_human_message(
                entity=stage_entity,
                human_message=HumanMessage(content=chat_client.prompt),
            )

        # 添加 LLM 响应消息到 stage entity 的对话历史
        assert chat_client.response_ai_message is not None
        self._game.add_ai_message(
            entity=stage_entity,
            ai_message=chat_client.response_ai_message,
        )

        # 解析每个角色的指令，应用状态效果与塞牌
        if not response.per_actor:
            logger.debug(f"[{stage_entity.name}] 仲裁后无干预指令")
            return

        for directive in response.per_actor:
            target_entity = self._game.get_entity_by_name(directive.target)
            assert (
                target_entity is not None
            ), f"预验证阶段未发现目标角色: {directive.target}"

            if directive.add_effects:
                self._apply_status_effects(stage_entity, target_entity, directive)

            if directive.inject_cards:
                self._inject_cards(stage_entity, target_entity, directive)

    #######################################################################################################################################
    def _apply_status_effects(
        self,
        stage_entity: Entity,
        target_entity: Entity,
        directive: ActorPostArbitrationDirective,
    ) -> None:
        """追加状态效果到目标实体，跳过已存在同名效果"""

        for effect in directive.add_effects:
            effect.source = stage_entity.name

        assert target_entity.has(
            StatusEffectsComponent
        ), f"目标角色 {directive.target} 缺少 StatusEffectsComponent"

        effects_comp = target_entity.get(StatusEffectsComponent)
        existing_effect_names = {e.name for e in effects_comp.status_effects}
        new_effects = []
        for effect in directive.add_effects:
            if effect.name in existing_effect_names:
                logger.debug(
                    f"[{stage_entity.name}] → [{directive.target}] "
                    f'状态效果 "{effect.name}" 已存在，放弃追加'
                )
            else:
                new_effects.append(effect)

        if new_effects:
            effects_comp.status_effects.extend(new_effects)
            logger.debug(
                f"[{stage_entity.name}] → [{directive.target}] "
                f"追加 {len(new_effects)} 个状态效果"
            )

    #######################################################################################################################################
    def _inject_cards(
        self,
        stage_entity: Entity,
        target_entity: Entity,
        directive: ActorPostArbitrationDirective,
    ) -> None:
        """向目标实体手牌注入卡牌，跳过已存在同名卡牌"""

        assert target_entity.has(
            HandComponent
        ), f"目标角色 {directive.target} 缺少 HandComponent"

        hand_comp = target_entity.get(HandComponent)
        for card in directive.inject_cards:
            card.source = stage_entity.name

        existing_card_names = {c.name for c in hand_comp.cards}
        new_cards = []
        for card in directive.inject_cards:
            if card.name in existing_card_names:
                logger.debug(
                    f"[{stage_entity.name}] → [{directive.target}] "
                    f'卡牌 "{card.name}" 已在手牌中，放弃塞入'
                )
            else:
                new_cards.append(card)

        if not new_cards:
            return

        # 将新的卡牌追加到手牌中
        hand_comp.cards = hand_comp.cards + new_cards
        logger.debug(
            f"[{stage_entity.name}] → [{directive.target}] "
            f"塞入 {len(new_cards)} 张卡牌"
        )


#######################################################################################################################################
