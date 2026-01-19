"""
卡牌抽取系统模块

该模块实现了战斗回合中的卡牌生成机制，负责将角色技能转化为可执行的行动卡牌。

核心特性：
- 单技能单卡牌：每个 DrawCardsAction 携带一个技能，生成一张对应的行动卡牌
- 外部决策：技能选择由 activate_actor_card_draws 函数负责，系统仅执行生成
- LLM驱动：通过语言模型生成富有创意且符合角色特征的卡牌名称和描述
- 数据流清晰：DrawCardsAction.skill → 提示词生成 → 卡牌生成

主要组件：
- DrawCardsActionSystem: 核心系统类，协调整个卡牌生成流程
- _generate_round_prompt: 生成完整的LLM请求提示词
- _generate_compressd_round_prompt: 生成用于历史记录的压缩提示词
"""

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
    specified_targets: List[str],
    current_round_number: int,
) -> str:
    """
    生成战斗回合的卡牌抽取提示词。

    要求LLM为提供的技能生成对应的卡牌，不进行技能组合。
    当前版本：每次调用使用单个技能，生成一张卡牌。
    targets由系统指定，Agent只需生成name和description。

    Args:
        actor_name: 角色名称（当前未使用）
        card_creation_count: 需要生成的卡牌数量（固定为1）
        action_order: 角色行动顺序列表
        selected_skills: 技能列表（当前固定为1个元素）
        specified_targets: 指定的目标列表（供Agent理解战术意图）
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

    # 格式化目标列表
    targets_text = "\n".join([f"- {target}" for target in specified_targets])

    return f"""# 指令！第 {current_round_number} 回合：生成 {card_creation_count} 张卡牌，以JSON格式返回。

## 1. 本回合行动顺序

{action_order}

先手角色的卡牌会先生效，影响后续角色的战场状态。

## 2. 生成卡牌

### 2.1 可用技能池

{skills_text}

### 2.2 指定目标

本次行动的目标已确定为：

{targets_text}

### 2.3 卡牌生成规则

- 设计要求：为指定技能生成针对上述目标的行动卡牌
- 卡牌命名：基于技能效果和目标特点创造行动名称(禁止暴露技能名)
- 卡牌描述：行动方式、战术目的、使用代价

## 3. 输出格式(JSON)

