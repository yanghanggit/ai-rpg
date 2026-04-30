"""
卡牌抽取系统模块

为战斗回合中的每个参战角色填充手牌。优先复用 DrawDeckComponent 历史牌（FIFO），
Deck 不足时调用 LLM 实时补足；Deck 充裕时完全跳过 LLM 推理。

主要组件：
- DrawCardsActionSystem: 核心系统类
- CardEntry / DrawCardsResponse: LLM 响应的 Pydantic 解析模型
"""

import json
import random
from typing import Any, Dict, Final, List, final, override
from loguru import logger
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    ActorComponent,
    Keyword,
    KeywordComponent,
    DiceValue,
    DrawDeckComponent,
    DrawCardsAction,
    HandComponent,
    Card,
    CardTargetType,
    DeathComponent,
    CharacterStats,
    CharacterStatsComponent,
    StatusEffectsComponent,
    StatusEffect,
    StatusEffectPhase,
    ExpeditionMemberComponent,
    EnemyComponent,
    AffixSealedComponent,
    ComponentSerialization,
    COMPONENT_TYPES,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
# 兜底牌常量
_FALLBACK_CARD_NAME = "等待"
_FALLBACK_CARD_DESCRIPTION = "什么都不做，原地等待。"
_FALLBACK_DRAW_SYSTEM_MESSAGE = (
    "[系统提示] 本回合卡牌生成失败（LLM 响应格式错误），已自动添加兜底牌「等待」。"
)


#######################################################################################################################################
@final
class CardEntry(BaseModel):
    """单张卡牌条目（用于 DrawCardsResponse 解析）"""

    name: str
    description: str
    effects: List[str] = (
        []
    )  # 词缀列表，每项为"[名称]:短句描述"格式；为空时仲裁后不触发 AddStatusEffectsAction LLM 推理
    affixes: List[Dict[str, Any]] = (
        []
    )  # 结构化词缀列表，每项格式为 ComponentSerialization JSON 对象：{"name": "<ComponentName>", "data": {<组件字段字典>}}；无词缀时输出空数组 []
    damage_dealt: int
    block_gain: int
    hit_count: int = 1
    target_type: str = CardTargetType.ENEMY_SINGLE  # 接受原始字符串，由系统逐卡校验


#######################################################################################################################################
@final
class DrawCardsResponse(BaseModel):
    """LLM 一次抽取 num_cards 张卡牌的响应模型"""

    cards: List[CardEntry]


#######################################################################################################################################
def _sample_keywords(keywords: List[Keyword], k: int) -> List[Keyword]:
    """从关键词池中采样 k 个关键词，优先不重复，池不足时降级为有放回采样。"""
    if not keywords:
        return []
    if len(keywords) >= k:
        return random.sample(keywords, k=k)
    return random.choices(keywords, k=k)


#######################################################################################################################################
def _build_design_principle_prompt(
    num_cards: int,
    keywords: List[Keyword],
    dice_rolls: List[int] = [],
) -> str:
    """生成关键词约束段落，注入抽牌 prompt。

    无关键词时输出差异化指引；有骰值时附加于各卡约束行末尾（骰值语义由 Keyword.description 声明）。
    """
    if not keywords:
        return (
            f"关键词约束：无（{num_cards}张卡牌应有差异化，如高伤低防/高防低伤/均衡型）"
        )
    use_dice = len(dice_rolls) == len(keywords)
    header = (
        "关键词约束（按顺序对应；骰值仅在约束中明确说明用法时生效，否则忽略）："
        if use_dice
        else "关键词约束（按顺序对应）："
    )
    lines = "\n".join(
        f"  - 卡牌{i + 1}：{keywords[i].description}"
        + (f"（骰值：{dice_rolls[i]}）" if use_dice else "")
        for i in range(len(keywords))
    )
    return f"{header}\n{lines}"


