"""仲裁后场景效果系统模块

在每次 ArbitrationActionSystem 完成真实仲裁结算后触发，由 combat stage 的 LLM agent
（地牢主视角）决定是否对场内存活角色追加状态效果或塞入特殊卡牌。

执行时机：
- 监听 StagePostArbitrationAction.ADDED（ReactiveProcessor）
- 由 ArbitrationActionSystem._apply_arbitration_result 在结算成功后添加到 stage entity
- 仅在战斗进行中时触发（is_ongoing 守卫）
"""

from enum import StrEnum, unique
import random
from typing import Final, List, Set, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..chat_client.client import ChatClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    BlockComponent,
    Card,
    CardTargetType,
    CharacterStatsComponent,
    DungeonComponent,
    HandComponent,
    StageComponent,
    StagePostArbitrationAction,
    StatusEffect,
    StatusEffectPhase,
    StatusEffectsComponent,
)
from ..utils import extract_json_from_code_block


###############################################################################################################################################
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
def _fmt_duration(d: int) -> str:
    return "永久" if d == -1 else f"剩余{d}回合"


def _generate_stage_post_arbitration_prompt(
    actor_entities: Set[Entity],
    actor_name: str,
    current_round_number: int,
) -> str:
    """生成仲裁后场景效果提示词

    要求 stage agent 以地牢主视角，在仲裁结算后决定是否对场内角色施加新效果或塞牌。
    仲裁结算的完整内容（combat_log/narrative）已在 stage agent 的上下文中，无需重复传入。

    Args:
        actor_entities: 场内所有存活角色实体集合
        actor_name: 本次仲裁的出牌者名称
        current_round_number: 当前回合数

    Returns:
        格式化的提示词字符串
    """

    # 格式化存活角色状态
    actor_lines: List[str] = []
    for entity in actor_entities:
        stats_comp = entity.get(CharacterStatsComponent)
        block_comp = entity.get(BlockComponent)
        effects_comp = entity.get(StatusEffectsComponent)

        hp_str = (
            f"HP: {stats_comp.stats.hp}/{stats_comp.stats.max_hp}"
            if stats_comp is not None
            else "HP: ?"
        )
        block_str = f"格挡: {block_comp.block}" if block_comp is not None else "格挡: 0"

        if effects_comp is not None and effects_comp.status_effects:
            effects_str = "、".join(
                f"{e.name}（{_fmt_duration(e.duration)}）"
                for e in effects_comp.status_effects
            )
        else:
            effects_str = "无"

        has_hand = entity.has(HandComponent)
        hand_note = (
            "（当前持有手牌，可塞牌）" if has_hand else "（本回合无手牌，塞牌无效）"
        )
        actor_lines.append(
            f"- **{entity.name}**  {hp_str}  {block_str}  "
            f"状态效果: {effects_str}  {hand_note}"
        )

    actors_summary = "\n".join(actor_lines) if actor_lines else "  （无存活角色）"

    phase_desc = f"""
## 状态效果字段说明

每个状态效果必须指定 `phase` 字段，决定生效阶段与可影响属性：

| phase | 对应阶段 | 可影响属性 | 典型效果举例 |
|---|---|---|---|
| `{StatusEffectPhase.DRAW}` | 抽牌阶段 | attack、defense（间接影响下回合卡牌数值） | 「虚弱」攻击力−2，生成卡牌 damage_dealt 偏低；「迟重」防御力−1，block_gain 偏低 |
| `{StatusEffectPhase.PLAY}` | 出牌阶段 | damage_dealt、block_gain（附加到本回合打出的牌） | 「淬毒」出牌时 damage_dealt+2；「护盾祝福」出牌时 block_gain+2 |
| `{StatusEffectPhase.ARBITRATION}` | 仲裁结算阶段 | hp、damage_dealt、block_gain | 「燃烧」每回合结算扣 hp 3；「黑暗腐蚀」造成伤害+4；「坚甲赐福」格挡+3 |

**属性约束**：
- 禁止修改 max_hp
- `{StatusEffectPhase.DRAW}` 阶段用 attack / defense 描述，不直接写 damage_dealt / block_gain
- `{StatusEffectPhase.ARBITRATION}` 阶段直接用 hp / damage_dealt / block_gain，不用 attack / defense
- description 须引用上下文中实际存在的场景要素，第三人称描述环境如何作用于角色身体，如"战斗搅起的沙尘钻入眼中，视线模糊，造成伤害减少"

绝大多数惩罚/增益效果选 `{StatusEffectPhase.ARBITRATION}`。"""

    card_field_desc = f"""
## 塞牌字段说明

塞入的卡牌会被加入目标的当前手牌；数值应与场内角色血量及战斗烈度相匹配。

| 字段 | 说明 |
|---|---|
| name | 卡牌名称（<8字），体现效果意图 |
| description | 第三人称，描述角色借助**上下文中已存在的**场景具体物件的客观动作（1句，如"抓起地面的断柱碎块掷向对方"）；不可凭空引入非场景物件 |
| damage_dealt | 单次命中造成的伤害（整数；攻击类取合理正值，无伤害取 0） |
| block_gain | 本张牌提供的格挡（整数；防御类取合理正值，无格挡取 0） |
| hit_count | 攻击次数（默认 1；多段攻击可设 2~4，每段独立抵挡目标格挡） |
| target_type | 出牌目标类型（见下表） |

| target_type | 含义 |
|---|---|
| `{CardTargetType.ENEMY_SINGLE}` | 攻击单体敌方（默认） |
| `{CardTargetType.ENEMY_ALL}` | 攻击全体敌方 |
| `{CardTargetType.ALLY_SINGLE}` | 治疗/增益单体友方 |
| `{CardTargetType.ALLY_ALL}` | 治疗/增益全体友方 |
| `{CardTargetType.SELF_ONLY}` | 仅作用于自身（防御、自损诅咒等） |

**注意**：damage_dealt 与 block_gain 不得同时为 0；只有当前持有手牌的角色才能被塞牌。"""

    return f"""# 第 {current_round_number} 回合 — 仲裁后场景干预

**{actor_name}** 刚刚完成出牌，仲裁结算已在上下文中记录。

## 场内存活角色当前状态

{actors_summary}

## 你的本质与职责

你是这片场景本身，没有意志，没有偏好，只有物理现实在运作。
你能做的，是将**上下文中已出现、已存在于this场景里的环境要素**，转化为对角色身体的客观影响，或为角色提供可借用的场景物件。

**干预原则**：
- ✅ 允许：上下文叙事中已描述的环境要素引发的物理后果（沙尘入眼、热浪灼烧、松软地面失稳、碎石可用、断柱可借力等）
- ✅ 塞牌须有据：只有上下文中描述了该物件存在于场景中，才能将其作为卡牌塞给角色使用
- ❌ 禁止：勇气、恐惧、神圣、复仇、祝福、诅咒等角色内在情绪或来源不明的魔法效果
- ❌ 禁止：凭空塞入武器或装备（除非场景叙事中明确描述了该物件）
- 不滥用：若上下文中无明显可利用的环境要素，**必须输出空数组**
- 状态效果与卡牌可同时施加于同一目标
{phase_desc}
{card_field_desc}

**description 规范**：
- 状态效果 description：第三人称，描述环境要素如何作用于角色身体（如："沙尘被战斗扰动卷入眼中，视线受阻，造成伤害减少"）
- 塞牌 description：第三人称，描述角色借助场景具体物件的客观动作（如："抓起地面裸露的岩板碎片朝对方投出"），不绑定具体场景名词，使描述通用可复用

**注意**：`source` 字段由系统自动设置，无需在 JSON 中填写。

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
          "phase": "{StatusEffectPhase.ARBITRATION}"
        }}
      ],
      "inject_cards": [
        {{
          "name": "碎柱投掷",
          "description": "抓起地面的断柱碎块用力掷向对方，造成钝击伤害",
          "damage_dealt": 2,
          "block_gain": 0,
          "hit_count": 1,
          "target_type": "{CardTargetType.ENEMY_SINGLE}"
        }}
      ]
    }}
  ]
}}
```

无干预时输出空的 per_actor 数组，只输出JSON。"""


