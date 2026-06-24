"""仲裁后效果系统模块"""

from enum import StrEnum, unique
import random
from typing import Final, List, Set, final, Dict
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    Card,
    TargetType,
    CharacterStatsComponent,
    DungeonComponent,
    HandComponent,
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
# 塞牌位置策略枚举
@final
@unique
class CardInjectStrategy(StrEnum):
    """仲裁后塞牌位置策略"""

    APPEND = "append"  # 追加到手牌尾部（默认）
    RANDOM_INSERT = "random_insert"  # 随机插入到原有手牌队列中


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
def _build_actors_summary(game: TCGGame, actor_entities: Set[Entity]) -> str:
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

        final_stats = game.compute_character_stats(entity)

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
    game: TCGGame,
    actor_entities: Set[Entity],
    current_turn_actor_name: str,
    current_round_number: int,
) -> str:
    """生成压缩版仲裁后场景效果提示词（仅动态感知部分，省略静态规则/格式说明）"""

    actors_summary = _build_actors_summary(game, actor_entities)

    return f"""# 第 {current_round_number} 回合 — 仲裁后场景干预

**{current_turn_actor_name}** 刚刚完成出牌，仲裁结算已在上下文中记录。

## 场内存活角色当前状态

{actors_summary}"""


#######################################################################################################################################
def _generate_stage_post_arbitration_prompt(
    game: TCGGame,
    actor_entities: Set[Entity],
    current_turn_actor_name: str,
    current_round_number: int,
) -> str:
    """生成仲裁后场景效果提示词

    Args:
        actor_entities: 场内所有存活角色实体集合
        current_turn_actor_name: 本回合出牌者名称（当前行动角色）
        current_round_number: 当前回合数

    Returns:
        格式化的提示词字符串
    """

    actors_summary = _build_actors_summary(game, actor_entities)

    return f"""# 第 {current_round_number} 回合 — 仲裁后场景干预

**{current_turn_actor_name}** 刚刚完成出牌，仲裁结算已在上下文中记录。

## 场内存活角色当前状态

{actors_summary}

**干预原则**：
- ✅ 允许：上下文叙事中已描述的环境要素引发的物理后果（沙尘入眼、热浪灼烧、松软地面失稳、碎石可用、断柱可借力等）
- ✅ 塞牌须有据：只有上下文中描述了该物件存在于场景中，才能将其作为卡牌塞给角色使用
- ✅ 干预前先推断对象当前状态：从上下文叙事中判断场景对象处于何种状态（完好/部分损耗/已触发/已取走/仍可操作…），仅在该状态允许进一步交互时才将其转化为效果或卡牌
- ❌ 禁止：勇气、恐惧、神圣、复仇、祝福、诅咒等角色内在情绪或来源不明的魔法效果
- 不滥用：若上下文中无明显可利用的环境要素，**必须输出空数组**
- 状态效果与卡牌可同时施加于同一目标

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
        game: TCGGame,
        strategy: CardInjectStrategy = CardInjectStrategy.APPEND,
        use_compressed_prompt: bool = True,
    ) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game
        self._strategy: Final[CardInjectStrategy] = strategy
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
        if not self._game.current_dungeon.is_ongoing:
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

        actor_entities = self._game.get_alive_actors_in_stage(stage_entity)
        if not actor_entities:
            logger.debug("PostArbitrationActionSystem: 无存活角色，跳过")
            return

        current_round_number = len(self._game.current_dungeon.current_rounds or [])

        prompt = _generate_stage_post_arbitration_prompt(
            game=self._game,
            actor_entities=actor_entities,
            current_turn_actor_name=action.current_turn_actor_name,
            current_round_number=current_round_number,
        )

        compressed_message: str | None = None
        if self._use_compressed_prompt:
            compressed_message = _generate_compressed_stage_post_arbitration_prompt(
                game=self._game,
                actor_entities=actor_entities,
                current_turn_actor_name=action.current_turn_actor_name,
                current_round_number=current_round_number,
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
        await DeepSeekClient.batch_chat(clients=[chat_client])

        self._apply_response(stage_entity, chat_client)

    #######################################################################################################################################
    def _apply_response(
        self, stage_entity: Entity, chat_client: DeepSeekClient
    ) -> None:
        """解析 LLM 响应并应用状态效果与塞牌"""
        try:

            # 解析 LLM 响应为 StagePostArbitrationResponse
            response = StagePostArbitrationResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            # 预验证所有目标角色是否存在，避免部分指令生效导致的状态不一致
            for directive in response.per_actor:
                target_entity = self._game.get_entity_by_name(directive.target)
                if target_entity is None:
                    logger.warning(
                        f"[{stage_entity.name}] 找不到目标角色: {directive.target}，跳过"
                    )
                    raise ValueError(f"找不到目标角色: {directive.target}")

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
                    message_content=chat_client.compressed_prompt,
                    stage_post_arbitration_full_prompt=chat_client.prompt,
                )
            else:
                self._game.add_human_message(
                    entity=stage_entity,
                    message_content=chat_client.prompt,
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

        except Exception as e:
            logger.error(f"[{stage_entity.name}] 解析仲裁后干预响应失败: {e}")
            logger.error(f"原始响应: {chat_client.response_content}")

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

        if self._strategy == CardInjectStrategy.RANDOM_INSERT:
            for card in new_cards:
                insert_pos = random.randint(0, len(hand_comp.cards))
                hand_comp.cards.insert(insert_pos, card)
        else:  # APPEND
            hand_comp.cards = hand_comp.cards + new_cards

        logger.debug(
            f"[{stage_entity.name}] → [{directive.target}] "
            f"塞入 {len(new_cards)} 张卡牌"
        )


#######################################################################################################################################