```json
{{
  "cards": [
    {{
      "name": "[行动名称]",
      "description": "[行动描述]"
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
        self._card_creation_count: Final[int] = 1

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
            logger.debug(f"last_round.has_ended, so setup new round")
            self._game.create_next_round()

        logger.debug(
            f"当前回合数: {len(self._game.current_combat_sequence.current_rounds)}"
        )
        assert (
            len(self._game.current_combat_sequence.current_rounds) > 0
        ), "当前没有进行中的战斗，不能设置回合。"

        # 清除手牌，准备重新生成
        self._game.clear_hands()

        # 为每个实体提取技能和目标，构建映射表
        entity_skill_map: Dict[str, Skill] = {}
        entity_targets_map: Dict[str, List[str]] = {}
        for entity in entities:
            draw_cards_action = entity.get(DrawCardsAction)
            assert (
                draw_cards_action is not None
            ), f"Entity {entity.name} must have DrawCardsAction"
            assert (
                draw_cards_action.skill is not None
            ), f"DrawCardsAction.skill must not be None for {entity.name}"
            entity_skill_map[entity.name] = draw_cards_action.skill
            entity_targets_map[entity.name] = draw_cards_action.targets

        # 生成请求
        chat_clients: List[ChatClient] = self._create_chat_clients(
            entities, entity_skill_map, entity_targets_map
        )

        # 语言服务
        await ChatClient.gather_request_post(clients=chat_clients)

        # 处理角色规划请求
        for chat_client in chat_clients:

            found_entity = self._game.get_entity_by_name(chat_client.name)
            assert (
                found_entity is not None
            ), f"Entity {chat_client.name} not found in game."

            # 处理卡牌生成响应
            self._process_draw_cards_response(found_entity, chat_client)

        # 最后的兜底，遍历所有参与的角色，如果没有手牌，说明_process_draw_cards_response出现了错误，可能是LLM返回的内容无法正确解析。此时，就需要给角色一个默认的手牌，避免游戏卡死。
        self._ensure_all_entities_have_hands(entities)

    #######################################################################################################################################
    def _ensure_all_entities_have_hands(self, entities: List[Entity]) -> None:
        """
        确保所有实体都有手牌组件的兜底机制。
        如果某个实体缺少HandComponent，说明_process_draw_cards_response出现了错误，
        可能是LLM返回的内容无法正确解析。此时给角色一个应急应对卡牌，避免游戏卡死。

        Args:
            entities: 需要检查的实体列表
        """
        # 获取当前回合信息
        last_round = self._game.current_combat_sequence.latest_round
        current_round_number = len(self._game.current_combat_sequence.current_rounds)
        # card_creation_count = 1

        for entity in entities:

            if entity.has(HandComponent) or entity.has(DeathComponent):
                continue

            # 兜底卡牌的目标固定为自己
            fallback_card = Card(
                name="应急应对",
                description="行动计划出现偏差，暂时采取保守策略观察战局",
                targets=[entity.name],
            )

            entity.replace(
                HandComponent,
                entity.name,
                [fallback_card],
            )

            # 模拟历史上下文，使用与正常流程一致的压缩提示词
            self._game.add_human_message(
                entity=entity,
                message_content=_generate_compressd_round_prompt(
                    actor_name=entity.name,
                    card_creation_count=self._card_creation_count,
                    action_order=last_round.action_order,
                    current_round_number=current_round_number,
                ),
            )

            # 模拟AI响应，将fallback_card序列化为JSON格式
            fallback_response = DrawCardsResponse(cards=[fallback_card])
            fallback_json = fallback_response.model_dump_json(indent=2)

            self._game.add_ai_message(
                entity,
                [AIMessage(content=f"```json\n{fallback_json}\n```")],
            )

    #######################################################################################################################################
    def _process_draw_cards_response(
        self, entity: Entity, chat_client: ChatClient
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
                    card_creation_count=self._card_creation_count,
                    action_order=last_round.action_order,
                    current_round_number=len(
                        self._game.current_combat_sequence.current_rounds
                    ),
                ),
                compressed_prompt=chat_client.prompt,
            )

            # 添加AI消息，包括响应内容。
            self._game.add_ai_message(entity, chat_client.response_ai_messages)

            # 从DrawCardsAction获取targets
            draw_cards_action = entity.get(DrawCardsAction)
            assert (
                draw_cards_action is not None
            ), f"Entity {entity.name} must have DrawCardsAction"
            specified_targets = draw_cards_action.targets

            # 生成的结果（Agent只生成了name和description）
            # 需要手动填充targets字段
            cards: List[Card] = []
            for card_data in validated_response.cards:
                # 创建完整的Card对象，使用DrawCardsAction中的targets
                complete_card = Card(
                    name=card_data.name,
                    description=card_data.description,
                    targets=specified_targets,
                )
                cards.append(complete_card)

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
    #######################################################################################################################################
    def _create_chat_clients(
        self,
        actor_entities: List[Entity],
        entity_skill_map: Dict[str, Skill],
        entity_targets_map: Dict[str, List[str]],
    ) -> List[ChatClient]:
        """
        为每个角色实体创建聊天客户端以请求LLM生成卡牌。

        为每个实体构建包含上下文的ChatClient对象，准备发起LLM请求。

        Args:
            actor_entities: 需要生成卡牌的角色实体列表
            entity_skill_map: 实体名称到单个技能的映射表
            entity_targets_map: 实体名称到目标列表的映射表

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

            # 从映射表中获取单个技能和目标列表
            skill = entity_skill_map[entity.name]
            targets = entity_targets_map[entity.name]

            # 生成提示词
            prompt = _generate_round_prompt(
                actor_name=entity.name,
                card_creation_count=1,
                action_order=last_round.action_order,
                selected_skills=[skill],
                specified_targets=targets,
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
