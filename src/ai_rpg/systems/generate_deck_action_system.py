# """
# 牌库生成系统模块
# """

# import random
# from typing import Dict, Final, List, final, override

# from loguru import logger
# from pydantic import BaseModel

# from ..deepseek import DeepSeekClient, batch_chat
# from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
# from ..game.dbg_combat_processor import compute_character_stats
# from ..game.dbg_game import DBGGame
# from ..models import (
#     ActorComponent,
#     ArchetypeComponent,
#     Card,
#     CharacterStats,
#     CharacterStatsComponent,
#     DeathComponent,
#     DeckComponent,
#     DEFAULT_ROUND_ENERGY,
#     DrawPileComponent,
#     GenerateDeckAction,
#     HumanMessage,
#     MonsterComponent,
#     PartyMemberComponent,
#     TargetType,
# )
# from ..utils import extract_json, prompt_builder
# from .card_prompt_builders import BUILD_CARD_FIELD_DESCRIPTION


# #######################################################################################################################################
# class DeckCardEntry(BaseModel):
#     """单张卡牌条目（用于 DeckGenerateResponse 解析）"""

#     name: str
#     description: str
#     on_play_affixes: List[str] = []
#     playable: bool = True
#     exhaust: bool = False
#     retain: bool = False
#     ethereal: bool = False
#     cost: int = 1
#     damage: int
#     hit_count: int = 1
#     block: int = 0
#     self_target: bool = False
#     target_type: str = TargetType.SINGLE


# #######################################################################################################################################
# class DeckGenerateResponse(BaseModel):
#     """LLM 一次生成 num_cards 张牌库卡牌的响应模型"""

#     cards: List[DeckCardEntry]


# #######################################################################################################################################
# @prompt_builder
# def build_design_principle_prompt(
#     num_cards: int,
#     keywords: List[str] = [],
# ) -> str:
#     """生成关键词约束段落。无关键词时输出差异化指引。"""
#     if not keywords:
#         return f"关键词约束：无（{num_cards}张卡牌应有差异化，如高伤低格挡/高格挡低伤/均衡型）"
#     lines = "\n".join(f"  - 卡牌{i + 1}：{keywords[i]}" for i in range(len(keywords)))
#     return f"关键词约束（按顺序对应）：\n{lines}"


# #######################################################################################################################################
# @prompt_builder
# def build_deck_prompt(
#     actor_stats: CharacterStats,
#     num_cards: int,
#     keywords: List[str] = [],
# ) -> str:
#     """生成战斗开始牌库生成 prompt（含字段说明与 JSON 示例）。"""

#     design_principle = build_design_principle_prompt(num_cards, keywords)

#     return f"""# 战斗开始：生成 {num_cards} 张初始牌库卡牌

# ## 角色属性

# | HP | 攻击 | 防御 | 每回合行动次数 |
# |---|---|---|---|
# | {actor_stats.hp}/{actor_stats.max_hp} | {actor_stats.attack} | {actor_stats.defense} | {DEFAULT_ROUND_ENERGY} |

# ## 设计约束

# {design_principle}

# ## 叙事主题

# 请从你的「角色设定」（历史、性格、习惯、随身之物、身体特征等）中提炼一个叙事主题，本牌库所有卡牌的 `name` 与 `description` 都应围绕该主题展开——主题是叙事意象的来源，不约束功能（功能由上方关键词约束决定）。

# {BUILD_CARD_FIELD_DESCRIPTION}

# ## 核心原则

# - keywords 即边界，不是风格建议：要求的效果在对应字段体现；未提及即禁止
# - 即时词缀（on_play_affixes）仅限 keywords 授权时填充
# - 叙事主题是 description 的意象来源，keywords 是 description 的功能边界，二者各自独立

# ## 约束

# - `description` 须围绕上方「叙事主题」展开，可自由采用动作、物件、意象、氛围、典故等任意形态；禁止提及具体地名与某一具体战斗场景的即时情境
# - `on_play_affixes` 禁止重述数值字段已确定性表达的效果：不得重复量化 `damage`/`hit_count`/`block` 已决定的数值量级
# - `cards` 数组长度必须恰好为 {num_cards}
# - 只输出 JSON，不附加任何说明文字

# ```json
# {{
#   "cards": [
#     {{
#       "name": "...",
#       "description": "...",
#       "on_play_affixes": [],
#       "playable": true,
#       "exhaust": false,
#       "retain": false,
#       "ethereal": false,
#       "cost": 1,
#       "damage": 0,
#       "hit_count": 1,
#       "block": 0,
#       "self_target": false,
#       "target_type": "single"
#     }}
#   ]
# }}
# ```"""