#######################################################################################################################################
def _generate_draw_prompt(
    actor_stats: CharacterStats,
    current_round_number: int,
    num_cards: int,
    draw_status_effects: List[StatusEffect],
    keywords: List[Keyword] = [],
    dice_rolls: List[int] = [],
) -> str:
    """生成完整抽牌 prompt（含字段说明与 JSON 示例），用于 LLM 推理。

    Args:
        actor_stats: 角色当前属性
        current_round_number: 当前回合数
        num_cards: 要求生成的张数
        draw_status_effects: DRAW 阶段状态效果，影响数值建议
        keywords: 与 num_cards 等长的关键词约束列表（为空则输出差异化指引）
        dice_rolls: 与 num_cards 等长的骰值列表（0-100）
    """

    def _fmt_duration(d: int) -> str:
        return "永久" if d == -1 else f"剩余{d}回合"

    if draw_status_effects:
        effects_lines = "\n".join(
            f"- {e.name}（{_fmt_duration(e.duration)}）: {e.description}"
            for e in draw_status_effects
        )
        draw_effects_prompt = (
            f"状态效果（attack→damage_dealt，defense→block_gain）:\n{effects_lines}"
        )
    else:
        draw_effects_prompt = ""

    stats_line = f"属性：HP:{actor_stats.hp}/{actor_stats.max_hp} | 攻击:{actor_stats.attack} | 防御:{actor_stats.defense}"
    keyword_line = _build_design_principle_prompt(num_cards, keywords, dice_rolls)
    fields_line = (
        "字段说明：\n"
        "- name：富有想象力，体现行动意图\n"
        "- description：第三人称通用描述（1句，客观说明这张牌的即时战斗行为，禁止叙事润色）。\n"
        "  【重要】禁止提及任何当前场景的地物（如断柱、沙地、余晖、岩板等）、地名或即时情境细节。\n"
        "  ❌ 错误示例：「借助断柱的支撑旋身，踢击敌人」「从落日余晖中冲出扑向目标」\n"
        "  ✓ 正确示例：「旋身借力，以连续踢击攻击单一敌人」「快速突进，向单一目标发起猛扑」\n"
        '- effects：词缀列表，每项格式为"[名称]:短句描述"（如"[燃烧]:可能引发持续火焰伤害"、"[中毒]:持续造成毒素伤害"）；若该卡仅为即时伤害/格挡无副作用，则输出空数组 []\n'
        "- affixes：结构化词缀列表（与 effects 不同，effects 是自然语言状态效果描述，affixes 是可被系统直接反序列化的组件约束）。\n"
        '  每项格式：{"name": "<ComponentName>", "data": {<组件字段字典>}}\n'
        "  无词缀时输出空数组 []\n"
        "- damage_dealt：单次攻击造成的伤害值（基于攻击力合理推算，整数）\n"
        "- block_gain：本张卡牌提供的格挡增量（基于防御力合理推算，整数）\n"
        "- hit_count：攻击次数（默认 1；多段攻击如回旋镖可设为 2~4，每段独立抵挡目标格挡）\n"
        "- target_type：出牌目标类型：攻击/伤害类卡牌通常选 enemy_single 或 enemy_all；每段独立随机命中一名敌方（多段随机，搭配较高 hit_count）选 enemy_random_multi；治疗/强化友方类卡牌通常选 ally_single 或 ally_all；纯粹的自我防御、呼吸调息等仅作用于自身的卡牌选 self_only"
    )
    example_line = '{"name":"...","description":"...","effects":[],"affixes":[],"damage_dealt":0,"block_gain":0,"hit_count":1,"target_type":"enemy_single"}'

    sections = [stats_line]

    if draw_effects_prompt:
        sections.append(draw_effects_prompt)

    sections.append(keyword_line)

    sections.append(fields_line)

    sections.append(f"输出 JSON，cards 数组共 {num_cards} 张：\n{example_line}")

    return (
        f"# 第 {current_round_number} 回合：生成 {num_cards} 张手牌\n\n"
        + "\n\n".join(sections)
    )


