"""仲裁后效果系统模块

每次战斗仲裁结算完成后，决定是否对场内角色施加额外效果。
当前支持两条处理路径：Stage（场景级干预）和 Actor（角色级反应，暂为 stub）。
"""

from enum import StrEnum, unique
import random
from typing import Final, List, Set, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    ActorComponent,
    Card,
    TargetType,
    CharacterStatsComponent,
    DungeonComponent,
    HandComponent,
    StageComponent,
    PostArbitrationAction,
    StatusEffect,
    EffectPhase,
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


#######################################################################################################################################
def _build_actors_summary(game: TCGGame, actor_entities: Set[Entity]) -> str:
    """格式化场内存活角色状态摘要，供 prompt 函数复用。"""
    actor_lines: List[str] = []
    for entity in actor_entities:
        final_stats = (
            game.compute_character_stats(entity)
            if entity.has(CharacterStatsComponent)
            else None
        )
        effects_comp = entity.get(StatusEffectsComponent)

        hp_str = (
            f"HP: {final_stats.hp}/{final_stats.max_hp}"
            if final_stats is not None
            else "HP: ?"
        )

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
            f"- **{entity.name}**  {hp_str}  " f"状态效果: {effects_str}  {hand_note}"
        )
    return "\n".join(actor_lines) if actor_lines else "  （无存活角色）"


#######################################################################################################################################
def _generate_compressed_stage_post_arbitration_prompt(
    game: TCGGame,
    actor_entities: Set[Entity],
    current_turn_actor_name: str,
    current_round_number: int,
) -> str:
    """生成压缩版仲裁后场景效果提示词（仅动态感知部分，省略静态规则/格式说明）

    保留内容：回合标题、出牌者说明、存活角色当前状态。
    省略内容：## 你的本质与职责、状态效果字段说明、塞牌字段说明、description 规范、JSON 示例。
    """

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

    要求 stage agent 以地牢主视角，在仲裁结算后决定是否对场内角色施加新效果或塞牌。
    仲裁结算的完整内容（combat_log/narrative）已在 stage agent 的上下文中，无需重复传入。

    Args:
        actor_entities: 场内所有存活角色实体集合
        current_turn_actor_name: 本回合出牌者名称（当前行动角色）
        current_round_number: 当前回合数

    Returns:
        格式化的提示词字符串
    """

    actors_summary = _build_actors_summary(game, actor_entities)

    phase_desc = f"""
## 状态效果字段说明

每个状态效果必须指定 `phase` 字段，决定生效阶段与可影响属性：

| phase | 对应阶段 | 可影响属性 | 典型效果举例 |
|---|---|---|---|
| `{EffectPhase.DRAW}` | 抽牌阶段 | attack、defense（间接影响下回合卡牌数値） | 「虚弱」攻击力−2，damage_dealt 偏低；「沉重」防御力−1，防御较弱 |
| `{EffectPhase.ARBITRATION}` | 仲裁结算阶段 | hp、damage_dealt | 「破甲」防御降低；「荆棘」反伤；「眩晕」影响出牌；「虚弱」伤害减少 |
| `{EffectPhase.ROUND_END}` | 回合末阶段 | hp | 「中毒」每回合末扣血；「燃烧」持续火焰伤害；「再生」每回合末回血 |

**speed**：影响出手顺序，只允许 +1 / 0 / -1，默认 0。
**defense**：影响防御值（正值增防、负值破甲），整数，默认 0。
禁止修改 max_hp。
"""

    card_field_desc = f"""
## 塞牌字段说明

塞入的卡牌会被加入目标的当前手牌；数值应与场内角色血量及战斗烈度相匹配。

| 字段 | 说明 |
| --- | --- |
| name | 卡牌名称（<8字），体现效果意图 |
| description | 第三人称，描述角色借助**上下文中已存在的**场景具体物件的即时客观动作（1句，如"抓起地面的断柱碎块掷向对方"）；不可凭空引入非场景物件 |
| affixes | 可选。词缀声明列表，两类格式：延迟词缀 `[名称]:触发倾向描述`（如 `[碎石粉尘]:可能引起视线模糊`），仲裁后独立推理生成持续状态效果；即时词缀 `![名称]:即时修正描述`（如 `![穿甲]:无视目标防御`），直接注入本次仲裁计算。纯即时无词缀时输出 [] |
| playable | 可选。布尔值，是否允许出牌；默认 true，场景叙事明确暗示该物件具有禁出属性时填 false |
| exhaust | 可选。布尔值，出牌后是否永久消耗（归入消耗堆，不再回到抽牌循环）；默认 false，场景叙事明确暗示该物件使用后消失时填 true |
| damage_dealt | 单次命中造成的伤害（整数；攻击类取合理正值，无伤害取 0） |
| hit_count | 攻击次数（默认 1；多段攻击可设 2~4，每段独立作用） |
| target_type | 出牌目标类型（见下表） |

| target_type | 含义 |
|---|---|
| `{TargetType.ENEMY_SINGLE}` | 攻击单体敌方（默认） |
| `{TargetType.ENEMY_ALL}` | 攻击全体敌方 |
| `{TargetType.ENEMY_RANDOM_MULTI}` | 每段独立随机命中一名敌方（需配合较高 hit_count） |
| `{TargetType.ALLY_SINGLE}` | 治疗/增益单体友方 |
| `{TargetType.ALLY_ALL}` | 治疗/增益全体友方 |
| `{TargetType.SELF_ONLY}` | 仅作用于自身（防御、自损诅咒等） |

