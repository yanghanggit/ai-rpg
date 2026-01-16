"""
卡牌抽取系统模块

该模块实现了战斗回合中的卡牌生成机制，负责将角色技能转化为可执行的行动卡牌。

核心特性：
- 动态卡牌生成：每回合从角色技能池中随机选择最多2个技能
- 一对一映射：每个选中的技能对应生成一张独立的行动卡牌
- LLM驱动：通过语言模型生成富有创意且符合角色特征的卡牌名称和描述
- 上下文一致性：确保提示词生成和响应处理使用相同的技能数据

主要组件：
- DrawCardsActionSystem: 核心系统类，协调整个卡牌生成流程
- _generate_round_prompt: 生成完整的LLM请求提示词
- _generate_compressd_round_prompt: 生成用于历史记录的压缩提示词
"""

import random
from typing import Dict, Final, List, final, override
from loguru import logger
from pydantic import BaseModel
from ..chat_services.client import ChatClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    DrawCardsAction,
    HandComponent,
    Card,
    Skill,
    SkillBookComponent,
    DeathComponent,
)
from ..utils import extract_json_from_code_block
from langchain_core.messages import AIMessage


#######################################################################################################################################
@final
class DrawCardsResponse(BaseModel):
    cards: List[Card] = []


#######################################################################################################################################
def _generate_round_prompt(
    actor_name: str,
    card_creation_count: int,
    action_order: List[str],
    selected_skills: List[Skill],
    current_round_number: int,
) -> str:
    """
    生成战斗回合的卡牌抽取提示词。

    要求LLM为每个技能生成一张对应的卡牌，不进行技能组合。
    卡牌数量等于提供的技能数量。

    Args:
        actor_name: 角色名称（当前未使用）
        card_creation_count: 需要生成的卡牌数量（等于 selected_skills 的长度）
        action_order: 角色行动顺序列表
        selected_skills: 已选择的技能列表（最多2个）
        current_round_number: 当前回合数

    Returns:
        str: 格式化的提示词
    """
    assert card_creation_count > 0, "card_creation_count must be greater than 0"
    assert len(action_order) > 0, "action_order must not be empty"

    # 格式化技能列表
    skills_text = "\n".join(
        [f"- {skill.name}: {skill.description}" for skill in selected_skills]
    )

    return f"""# 指令！第 {current_round_number} 回合：生成 {card_creation_count} 张卡牌，以JSON格式返回。

## 1. 本回合行动顺序

{action_order}

先手角色的卡牌会先生效，影响后续角色的战场状态。

## 2. 生成卡牌

### 2.1 可用技能池

{skills_text}

### 2.2 卡牌生成规则

- 设计要求：每张卡牌对应一个技能，不进行组合。必须为每个技能生成一张对应的卡牌
- 卡牌命名：基于技能效果创造新颖行动名称(禁止暴露技能名)
- 卡牌描述：行动方式、战斗目的、使用代价

## 3. 输出格式(JSON)

```json
{{
  "cards": [
    {{
      "name": "[行动名称]",
      "description": "[行动描述]",
      "targets": ["[目标角色名]"]
    }}
  ]
}}
```

**约束规则**：

- 必须生成{card_creation_count}张卡牌
- description可含整数但禁止百分率，禁止出现角色名称
- 严格按上述JSON格式输出"""


#######################################################################################################################################
def _generate_compressd_round_prompt(
    actor_name: str,
    card_creation_count: int,
    action_order: List[str],
    current_round_number: int,
) -> str:
    """
    生成压缩版本的回合提示词，用于保存到上下文历史。

    与完整提示词相比，该版本更简洁，仅包含关键信息。

    Args:
        actor_name: 角色名称（当前未使用）
        card_creation_count: 卡牌数量
        action_order: 角色行动顺序列表
        current_round_number: 当前回合数

    Returns:
        str: 压缩后的提示词
    """
    return f"""# 指令！这是第 {current_round_number} 回合，评估当前态势，生成你的参战信息，并以JSON格式返回。

## 场景内角色行动顺序(从左到右，先行动者可能影响战局与后续行动)

{action_order}

## 参战信息内容

- 生成 {card_creation_count} 张卡牌(cards)"""


