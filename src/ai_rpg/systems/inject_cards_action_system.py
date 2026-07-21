"""场景塞牌系统模块"""

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
    DiscardPileComponent,
    HumanMessage,
    PlayCardsAction,
    UseConsumableItemAction,
    UseGearItemAction,
    StatusEffectsComponent,
)
from ..utils import extract_json_from_code_block
from .arbitration_prompt_builders import fmt_duration
from .card_prompt_builders import build_card_field_description


#######################################################################################################################################
@final
class ActorPostArbitrationDirective(BaseModel):
    """单个角色的仲裁后指令"""

    target: str  # 目标角色名称
    inject_cards: List[Card] = []  # 注入到弃牌堆的卡牌


#######################################################################################################################################
@final
class StagePostArbitrationResponse(BaseModel):
    """仲裁后场景效果响应"""

    per_actor: List[ActorPostArbitrationDirective] = []  # 每个被影响角色的指令


#######################################################################################################################################
def _build_actors_summary(actor_entities: Set[Entity]) -> str:
    """格式化场内存活角色状态摘要，供 prompt 函数复用。"""
    actor_lines: List[str] = []

    for entity in actor_entities:

        assert entity.has(
            CharacterStatsComponent
        ), f"角色 {entity.name} 缺少 CharacterStatsComponent"
        assert entity.has(
            StatusEffectsComponent
        ), f"角色 {entity.name} 缺少 StatusEffectsComponent"

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

    #
    return "\n".join(actor_lines) if actor_lines else "  （无存活角色）"


#######################################################################################################################################
def _generate_compressed_inject_cards_prompt(
    actor_entities: Set[Entity],
    current_round_number: int,
) -> str:
    """生成压缩版塞牌评估提示词（仅动态感知部分，省略静态规则/格式说明）"""

    actors_summary = _build_actors_summary(actor_entities)

    return f"""# 第 {current_round_number} 回合 — 场景塞牌评估

请回顾你在上文刚记录的本回合战斗演出（叙事与仲裁结果），判断是否需要触发场景塞牌。

## 场内存活角色当前状态

{actors_summary}"""


#######################################################################################################################################
def _generate_inject_cards_prompt(
    actor_entities: Set[Entity],
    current_round_number: int,
) -> str:
    """生成塞牌评估提示词"""

    actors_summary = _build_actors_summary(actor_entities)

    return f"""# 第 {current_round_number} 回合 — 场景塞牌评估

请回顾你在上文刚记录的本回合战斗演出（叙事与仲裁结果），判断是否需要触发场景塞牌。

## 场内存活角色当前状态

{actors_summary}

**干预原则**：

- ✅ 塞牌须有据：仅可将上下文叙事中已明确描述的环境要素（沙尘入眼、热浪灼烧、松软地面失稳、碎石可用、断柱可借力等）转化为卡牌，不得凭空引入场景中未出现的物件
- ✅ 干预前先推断该物件当前状态（完好/部分损耗/已触发/已取走/仍可操作…），仅状态允许进一步交互时才可转化；若当前不可用，需在 `description` 中体现，并将对应卡牌的 `playable` 设为 `false`
- ❌ 禁止：无中生有的卡牌（即与环境交互无关、纯粹基于角色内在情绪/能力的卡牌）
- 不滥用：若无明显可利用的环境要素，**必须输出空数组**
- 塞牌字段（`inject_cards`）：`exhaust` 通常设为 `true`（一次性机遇，用后不再出现）；`cost` 由你自行判断，轻微动作（如随手投掷碎石）可设为 0，需专注/耗时的复杂互动可设为 1 或更高

{build_card_field_description()}

## 输出格式

`source` 字段由系统自动设置，无需填写。

```json
{{
  "per_actor": [
    {{
      "target": "角色名称",
      "inject_cards": [
        {{
          "name": "碎柱投掷",
          "description": "抓起地面的断柱碎块用力掷向对方，造成钝击伤害",
          "affixes": [],
          "modifiers": ["无视防御:本次攻击无视目标防御"],
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

（`affixes`/`modifiers` 无内容时输出 `[]`；有内容时数组元素必须是如上示例的字符串，禁止输出对象）

**无干预时输出空的 per_actor 数组，只输出 JSON。**"""