#######################################################################################################################################
def _generate_compressed_draw_prompt(
    actor_stats: CharacterStats,
    current_round_number: int,
    num_cards: int,
    draw_status_effects: List[StatusEffect],
    keywords: List[Keyword] = [],
    dice_rolls: List[int] = [],
) -> str:
    """生成压缩版抽牌 prompt（仅动态感知部分），写入对话历史以减少 token 消耗。

    静态字段说明与 JSON 示例附挂在消息额外字段中，LLM 推理仍使用全量版。
    Args 同 `_generate_draw_prompt`。
    """

    def _fmt_duration(d: int) -> str:
        return "永久" if d == -1 else f"剩余{d}回合"

    if draw_status_effects:
        effects_lines = "\n".join(
            f"- {e.name}（{_fmt_duration(e.duration)}）: {e.description}"
            for e in draw_status_effects
        )
        draw_effects_prompt = (
            f"状态效果（attack→damage_dealt，defense→block_gain）:\n{effects_lines}"
        )
    else:
        draw_effects_prompt = ""

    stats_line = f"属性：HP:{actor_stats.hp}/{actor_stats.max_hp} | 攻击:{actor_stats.attack} | 防御:{actor_stats.defense}"
    keyword_line = _build_design_principle_prompt(num_cards, keywords, dice_rolls)

    sections = [stats_line]

    if draw_effects_prompt:
        sections.append(draw_effects_prompt)

    sections.append(keyword_line)
    sections.append(
        f"输出 JSON，cards 数组共 {num_cards} 张（affixes 字段无词缀时输出 []）"
    )

    return (
        f"# 第 {current_round_number} 回合：生成 {num_cards} 张手牌\n\n"
        + "\n\n".join(sections)
    )