#######################################################################################################################################
@final
class DrawCardsActionSystem(ReactiveProcessor):
    """
    卡牌抽取系统

    负责在战斗回合中为每个角色生成行动卡牌。
    采用抽象提示词设计，只描述行动意图而不要求具体数值，
    遵循行动规划与数值解析分离的架构原则。

    卡牌生成规则：
    - 每个角色从其技能池中随机选择最多2个技能
    - 每个技能对应生成一张卡牌，不进行技能组合
    - 卡牌数量等于选择的技能数量（1-2张）
    """

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: Final[TCGGame] = game_context

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(DrawCardsAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(DrawCardsAction) and not entity.has(DeathComponent)

    ######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        assert (
            len(entities) > 0
        ), "DrawCardsActionSystem react called with empty entities list"

        if not self._game.current_combat_sequence.is_ongoing:
            # 阶段不对，直接返回
            return

        last_round = self._game.current_combat_sequence.latest_round
        if last_round.is_completed:
            logger.success(f"last_round.has_ended, so setup new round")
            self._game.create_next_round()

        logger.debug(
            f"当前回合数: {len(self._game.current_combat_sequence.current_rounds)}"
        )
        assert (
            len(self._game.current_combat_sequence.current_rounds) > 0
        ), "当前没有进行中的战斗，不能设置回合。"

        # 清除手牌，准备重新生成
        self._game.clear_hands()

        # 提前为每个实体获取技能列表（最多2个，随机选择），确保整个流程使用一致的数据
        entity_card_count_map: Dict[str, List[Skill]] = {}
        for entity in entities:
            available_skills = self._get_available_skills(entity)
            entity_card_count_map[entity.name] = available_skills

        # 生成请求
        chat_clients: List[ChatClient] = self._create_chat_clients(
            entities, entity_card_count_map
        )

        # 语言服务
        await ChatClient.gather_request_post(clients=chat_clients)

        # 处理角色规划请求
        for chat_client in chat_clients:

            found_entity = self._game.get_entity_by_name(chat_client.name)
            assert (
                found_entity is not None
            ), f"Entity {chat_client.name} not found in game."

            # 使用映射表中的技能列表，确保与生成请求时一致
            card_count = len(entity_card_count_map[found_entity.name])
            self._process_draw_cards_response(found_entity, chat_client, card_count)

        # 最后的兜底，遍历所有参与的角色，如果没有手牌，说明_process_draw_cards_response出现了错误，可能是LLM返回的内容无法正确解析。此时，就需要给角色一个默认的手牌，避免游戏卡死。
        self._ensure_all_entities_have_hands(entities)

    #######################################################################################################################################
    def _ensure_all_entities_have_hands(self, entities: List[Entity]) -> None:
        """
        确保所有实体都有手牌组件的兜底机制。
        如果某个实体缺少HandComponent，说明_process_draw_cards_response出现了错误，
        可能是LLM返回的内容无法正确解析。此时给角色一个默认的等待，避免游戏卡死。

        Args:
            entities: 需要检查的实体列表
        """
        for entity in entities:

            if entity.has(HandComponent) or entity.has(DeathComponent):
                continue

            wait_card = Card(
                name="等待",
                description="什么都不做",
                targets=[entity.name],
            )

            entity.replace(
                HandComponent,
                entity.name,
                [wait_card],
            )

            # 模拟历史上下文！
            self._game.add_human_message(
                entity=entity,
                message_content="# 指令！评估当前态势，生成你的参战信息",
            )

            # 添加AI消息，包括响应内容。
            self._game.add_ai_message(
                entity,
                [AIMessage(content="未能生成参战信息，默认执行等待动作。")],
            )

    #######################################################################################################################################
    def _process_draw_cards_response(
        self, entity: Entity, chat_client: ChatClient, card_creation_count: int
    ) -> None:
        """
        处理LLM返回的抽卡响应并应用到实体。

        解析ChatClient的JSON响应，提取卡牌和状态效果，
        然后更新实体的HandComponent、CombatStatsComponent等组件。
        如果解析失败，会记录错误日志但不会中断游戏流程。

        Args:
            entity: 目标角色实体
            chat_client: 包含LLM响应内容的聊天客户端
            card_creation_count: 该实体应生成的卡牌数量
        """

        try:

            validated_response = DrawCardsResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            last_round = self._game.current_combat_sequence.latest_round
            assert (
                not last_round.is_completed
            ), "当前没有进行中的战斗回合，不能生成卡牌。"

            # 添加压缩上下文的提示词
            self._game.add_human_message(
                entity=entity,
                message_content=_generate_compressd_round_prompt(
                    actor_name=entity.name,
                    card_creation_count=card_creation_count,
                    action_order=last_round.action_order,
                    current_round_number=len(
                        self._game.current_combat_sequence.current_rounds
                    ),
                ),
                compressed_prompt=chat_client.prompt,
            )

            # 添加AI消息，包括响应内容。
            self._game.add_ai_message(entity, chat_client.response_ai_messages)

            # 生成的结果。
            # validated_response.cards 中的每个 card_response 已经是 Card 类型
            # 因为 DrawCardsResponse.cards: List[Card] 会自动反序列化
            cards: List[Card] = validated_response.cards

            # 更新手牌。
            if len(cards) > 0:
                entity.replace(
                    HandComponent,
                    entity.name,
                    cards,
                )
            else:
                logger.warning(f"entity {entity.name} has no cards from LLM response")

        except Exception as e:
            logger.error(f"{chat_client.response_content}")
            logger.error(f"Exception: {e}")

    #######################################################################################################################################
    def _get_available_skills(self, entity: Entity) -> List[Skill]:
        """获取实体可用的技能列表。

        如果技能数量大于2，则随机选择2个技能；
        如果技能数量小于等于2，则返回所有技能。

        Args:
            entity (Entity): 目标实体

        Returns:
            List[Skill]: 实体可用的技能列表（最多2个）
        """

        skill_book_comp = entity.get(SkillBookComponent)
        assert skill_book_comp is not None, "Entity must have SkillBookComponent"
        if len(skill_book_comp.skills) == 0:
            logger.warning(f"entity {entity.name} has no skills in SkillBookComponent")
            assert False, "Using test skills pool for entity with no skills."

        all_skills = skill_book_comp.skills.copy()

        # 如果技能数量大于2，随机选择2个；否则返回所有技能
        if len(all_skills) > 2:
            return random.sample(all_skills, 2)
        else:
            return all_skills

    #######################################################################################################################################
    def _create_chat_clients(
        self,
        actor_entities: List[Entity],
        entity_card_count_map: Dict[str, List[Skill]],
    ) -> List[ChatClient]:
        """
        为每个角色实体创建聊天客户端以请求LLM生成卡牌。

        为每个实体构建包含上下文的ChatClient对象，准备发起LLM请求。

        Args:
            actor_entities: 需要生成卡牌的角色实体列表
            entity_card_count_map: 实体名称到技能列表的映射表

        Returns:
            List[ChatClient]: 准备好的聊天客户端列表
        """

        # 获取当前战斗的最新回合
        last_round = self._game.current_combat_sequence.latest_round
        assert not last_round.is_completed, "当前没有进行中的战斗回合，不能生成卡牌。"

        # 创建聊天客户端列表
        chat_clients: List[ChatClient] = []

        # 获取当前回合数
        current_round_number = len(self._game.current_combat_sequence.current_rounds)

        # 为每个实体创建聊天客户端
        for entity in actor_entities:

            # 从映射表中获取技能列表
            available_skills = entity_card_count_map[entity.name]
            card_creation_count = len(available_skills)

            # 生成提示词
            prompt = _generate_round_prompt(
                actor_name=entity.name,
                card_creation_count=card_creation_count,
                action_order=last_round.action_order,
                selected_skills=available_skills,
                current_round_number=current_round_number,
            )

            # 创建聊天客户端
            chat_clients.append(
                ChatClient(
                    name=entity.name,
                    prompt=prompt,
                    context=self._game.get_agent_context(entity).context,
                )
            )

        # 返回聊天客户端列表
        return chat_clients

    #######################################################################################################################################