#######################################################################################################################################
@final
class StagePostArbitrationActionSystem(ReactiveProcessor):
    """仲裁后场景效果系统

    监听 StagePostArbitrationAction.ADDED，由 combat stage 的 LLM agent（地牢主视角）
    决定是否对场内存活角色追加状态效果或塞入卡牌。

    执行机制：
    - 监听 StagePostArbitrationAction.ADDED（ReactiveProcessor）
    - 由 ArbitrationActionSystem 在每次真实仲裁结算成功后触发
    - 仅在战斗进行中时触发（is_ongoing 守卫）

    执行条件：
    - 战斗状态为 ONGOING（is_ongoing=True）
    - stage entity 具有 StageComponent + DungeonComponent

    塞牌策略：
    - APPEND（默认）：注入卡牌追加到手牌尾部
    - RANDOM_INSERT：每张注入卡牌随机插入到原有手牌队列中
    """

    def __init__(
        self,
        game: TCGGame,
        strategy: CardInjectStrategy = CardInjectStrategy.APPEND,
    ) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game
        self._strategy: Final[CardInjectStrategy] = strategy

    #######################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(StagePostArbitrationAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(StagePostArbitrationAction)
            and entity.has(StageComponent)
            and entity.has(DungeonComponent)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        if not self._game.current_dungeon.is_ongoing:
            logger.debug("StagePostArbitrationActionSystem: 战斗未进行中，跳过")
            return

        for stage_entity in entities:
            await self._process_stage(stage_entity)

    #######################################################################################################################################
    async def _process_stage(self, stage_entity: Entity) -> None:
        """为单个 stage entity 执行仲裁后场景干预逻辑"""

        action = stage_entity.get(StagePostArbitrationAction)
        assert (
            action is not None
        ), "StagePostArbitrationActionSystem: 无法获取 StagePostArbitrationAction 组件！"

        player_entity = self._game.get_player_entity()
        assert (
            player_entity is not None
        ), "StagePostArbitrationActionSystem: 无法找到玩家实体！"

        actor_entities = self._game.get_alive_actors_in_stage(player_entity)
        if not actor_entities:
            logger.debug("StagePostArbitrationActionSystem: 无存活角色，跳过")
            return

        current_round_number = len(self._game.current_dungeon.current_rounds or [])

        prompt = _generate_stage_post_arbitration_prompt(
            actor_entities=actor_entities,
            actor_name=action.actor_name,
            current_round_number=current_round_number,
        )

        chat_client = ChatClient(
            name=stage_entity.name,
            prompt=prompt,
            context=self._game.get_agent_context(stage_entity).context,
        )

        logger.debug(
            f"StagePostArbitrationActionSystem: [{stage_entity.name}] 进行仲裁后干预评估"
        )
        await ChatClient.batch_chat(clients=[chat_client])

        self._apply_response(stage_entity, chat_client)

    #######################################################################################################################################
    def _apply_response(self, stage_entity: Entity, chat_client: ChatClient) -> None:
        """解析 LLM 响应并应用状态效果与塞牌"""

        try:
            json_content = extract_json_from_code_block(chat_client.response_content)
            response = StagePostArbitrationResponse.model_validate_json(json_content)

            self._game.add_human_message(
                entity=stage_entity,
                message_content=chat_client.prompt,
            )
            self._game.add_ai_message(
                entity=stage_entity,
                ai_messages=chat_client.response_ai_messages,
            )

            if not response.per_actor:
                logger.debug(f"[{stage_entity.name}] 仲裁后无干预指令")
                return

            for directive in response.per_actor:
                target_entity = self._game.get_entity_by_name(directive.target)
                if target_entity is None:
                    logger.warning(
                        f"[{stage_entity.name}] 找不到目标角色: {directive.target}，跳过"
                    )
                    continue

                # 追加状态效果
                if directive.add_effects:

                    # 将新增效果的 source 字段设置为 stage entity 名称，便于后续追踪来源
                    for effect in directive.add_effects:
                        effect.source = stage_entity.name

                    # 追加状态效果到目标实体的 StatusEffectsComponent
                    if target_entity.has(StatusEffectsComponent):
                        effects_comp = target_entity.get(StatusEffectsComponent)
                        effects_comp.status_effects.extend(directive.add_effects)
                        logger.debug(
                            f"[{stage_entity.name}] → [{directive.target}] "
                            f"追加 {len(directive.add_effects)} 个状态效果"
                        )
                    else:
                        logger.warning(
                            f"[{directive.target}] 缺少 StatusEffectsComponent，跳过状态效果追加"
                        )

                # 塞牌（仅当目标当前持有手牌时生效）
                if directive.inject_cards:
                    if target_entity.has(HandComponent):

                        hand_comp = target_entity.get(HandComponent)
                        # 将注入卡牌的 source 字段设置为 stage entity 名称
                        for card in directive.inject_cards:
                            card.source = stage_entity.name

                        # 根据策略决定注入卡牌的插入位置
                        if self._strategy == CardInjectStrategy.RANDOM_INSERT:
                            for card in directive.inject_cards:
                                insert_pos = random.randint(0, len(hand_comp.cards))
                                hand_comp.cards.insert(insert_pos, card)
                        else:  # APPEND
                            hand_comp.cards = hand_comp.cards + directive.inject_cards

                        logger.debug(
                            f"[{stage_entity.name}] → [{directive.target}] "
                            f"塞入 {len(directive.inject_cards)} 张卡牌"
                        )
                    else:
                        logger.debug(f"[{directive.target}] 当前无手牌，跳过塞牌")

        except Exception as e:
            logger.error(f"[{stage_entity.name}] 解析仲裁后干预响应失败: {e}")
            logger.error(f"原始响应: {chat_client.response_content}")


#######################################################################################################################################