#######################################################################################################################################
@final
class InjectCardsActionSystem(ReactiveProcessor):
    """场景塞牌系统：响应 PlayCardsAction / UseConsumableItemAction / UseGearItemAction 事件，

    在对应的仲裁系统结算完毕后（同一帧内，依赖流水线中的注册顺序），复用 stage 已被更新的对话
    上下文（其中已包含本次行动的仲裁叙事），由 stage agent 判断是否需要向场内角色塞入场景卡牌。
    """

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
        return {
            Matcher(PlayCardsAction): GroupEvent.ADDED,
            Matcher(UseConsumableItemAction): GroupEvent.ADDED,
            Matcher(UseGearItemAction): GroupEvent.ADDED,
        }

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(PlayCardsAction)
            or entity.has(UseConsumableItemAction)
            or entity.has(UseGearItemAction)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        if not self._game.current_combat_room.combat.is_ongoing:
            logger.debug("InjectCardsActionSystem: 战斗未进行中，跳过")
            return

        logger.debug(f"InjectCardsActionSystem: 处理 {len(entities)} 个行动实体")
        for actor_entity in entities:
            await self._process_actor_action(actor_entity)

    #######################################################################################################################################
    async def _process_actor_action(self, actor_entity: Entity) -> None:
        """为单次行动（出牌/使用消耗品/使用装备）执行场景塞牌评估"""

        stage_entity = self._game.resolve_stage_entity(actor_entity)
        assert (
            stage_entity is not None
        ), f"InjectCardsActionSystem: 无法获取 {actor_entity.name} 所在场景实体！"

        actor_entities = get_alive_actors_in_stage(self._game, stage_entity)
        if not actor_entities:
            logger.debug("InjectCardsActionSystem: 无存活角色，跳过")
            return

        current_round_number = len(self._game.current_combat_room.combat.rounds or [])

        prompt = _generate_inject_cards_prompt(
            actor_entities=actor_entities,
            current_round_number=current_round_number,
        )

        compressed_message: Optional[str] = None
        if self._use_compressed_prompt:
            compressed_message = _generate_compressed_inject_cards_prompt(
                actor_entities=actor_entities,
                current_round_number=current_round_number,
            )

        chat_client = DeepSeekClient(
            name=stage_entity.name,
            prompt=prompt,
            compressed_prompt=compressed_message,
            context=self._game.get_agent_context(stage_entity).context,
        )

        logger.debug(f"InjectCardsActionSystem: [{stage_entity.name}] 进行场景塞牌评估")

        # 发起 LLM 请求，捕获异常以防止整个流程崩溃
        try:
            await chat_client.chat()
        except Exception as e:
            logger.error(
                f"InjectCardsActionSystem: [{stage_entity.name}] LLM 请求失败: {e}"
            )
            return

        if chat_client.response_ai_message is None:
            logger.warning(
                f"InjectCardsActionSystem: [{stage_entity.name}] LLM 响应为空，跳过"
            )
            return

        self._apply_response(chat_client)

    #######################################################################################################################################
    def _apply_response(self, chat_client: DeepSeekClient) -> None:
        """解析 LLM 响应并应用塞牌"""

        stage_entity = self._game.get_entity_by_name(chat_client.name)
        assert stage_entity is not None, f"找不到舞台实体: {chat_client.name}"

        if chat_client.response_ai_message is None:
            logger.warning(
                f"InjectCardsActionSystem: [{chat_client.name}] LLM 响应为空，跳过"
            )
            return

        try:

            # 解析 LLM 响应为 StagePostArbitrationResponse
            response = StagePostArbitrationResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            # 预验证所有目标角色是否存在，避免部分指令生效导致的状态不一致
            for directive in response.per_actor:
                target_entity = self._game.get_entity_by_name(directive.target)
                if target_entity is None:
                    raise ValueError(f"预验证阶段未发现目标角色: {directive.target}")

                assert target_entity.has(
                    DiscardPileComponent
                ), f"目标角色 {directive.target} 缺少 DiscardPileComponent"

        except Exception as e:
            logger.error(f"[{stage_entity.name}] 解析场景塞牌响应失败: {e}")
            logger.error(f"原始响应: {chat_client.response_content}")
            return

        # 添加上下文消息到 stage entity 的对话历史，便于后续回顾与调试
        if self._use_compressed_prompt:
            self._game.add_human_message(
                entity=stage_entity,
                human_message=HumanMessage(
                    content=chat_client.compressed_prompt,
                    inject_cards_full_prompt=chat_client.prompt,
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

        # 解析每个角色的指令，应用塞牌
        if response.per_actor:
            for directive in response.per_actor:
                target_entity = self._game.get_entity_by_name(directive.target)
                assert (
                    target_entity is not None
                ), f"预验证阶段未发现目标角色: {directive.target}"

                # 干预性：插牌
                if directive.inject_cards:
                    self._inject_cards(
                        stage_entity,
                        target_entity,
                        inject_cards=directive.inject_cards,
                    )
        else:
            logger.debug(f"[{stage_entity.name}] 本次评估无塞牌指令")

    #######################################################################################################################################
    def _inject_cards(
        self,
        stage_entity: Entity,
        target_entity: Entity,
        inject_cards: List[Card],
    ) -> None:
        """向目标实体弃牌堆注入卡牌，跳过已存在同名卡牌"""

        assert target_entity.has(
            DiscardPileComponent
        ), f"目标角色 {target_entity.name} 缺少 DiscardPileComponent"

        discard_pile_comp = target_entity.get(DiscardPileComponent)
        for card in inject_cards:
            card.source = stage_entity.name

        existing_card_names = {c.name for c in discard_pile_comp.cards}
        new_cards = []
        for card in inject_cards:
            if card.name in existing_card_names:
                logger.debug(
                    f"[{stage_entity.name}] → [{target_entity.name}] "
                    f'卡牌 "{card.name}" 已在弃牌堆中，放弃塞入'
                )
            else:
                new_cards.append(card)

        if not new_cards:
            return

        # 将新的卡牌追加到弃牌堆中
        discard_pile_comp.cards = discard_pile_comp.cards + new_cards
        logger.debug(
            f"[{stage_entity.name}] → [{target_entity.name}] "
            f"塞入 {len(new_cards)} 张卡牌至弃牌堆"
        )


#######################################################################################################################################