# #######################################################################################################################################
# @prompt_builder
# def build_condensed_deck_prompt(
#     actor_stats: CharacterStats,
#     num_cards: int,
#     keywords: List[str] = [],
# ) -> str:
#     """生成牌库生成 prompt 的精简版（写入对话历史，减少 token 消耗）。"""
#     design_principle = build_design_principle_prompt(num_cards, keywords)
#     return f"""# 战斗牌库生成（{num_cards} 张）

# HP:{actor_stats.hp}/{actor_stats.max_hp} | 攻击:{actor_stats.attack} | 防御:{actor_stats.defense} | 行动次数:{DEFAULT_ROUND_ENERGY}

# {design_principle}

# 叙事主题：从你的角色设定中提炼"""


# @final
# class GenerateDeckActionSystem(ReactiveProcessor):
#     """
#     响应 GenerateDeckAction，为每个触发角色并行调用 LLM 生成初始牌库卡牌，
#     """

#     def __init__(self, game: DBGGame) -> None:
#         super().__init__(game)
#         self._game: Final[DBGGame] = game

#     ####################################################################################################################################
#     def _get_cards_per_combat(self, actor_entity: Entity) -> int:
#         """返回角色在本次战斗中的初始牌库数量（PartyMember=5，Monster=3）。"""
#         if actor_entity.has(PartyMemberComponent):
#             return 5
#         if actor_entity.has(MonsterComponent):
#             return 3
#         return 3

#     ####################################################################################################################################
#     @override
#     def get_trigger(self) -> Dict[Matcher, GroupEvent]:
#         return {Matcher(GenerateDeckAction): GroupEvent.ADDED}

#     ####################################################################################################################################
#     @override
#     def filter(self, entity: Entity) -> bool:
#         return (
#             entity.has(GenerateDeckAction)
#             and entity.has(ActorComponent)
#             and entity.has(ArchetypeComponent)
#             and entity.has(DeckComponent)
#             and entity.has(CharacterStatsComponent)
#             and not entity.has(DeathComponent)
#         )

#     ####################################################################################################################################
#     @override
#     async def react(self, entities: List[Entity]) -> None:

#         logger.debug(f"DeckGenerationSystem: 为 {len(entities)} 个角色生成初始牌库")

#         # 构建并行 LLM 请求
#         chat_clients: List[DeepSeekClient] = [
#             self._build_client(entity) for entity in entities
#         ]

#         await batch_chat(clients=chat_clients)

#         # 解析结果，填入 DeckComponent 后洗牌移入 DrawPileComponent
#         for chat_client in chat_clients:
#             self._process_generation_response(chat_client)

#     #######################################################################################################################################
#     def _build_client(self, entity: Entity) -> DeepSeekClient:
#         """为单个实体构建牌库生成的 DeepSeekClient。"""

#         num_cards = self._get_cards_per_combat(entity)

#         archetype_comp = entity.get(ArchetypeComponent)
#         assert archetype_comp is not None, f"{entity.name} 缺少 ArchetypeComponent"

#         keywords_pool = archetype_comp.keywords
#         if not keywords_pool:
#             sampled_keywords: List[str] = []
#         elif len(keywords_pool) >= num_cards:
#             sampled_keywords = random.sample(keywords_pool, k=num_cards)
#         else:
#             sampled_keywords = random.choices(keywords_pool, k=num_cards)

#         logger.debug(f"[{entity.name}] 关键词: {[k[:20] for k in sampled_keywords]}")

#         # 生成完整提示词，供 LLM 生成卡牌
#         combat_stats = compute_character_stats(entity)
#         prompt = build_deck_prompt(
#             actor_stats=combat_stats,
#             num_cards=num_cards,
#             keywords=sampled_keywords,
#         )

#         # 生成精简提示词，减少 LLM token 消耗
#         condensed_prompt = build_condensed_deck_prompt(
#             actor_stats=combat_stats,
#             num_cards=num_cards,
#             keywords=sampled_keywords,
#         )

#         # 构建 DeepSeekClient，传入完整提示词、精简提示词和消息历史
#         return DeepSeekClient(
#             name=entity.name,
#             full_prompt=prompt,
#             condensed_prompt=condensed_prompt,
#             messages=self._game.get_agent_memory(entity).messages,
#         )