**注意**：只有当前持有手牌的角色才能被塞牌。"""

    return f"""# 第 {current_round_number} 回合 — 仲裁后场景干预

**{current_turn_actor_name}** 刚刚完成出牌，仲裁结算已在上下文中记录。

## 场内存活角色当前状态

{actors_summary}

## 你的本质与职责

你是这片场景本身，没有意志，没有偏好，只有物理现实在运作。
你能做的，是将**上下文中已出现、已存在于此场景里的环境要素**，转化为对角色身体的客观影响，或为角色提供可借用的场景物件。

**干预原则**：
- ✅ 允许：上下文叙事中已描述的环境要素引发的物理后果（沙尘入眼、热浪灼烧、松软地面失稳、碎石可用、断柱可借力等）
- ✅ 塞牌须有据：只有上下文中描述了该物件存在于场景中，才能将其作为卡牌塞给角色使用
- ✅ 干预前先推断对象当前状态：从上下文叙事中判断场景对象处于何种状态（完好/部分损耗/已触发/已取走/仍可操作…），仅在该状态允许进一步交互时才将其转化为效果或卡牌
- ❌ 禁止：勇气、恐惧、神圣、复仇、祝福、诅咒等角色内在情绪或来源不明的魔法效果
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
          "phase": "{EffectPhase.ARBITRATION}",
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
          "damage_dealt": 2,
          "hit_count": 1,
          "target_type": "{TargetType.ENEMY_SINGLE}"
        }}
      ]
    }}
  ]
}}
```

`phase` 填 `{EffectPhase.DRAW}` / `{EffectPhase.ARBITRATION}` / `{EffectPhase.ROUND_END}` 其中之一。
- `duration`：-1=永久，>0=剩余回合数，默认 3
- `counter`：整数初始值；`{EffectPhase.ARBITRATION}` 阶段特殊计数器词条（如"前3次受击"设 3），默认 0
无干预时输出空的 per_actor 数组，只输出JSON."""


#######################################################################################################################################
@final
class PostArbitrationActionSystem(ReactiveProcessor):
    """仲裁后效果系统

    每次仲裁结算成功后触发，对 Stage 和 Actor 两类实体分批处理：

    - Stage：combat stage 的 LLM agent 以地牢主视角决定是否干预，
      可追加状态效果或向角色手牌塞入卡牌。
    - Actor（暂为 stub）：预留给角色级仲裁后反应，当前未激活。

    战斗未进行中时整批跳过。

    参数：
        strategy: 塞牌位置策略（APPEND 追加尾部 / RANDOM_INSERT 随机插入）
        use_compressed_prompt: 是否使用压缩提示词（默认 True）
    """

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
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(PostArbitrationAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(PostArbitrationAction) and (
            (entity.has(StageComponent) and entity.has(DungeonComponent))
            or entity.has(ActorComponent)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        if not self._game.current_dungeon.is_ongoing:
            logger.debug("PostArbitrationActionSystem: 战斗未进行中，跳过")
            return

        # 批次一：Stage 实体 — 地牢主视角干预（追加状态效果 / 塞牌）
        stage_entities = [
            e for e in entities if e.has(StageComponent) and e.has(DungeonComponent)
        ]
        for stage_entity in stage_entities:
            await self._process_stage(stage_entity)

        # 批次二：Actor 实体 — 角色级仲裁后反应（暂未实现）
        actor_entities = [e for e in entities if e.has(ActorComponent)]
        for actor_entity in actor_entities:
            await self._process_actor(actor_entity)

    #######################################################################################################################################
    async def _process_actor(self, actor_entity: Entity) -> None:
        """Actor 路径：角色级仲裁后反应（暂未实现）

        未来由 actor 自身的 LLM agent 决定是否执行仲裁后的角色反应。
        触发点需在 PlayCardsArbitrationSystem._apply_arbitration_result 中
        对 actor_entity 添加 PostArbitrationAction 才会激活此路径。
        """
        logger.debug(
            f"PostArbitrationActionSystem: [{actor_entity.name}] Actor 路径暂未实现，跳过"
        )

    #######################################################################################################################################
    async def _process_stage(self, stage_entity: Entity) -> None:
        """为单个 stage entity 执行仲裁后场景干预逻辑"""

        action = stage_entity.get(PostArbitrationAction)
        assert (
            action is not None
        ), "PostArbitrationActionSystem: 无法获取 PostArbitrationAction 组件！"

        player_entity = self._game.get_player_entity()
        assert (
            player_entity is not None
        ), "PostArbitrationActionSystem: 无法找到玩家实体！"

        actor_entities = self._game.get_alive_actors_in_stage(player_entity)
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
            json_content = extract_json_from_code_block(chat_client.response_content)
            response = StagePostArbitrationResponse.model_validate_json(json_content)

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
        # if not target_entity.has(HandComponent):
        #     logger.debug(f"[{directive.target}] 当前无手牌，跳过塞牌")
        #     return

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