#######################################################################################################################################
@final
class DrawCardsActionSystem(ReactiveProcessor):
    """
    响应 DrawCardsAction，为每个存活角色填充 HandComponent。

    Deck 充裕时从历史牌直接填满（跳过 LLM）；不足时并行调用 LLM 补足差额后合并写入。
    """

    def __init__(self, game: TCGGame, use_compressed_prompt: bool = True) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game
        self._use_compressed_prompt: Final[bool] = use_compressed_prompt

    ####################################################################################################################################
    def _get_max_num_cards(self, actor: Entity) -> int:
        """返回角色本回合应持有的手牌上限（ExpeditionMember=3，Enemy=1）。"""
        if actor.has(ExpeditionMemberComponent):
            return 3
        if actor.has(EnemyComponent):
            return 1
        return 1

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(DrawCardsAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(DrawCardsAction)
            and entity.has(ActorComponent)
            and entity.has(KeywordComponent)
            and entity.has(DrawDeckComponent)
            and entity.has(CharacterStatsComponent)
            and not entity.has(DeathComponent)
            and not entity.has(HandComponent)  # 确保没有旧的 HandComponent
        )

    ######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:

        if not self._game.current_dungeon.is_ongoing:
            logger.debug("当前战斗状态非 ONGOING，DrawCardsActionSystem 不执行")
            return

        logger.debug(
            f"DrawCardsActionSystem: 处理 {len(entities)} 个实体的 DrawCardsAction"
        )

        current_rounds = self._game.current_dungeon.current_rounds
        assert (
            current_rounds is not None and len(current_rounds) > 0
        ), "当前回合未创建，检查 CombatRoundTransitionSystem 是否正常执行"
        logger.debug(f"当前回合数: {len(current_rounds)}")

        last_round = self._game.current_dungeon.latest_round
        assert last_round is not None, "无法获取当前回合信息！"

        # 清除手牌（如果有）以避免旧数据干扰
        for entity in entities:
            assert not entity.has(
                HandComponent
            ), f"实体 {entity.name} 已有 HandComponent，可能是上回合遗留，先行移除"

        entity_deck_cards, entity_generate_counts = self._consume_deck_cards(entities)
        current_round_number = len(current_rounds)

        # Deck 充裕（num_cards == 0）→ 直接写入 HandComponent，跳过 LLM
        llm_entities = [e for e in entities if entity_generate_counts[e.name] > 0]
        for entity in entities:
            if entity_generate_counts[entity.name] == 0:
                deck_cards = entity_deck_cards[entity.name]
                entity.replace(
                    HandComponent, entity.name, deck_cards, current_round_number
                )
                logger.debug(
                    f"[{entity.name}] Deck 充裕，手牌共 {len(deck_cards)} 张（全部历史牌，跳过 LLM）："
                    f"{[c.name for c in deck_cards]}"
                )

        if not llm_entities:
            return

        self._inject_affix_sealed_mock_context(llm_entities, current_round_number)

        chat_clients: List[DeepSeekClient] = []
        for entity in llm_entities:
            chat_client = self._create_draw_chat_client(
                entity=entity, num_cards=entity_generate_counts[entity.name]
            )
            chat_clients.append(chat_client)

        await DeepSeekClient.batch_chat(clients=chat_clients)

        for chat_client in chat_clients:
            found_entity = self._game.get_entity_by_name(chat_client.name)
            assert (
                found_entity is not None
            ), f"Entity {chat_client.name} not found in game."
            self._process_draw_response(
                found_entity,
                chat_client,
                num_cards=entity_generate_counts[found_entity.name],
                deck_cards=entity_deck_cards[found_entity.name],
            )

    #######################################################################################################################################
    def _inject_affix_sealed_mock_context(
        self, entities: list[Entity], current_round_number: int
    ) -> None:
        """[mock] 第一回合向远征队员注入 context，引导 LLM 在某张手牌生成封印词缀。"""
        if current_round_number != 1:
            return
        affix_example = {
            "name": AffixSealedComponent.__name__,
            "data": AffixSealedComponent(
                name="", description="不可被出牌，也不可被弃牌", sealed_cards=[]
            ).model_dump(),
        }
        msg = (
            f"[系统提示] 本回合请在你生成的某一张卡牌的 affixes 字段中加入以下词缀（JSON 格式），"
            f"以触发「封印」词条效果：\n{json.dumps(affix_example, ensure_ascii=False)}"
        )
        for entity in entities:
            if not entity.has(ExpeditionMemberComponent):
                continue
            self._game.add_human_message(entity, msg)
            logger.debug(f"[mock context] [{entity.name}] 注入封印词缀引导 context")

    #######################################################################################################################################
    def _consume_deck_cards(
        self, entities: list[Entity]
    ) -> tuple[Dict[str, List[Card]], Dict[str, int]]:
        """FIFO 消耗 DrawDeckComponent 历史牌，计算各实体需 LLM 补足的张数。

        Returns: (entity_deck_cards, entity_generate_counts)；counts 为 0 表示 Deck 充裕，无需 LLM。
        """
        entity_deck_cards: Dict[str, List[Card]] = {}
        entity_generate_counts: Dict[str, int] = {}
        for entity in entities:
            draw_deck_comp = entity.get(DrawDeckComponent)
            assert (
                draw_deck_comp is not None
            ), f"实体 {entity.name} 缺少 DrawDeckComponent"
            max_cards = self._get_max_num_cards(entity)
            n_from_deck = min(len(draw_deck_comp.cards), max_cards)
            deck_cards = list(draw_deck_comp.cards[:n_from_deck])
            del draw_deck_comp.cards[:n_from_deck]
            entity_deck_cards[entity.name] = deck_cards
            entity_generate_counts[entity.name] = max_cards - n_from_deck
            logger.debug(
                f"[{entity.name}] 从 DrawDeck 取 {n_from_deck} 张历史牌，"
                f"需 LLM 生成 {entity_generate_counts[entity.name]} 张"
            )
        return entity_deck_cards, entity_generate_counts

    #######################################################################################################################################
    def _create_draw_chat_client(
        self,
        entity: Entity,
        num_cards: int,
    ) -> DeepSeekClient:
        """为单个角色构建 LLM 抽牌请求，注入当前属性、状态效果与关键词约束。

        Args:
            entity: 角色实体
            num_cards: 需 LLM 生成的张数（> 0）
        """
        last_round = self._game.current_dungeon.latest_round
        assert last_round is not None
        assert not last_round.is_completed, "当前没有进行中的战斗回合，不能生成卡牌。"

        current_round_number = len(self._game.current_dungeon.current_rounds or [])

        combat_stats = self._game.compute_character_stats(entity)

        status_effects_comp = entity.get(StatusEffectsComponent)
        draw_effects = [
            e
            for e in (
                status_effects_comp.status_effects
                if status_effects_comp is not None
                else []
            )
            if e.phase == StatusEffectPhase.DRAW
        ]

        # 从 KeywordComponent 随机采样，每张牌对应一个关键词约束
        assert entity.has(KeywordComponent), f"实体 {entity.name} 缺少 KeywordComponent"
        keyword_comp = entity.get(KeywordComponent)
        sampled_keywords = _sample_keywords(
            keyword_comp.keywords if keyword_comp is not None else [],
            k=num_cards,
        )
        logger.debug(
            f"[{entity.name}] 采样关键词: {[a.description[:20] for a in sampled_keywords]}"
        )

        dice_rolls = [
            random.randint(DiceValue.MIN, DiceValue.MAX) for _ in range(num_cards)
        ]
        logger.debug(f"[{entity.name}] 骰值: {dice_rolls}")

        prompt = _generate_draw_prompt(
            actor_stats=combat_stats,
            current_round_number=current_round_number,
            num_cards=num_cards,
            draw_status_effects=draw_effects,
            keywords=sampled_keywords,
            dice_rolls=dice_rolls,
        )

        compressed_prompt = (
            _generate_compressed_draw_prompt(
                actor_stats=combat_stats,
                current_round_number=current_round_number,
                num_cards=num_cards,
                draw_status_effects=draw_effects,
                keywords=sampled_keywords,
                dice_rolls=dice_rolls,
            )
            if self._use_compressed_prompt
            else None
        )

        return DeepSeekClient(
            name=entity.name,
            prompt=prompt,
            compressed_prompt=compressed_prompt,
            context=self._game.get_agent_context(entity).context,
        )

    #######################################################################################################################################
    def _process_draw_response(
        self,
        entity: Entity,
        chat_client: DeepSeekClient,
        num_cards: int,
        deck_cards: List[Card],
    ) -> None:
        """解析 LLM 响应，与 Deck 历史牌合并后写入 HandComponent。

        解析失败时插入兜底牌「等待」，确保手牌始终存在、回合不阻塞。

        Args:
            entity: 目标角色实体
            chat_client: 包含 LLM 响应的聊天客户端
            num_cards: 预期由 LLM 生成的张数
            deck_cards: 本回合已从 DrawDeckComponent 消耗的历史牌
        """
        current_round_number = len(self._game.current_dungeon.current_rounds or [])

        try:
            response = DrawCardsResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            last_round = self._game.current_dungeon.latest_round
            assert last_round is not None
            assert (
                not last_round.is_completed
            ), "当前没有进行中的战斗回合，不能写入卡牌。"

            # 写入对话历史（压缩版 prompt + AI 原文，附挂全量 prompt 供检索）
            if self._use_compressed_prompt:
                self._game.add_human_message(
                    entity=entity,
                    message_content=chat_client.compressed_prompt,
                    draw_cards_round_number=current_round_number,
                    draw_cards_full_prompt=chat_client.prompt,
                )
            else:
                self._game.add_human_message(
                    entity=entity,
                    message_content=chat_client.prompt,
                    draw_cards_round_number=current_round_number,
                )
            assert chat_client.response_ai_message is not None
            self._game.add_ai_message(
                entity,
                chat_client.response_ai_message,
                draw_cards_round_number=current_round_number,
            )

            # 逐卡校验 target_type，非法值废弃并写入 agent 警告
            valid_target_types = {e.value for e in CardTargetType}
            cards: List[Card] = []
            for entry in response.cards:

                if entry.target_type not in valid_target_types:
                    warn_msg = (
                        f"[系统警告] 你刚才生成的卡牌「{entry.name}」的 target_type 字段值为"
                        f"「{entry.target_type}」，不属于有效值（{sorted(valid_target_types)}），"
                        f"该卡已被系统废弃。请在后续生成中确保 target_type 只使用以下值之一：{sorted(valid_target_types)}"
                    )
                    logger.warning(
                        f"[{entity.name}] 卡牌「{entry.name}」target_type 无效，已废弃：{entry.target_type!r}"
                    )
                    self._game.add_human_message(
                        entity=entity, message_content=warn_msg
                    )
                    continue

                parsed_affixes: List[ComponentSerialization] = []
                for raw in entry.affixes:
                    comp_name = raw.get("name", "")
                    comp_data = raw.get("data", {})
                    comp_class = COMPONENT_TYPES.get(comp_name)
                    if comp_class is None:
                        logger.warning(
                            f"[{entity.name}] 未知词缀组件 {comp_name!r}，跳过"
                        )
                        continue
                    try:
                        comp_class(**comp_data)  # 实例化验证字段合法性
                    except Exception as affix_err:
                        logger.warning(
                            f"[{entity.name}] 词缀 {comp_name} data 验证失败：{affix_err}，跳过"
                        )
                        continue
                    parsed_affixes.append(
                        ComponentSerialization(name=comp_name, data=comp_data)
                    )

                cards.append(
                    Card(
                        name=entry.name,
                        description=entry.description,
                        effects=entry.effects,
                        affixes=parsed_affixes,
                        damage_dealt=entry.damage_dealt,
                        block_gain=entry.block_gain,
                        hit_count=entry.hit_count,
                        target_type=CardTargetType(entry.target_type),
                        source=entity.name,
                    )
                )

            if len(cards) != num_cards:
                logger.warning(
                    f"[{entity.name}] LLM 生成卡牌数量（{len(cards)}）与预期（{num_cards}）不符，"
                    "可能有部分卡牌因无效 target_type 被废弃"
                )

            all_cards = deck_cards + cards
            entity.replace(HandComponent, entity.name, all_cards, current_round_number)
            logger.debug(
                f"[{entity.name}] 手牌共 {len(all_cards)} 张 "
                f"= Deck {len(deck_cards)} 张 + 新生成 {len(cards)} 张："
                f"{[c.name for c in all_cards]}"
            )

        except Exception as e:
            logger.error(f"{chat_client.response_content}")
            logger.error(f"Exception: {e}")
            # LLM 推理失败：不做补偿，直接插入兜底牌，确保 HandComponent 始终被写入
            fallback_card = Card(
                name=_FALLBACK_CARD_NAME,
                description=_FALLBACK_CARD_DESCRIPTION,
                effects=[],
                damage_dealt=0,
                block_gain=0,
                hit_count=1,
                target_type=CardTargetType.SELF_ONLY,
                source=entity.name,
            )
            all_cards = deck_cards + [fallback_card]
            entity.replace(HandComponent, entity.name, all_cards, current_round_number)
            self._game.add_human_message(
                entity=entity,
                message_content=_FALLBACK_DRAW_SYSTEM_MESSAGE,
            )
            logger.warning(
                f"[{entity.name}] 卡牌生成失败，已插入兜底牌「等待」，手牌共 {len(all_cards)} 张"
            )

    #######################################################################################################################################