#     #######################################################################################################################################
#     def _process_generation_response(
#         self,
#         chat_client: DeepSeekClient,
#     ) -> None:
#         """解析 LLM 响应，将生成卡牌洗牌填入 DrawPileComponent。解析失败时跳过（DrawPile 保持空）。"""

#         # 检查 LLM 是否返回了有效的 AI 消息，如果没有则记录错误并返回
#         if chat_client.response_ai_message is None:
#             logger.error(f"[{chat_client.name}] LLM 返回空响应，跳过牌库生成")
#             return

#         entity = self._game.get_entity_by_name(chat_client.name)
#         assert (
#             entity is not None
#         ), f"DeckGenerationSystem: 无法找到实体 {chat_client.name} 以处理生成结果"

#         num_cards = self._get_cards_per_combat(entity)

#         try:
#             # 解析 LLM 响应 JSON
#             response = DeckGenerateResponse.model_validate_json(
#                 extract_json(chat_client.response_content)
#             )
#         except Exception as e:
#             logger.error(
#                 f"DeckGenerationSystem 解析失败 [{entity.name}]: {e}\n{chat_client.response_content}"
#             )
#             # 解析失败：DrawPile 保持空，DrawCardsActionSystem 回合首次抽牌时会插入兜底牌
#             return

#         valid_target_types = {e.value for e in TargetType}
#         cards: List[Card] = []
#         for entry in response.cards:

#             # 验证 target_type 字段值是否合法，非法则跳过该卡并发出警告
#             if entry.target_type not in valid_target_types:
#                 warn_msg = (
#                     f"[系统警告] 你刚才生成的牌库卡牌「{entry.name}」的 target_type 字段值为"
#                     f"「{entry.target_type}」，不属于有效值（{sorted(valid_target_types)}），"
#                     f"该卡已被系统废弃。"
#                 )
#                 logger.warning(
#                     f"[{entity.name}] 牌库卡牌「{entry.name}」target_type 无效，已废弃：{entry.target_type!r}"
#                 )
#                 self._game.add_human_message(
#                     entity=entity, human_message=HumanMessage(content=warn_msg)
#                 )
#                 continue

#             cards.append(
#                 Card(
#                     name=entry.name,
#                     description=entry.description,
#                     on_play_affixes=entry.on_play_affixes,
#                     playable=entry.playable,
#                     exhaust=entry.exhaust,
#                     retain=entry.retain,
#                     ethereal=entry.ethereal,
#                     cost=entry.cost,
#                     damage=entry.damage,
#                     hit_count=entry.hit_count,
#                     block=entry.block,
#                     self_target=entry.self_target,
#                     target_type=TargetType(entry.target_type),
#                     source=entity.name,
#                 )
#             )

#         if len(cards) != num_cards:
#             logger.warning(
#                 f"[{entity.name}] 牌库生成卡牌数量（{len(cards)}）与预期（{num_cards}）不符"
#             )

#         # 累积到原始牌库：本次新生成的牌追加到 DeckComponent
#         deck_comp = entity.get(DeckComponent)
#         assert deck_comp is not None, f"{entity.name} 缺少 DeckComponent"
#         deck_comp.cards.extend(cards)

#         # GenerateDeckActionSystem 仅写 DeckComponent；DrawPileComponent 是战斗管道职责。
#         # 战斗管道中，怪物在 CombatInitActorSystem 初始化空牌堆后才生成牌库，
#         # 因此此处允许存在“空的” DrawPileComponent（若存在则必须仍为空）。
#         if entity.has(DrawPileComponent):
#             draw_pile_comp = entity.get(DrawPileComponent)
#             assert (
#                 len(draw_pile_comp.cards) == 0
#             ), f"{entity.name} 的 DrawPileComponent 非空，牌库生成阶段不应已填充临时牌堆"

#         # 将本轮任务提示词与 LLM 回复写入 agent 对话历史
#         self._game.add_human_message(
#             entity=entity,
#             human_message=HumanMessage(
#                 content=chat_client.condensed_prompt,
#                 deck_generation_full_prompt=chat_client.full_prompt,
#             ),
#         )

#         # 将 LLM 回复写入 agent 对话历史
#         self._game.add_ai_message(
#             entity=entity, ai_message=chat_client.response_ai_message
#         )

#         logger.debug(
#             f"[{entity.name}] 牌库生成完成：本次 {len(cards)} 张"
#             f"，DeckComponent 共 {len(deck_comp.cards)} 张原始牌（含本次）"
#             f"：{[c.name for c in cards]}"
#         )
