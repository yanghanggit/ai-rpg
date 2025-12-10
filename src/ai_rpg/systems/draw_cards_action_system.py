"""
卡牌抽取系统
负责在战斗回合中为每个角色生成行动卡牌和状态效果。
第一回合生成初始卡牌(无update_hp)，后续回合基于战斗历史生成卡牌并更新生命值。
采用抽象提示词设计，只描述行动意图而不要求具体数值，遵循行动规划与数值解析分离的架构原则。
"""

import copy
import random
from typing import Final, List, Optional, final, override
from loguru import logger
from pydantic import BaseModel
from ..chat_services.client import ChatClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    DrawCardsAction,
    HandComponent,
    Card,
    StatusEffect,
    CombatStatsComponent,
    Skill,
    SkillBookComponent,
    DeathComponent,
)
from ..utils import extract_json_from_code_block
from ..demo.test_skills_pool import TEST_SKILLS_POOL
from langchain_core.messages import AIMessage


#######################################################################################################################################
@final
class DrawCardsResponse(BaseModel):
    update_hp: Optional[float] = None
    cards: List[Card] = []
    status_effects: List[StatusEffect] = []


#######################################################################################################################################
def _generate_first_round_prompt(
    actor_name: str,
    card_creation_count: int,
    action_order: List[str],
    selected_skills: List[Skill],
    current_round_number: int,
) -> str:
    """
    生成战斗第一回合的卡牌抽取提示词。

    用于战斗开局时指导AI角色评估战场态势，生成初始行动卡牌和自身状态效果。
    此提示词不包含update_hp字段，因为第一回合尚未发生伤害计算。

    Args:
        card_creation_count: 需要生成的卡牌数量
        round_turns: 角色行动顺序列表，格式为["角色名1", "角色名2", ...]
        current_round_number: 当前回合数

    Returns:
        str: 格式化的提示词，包含行动顺序、生成规则和JSON输出格式
    """
    assert card_creation_count > 0, "card_creation_count must be greater than 0"
    assert len(action_order) > 0, "round_turns must not be empty"

    # 格式化技能列表
    skills_text = "\n".join(
        [f"- {skill.name}: {skill.description}" for skill in selected_skills]
    )

    return f"""# 指令！这是第 {current_round_number} 回合，战斗开局，评估当前态势，生成你的 {card_creation_count} 张卡牌。

## 1. 场景内角色行动顺序(从左到右，先行动者可能影响战局与后续行动)

{action_order}

## 2. 可用技能池(必须从中选择)

{skills_text}

## 3. 生成内容规则

**重要约束：所有攻击必定命中目标，游戏中不存在影响攻击是否命中或被闪避的任何机制，禁止生成与此相关的卡牌代价和状态效果(status_effects)**

**卡牌(cards)**：你本回合可执行的行动
- 设计要求：
  * 优先组合2-3个技能创造复合行动
  * 技能组合产生协同效果但代价叠加
  * 单一技能仅用于简单直接行动
- 卡牌命名：基于技能效果创造新颖行动名称(禁止暴露技能名)
- 卡牌描述：行动方式、战斗目的、使用代价
- 禁止生成与命中，精准度或闪避相关的战斗目的和使用代价

**状态效果(status_effects)**：你当前回合新增的自身状态
- 战斗开局产生的初始状态（战斗准备、环境影响、心理状态、装备效果、过往经验等）
- 可同时存在多个状态效果
- 不要重复生成已存在的状态效果
- 禁止生成与命中，精准度或闪避相关的状态效果

## 4. 输出格式(JSON)

```json
{{
  "cards": [
    {{
      "name": "[组合技能效果的创意名称]",
      "description": "[先做什么,然后做什么的连贯动作描述]，[目的]。代价：[多重代价的叠加描述]",
      "targets": ["[目标角色1]", "[目标角色2]"]
    }}
  ],
  "status_effects": [
    {{
      "name": "[状态名称]",
      "description": "[状态产生原因的生动有趣描述]，[状态效果的具体影响，可包含具体数值]",
      "duration": [持续回合数]
    }}
  ]
}}
```

**约束规则**：
- 卡牌数量必须是{card_creation_count}张
- cards的description禁止出现具体数值，保持抽象描述
- status_effects的description可以包含具体数值，但不能有百分比数值
- description中禁止出现角色名称
- 禁用换行/空行，严格输出合规JSON"""


#######################################################################################################################################
def _generate_subsequent_round_prompt(
    actor_name: str,
    card_creation_count: int,
    action_order: List[str],
    selected_skills: List[Skill],
    current_round_number: int,
) -> str:
    """
    生成战斗第二回合及以后的卡牌抽取提示词。

    用于指导AI角色回顾战斗历史，更新自身状态，并生成后续行动卡牌。
    此提示词包含update_hp字段，要求从"计算过程"中提取当前生命值。

    Args:
        actor_name: 角色名称
        card_creation_count: 需要生成的卡牌数量
        round_turns: 角色行动顺序列表，格式为["角色名1", "角色名2", ...]
        current_round_number: 当前回合数

    Returns:
        str: 格式化的提示词，包含行动顺序、生成规则和JSON输出格式
    """
    assert card_creation_count > 0, "card_creation_count must be greater than 0"
    assert len(action_order) > 0, "round_turns must not be empty"

    # 格式化技能列表
    skills_text = "\n".join(
        [f"- {skill.name}: {skill.description}" for skill in selected_skills]
    )

    return f"""# 指令！这是第 {current_round_number} 回合，回顾战斗历史，评估当前态势，生成你的 {card_creation_count} 张卡牌。

## 1. 场景内角色行动顺序(从左到右，先行动者可能影响战局与后续行动)

{action_order}

## 2. 可用技能池(必须从中选择)

{skills_text}

## 3. 生成内容规则

**重要约束：所有攻击必定命中目标，游戏中不存在影响攻击是否命中或被闪避的任何机制，禁止生成与此相关的卡牌代价和状态效果(status_effects)**

**update_hp**：你的当前生命值(从最近"计算过程"的角色状态中提取当前HP数值)

**卡牌(cards)**：你本回合可执行的行动
- 设计要求：
  * 优先组合2-3个技能创造复合行动
  * 技能组合产生协同效果但代价叠加
  * 单一技能仅用于简单直接行动
- 卡牌命名：基于技能效果创造新颖行动名称(禁止暴露技能名)
- 卡牌描述：行动方式、战斗目的、使用代价
- 禁止生成与命中，精准度或闪避相关的战斗目的和使用代价

**状态效果(status_effects)**：你当前回合新增的自身状态
- 上回合受到的卡牌效果和使用代价产生的状态
- 可同时存在多个状态效果
- 不要重复生成已存在的状态效果
- 禁止生成与命中，精准度或闪避相关的状态效果

**特殊情况**：如果你已死亡(HP≤0)或认为战斗结束，则cards和status_effects填空数组，但update_hp仍需填写

## 4. 输出格式(JSON)

```json
{{
  "update_hp": [当前HP数值],
  "cards": [
    {{
      "name": "[组合技能效果的创意名称]",
      "description": "[先做什么,然后做什么的连贯动作描述]，[目的]。代价：[多重代价的叠加描述]",
      "targets": ["[目标角色1]", "[目标角色2]"]
    }}
  ],
  "status_effects": [
    {{
      "name": "[状态名称]",
      "description": "[状态产生原因的生动有趣描述]，[状态效果的具体影响，可包含具体数值]",
      "duration": [持续回合数]
    }}
  ]
}}
```

**约束规则**：
- 卡牌数量必须是{card_creation_count}张
- cards的description禁止出现具体数值，保持抽象描述
- status_effects的description可以包含具体数值，但不能有百分比数值
- description中禁止出现角色名称
- 禁用换行/空行，严格输出合规JSON"""


#######################################################################################################################################
def _generate_compressd_round_prompt(
    actor_name: str,
    card_creation_count: int,
    action_order: List[str],
    current_round_number: int,
) -> str:
    return f"""# 指令！这是第 {current_round_number} 回合，回顾战斗历史，评估当前态势，生成你的参战信息，并以JSON格式返回。

## 场景内角色行动顺序(从左到右，先行动者可能影响战局与后续行动)

{action_order}

## 参战信息内容

- 生成 {card_creation_count} 张卡牌(cards)
- 更新 当前生命值(update_hp)
- 生成 当前回合新增状态效果(status_effects)"""


#######################################################################################################################################
def _format_status_effects_message(status_effects: List[StatusEffect]) -> str:
    """
    格式化状态效果列表为通知消息。

    Args:
        status_effects: 状态效果列表

    Returns:
        str: 格式化的状态效果通知消息
    """
    effects_text = (
        "\n".join(
            [f"- {e.name}({e.duration}轮): {e.description}" for e in status_effects]
        )
        if len(status_effects) > 0
        else "- 无"
    )

    return f"""# 通知！你的 状态效果(status_effects) 已更新

{effects_text}"""


#######################################################################################################################################
@final
class DrawCardsActionSystem(ReactiveProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: Final[TCGGame] = game_context
        self._card_creation_count: Final[int] = 2

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

        # 根据当前回合数选择提示词生成方式
        if len(self._game.current_combat_sequence.current_rounds) == 1:
            logger.debug("第一回合卡牌生成")
        else:
            logger.debug("第二回合及以后卡牌生成")

        # 清除手牌，准备重新生成
        self._game.clear_hands()

        # 生成请求
        chat_clients: List[ChatClient] = self._create_chat_clients(
            entities, len(self._game.current_combat_sequence.current_rounds) == 1
        )

        # 语言服务
        await ChatClient.gather_request_post(clients=chat_clients)

        # 处理角色规划请求
        for chat_client in chat_clients:

            entity = self._game.get_entity_by_name(chat_client.name)
            assert entity is not None, f"Entity {chat_client.name} not found in game."

            self._process_draw_cards_response(
                entity,
                chat_client,
                len(self._game.current_combat_sequence.current_rounds) > 1,
            )

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
                message_content="# 指令！回顾战斗历史，评估当前态势，生成你的参战信息",
            )

            # 添加AI消息，包括响应内容。
            self._game.add_ai_message(
                entity,
                [AIMessage(content="未能生成参战信息，默认执行等待动作。")],
            )

    #######################################################################################################################################
    def _process_draw_cards_response(
        self, entity: Entity, chat_client: ChatClient, need_update_health: bool
    ) -> None:
        """
        处理LLM返回的抽卡响应并应用到实体。

        解析ChatClient的JSON响应，提取卡牌、生命值更新和状态效果，
        然后更新实体的HandComponent、CombatStatsComponent等组件。
        如果解析失败，会记录错误日志但不会中断游戏流程。

        Args:
            entity: 目标角色实体
            chat_client: 包含LLM响应内容的聊天客户端
            need_update_health: 是否需要更新生命值（第一回合为False，后续回合为True）
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

            # 更新健康属性。
            if need_update_health:
                self._update_combat_health(
                    entity,
                    validated_response.update_hp,
                )

            # 更新状态效果。
            self._append_status_effects(entity, validated_response.status_effects)

        except Exception as e:
            logger.error(f"{chat_client.response_content}")
            logger.error(f"Exception: {e}")

    #######################################################################################################################################
    def _get_available_skills(self, entity: Entity) -> List[Skill]:
        """获取实体可用的技能列表。

        Args:
            entity (Entity): 目标实体

        Returns:
            List[Skill]: 实体可用的技能列表
        """

        skill_book_comp = entity.get(SkillBookComponent)
        assert skill_book_comp is not None, "Entity must have SkillBookComponent"
        if len(skill_book_comp.skills) == 0:
            logger.warning(f"entity {entity.name} has no skills in SkillBookComponent")
            return TEST_SKILLS_POOL

        return skill_book_comp.skills.copy()

    #######################################################################################################################################
    def _create_chat_clients(
        self, actor_entities: List[Entity], is_first_round: bool
    ) -> List[ChatClient]:
        """
        为每个角色实体创建聊天客户端以请求LLM生成卡牌。

        根据是否为第一回合选择合适的提示词模板，
        为每个实体构建包含上下文的ChatClient对象，准备发起LLM请求。

        Args:
            actor_entities: 需要生成卡牌的角色实体列表
            is_first_round: 是否为战斗第一回合

        Returns:
            List[ChatClient]: 准备好的聊天客户端列表
        """

        # 获取当前战斗的最新回合
        last_round = self._game.current_combat_sequence.latest_round
        assert not last_round.is_completed, "当前没有进行中的战斗回合，不能生成卡牌。"

        # 创建聊天客户端列表
        chat_clients: List[ChatClient] = []

        # 为每个实体创建聊天客户端
        for entity in actor_entities:

            # 从技能池随机抽取 card_creation_count * 3 个技能作为子池
            skill_pool = self._get_available_skills(entity)
            skill_pool_size = min(self._card_creation_count * 2, len(skill_pool))
            selected_skills = random.sample(skill_pool, skill_pool_size)

            # 获取当前回合数
            current_round_number = len(
                self._game.current_combat_sequence.current_rounds
            )

            # 根据当前回合数选择提示词生成方式
            if is_first_round:
                # 处理战斗第一回合请求
                prompt = _generate_first_round_prompt(
                    actor_name=entity.name,
                    card_creation_count=self._card_creation_count,
                    action_order=last_round.action_order,
                    selected_skills=selected_skills,
                    current_round_number=current_round_number,
                )
            else:
                # 处理战斗后续回合请求
                prompt = _generate_subsequent_round_prompt(
                    actor_name=entity.name,
                    card_creation_count=self._card_creation_count,
                    action_order=last_round.action_order,
                    selected_skills=selected_skills,
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
    def _update_combat_health(self, entity: Entity, update_hp: Optional[float]) -> None:
        """
        更新实体的战斗生命值。

        从LLM响应中提取的生命值更新到实体的CombatStatsComponent。
        仅在后续回合调用，第一回合不需要更新生命值。

        Args:
            entity: 需要更新生命值的实体
            update_hp: 新的生命值，如果为None则不更新
        """

        combat_stats_comp = entity.get(CombatStatsComponent)
        assert combat_stats_comp is not None, "Entity must have CombatStatsComponent"
        if update_hp is not None:
            combat_stats_comp.stats.hp = int(update_hp)
            logger.debug(f"{entity.name} => hp: {combat_stats_comp.stats.hp}")

    ###############################################################################################################################################
    def _append_status_effects(
        self, entity: Entity, status_effects: List[StatusEffect]
    ) -> None:
        """
        添加新的状态效果到实体并发送通知消息。

        将LLM生成的状态效果添加到实体的CombatStatsComponent中，
        并通过游戏消息系统通知角色其状态效果已更新。

        Args:
            entity: 目标实体
            status_effects: 需要添加的状态效果列表
        """

        # 效果更新
        combat_stats_comp = entity.get(CombatStatsComponent)
        assert combat_stats_comp is not None, "Entity must have CombatStatsComponent"

        combat_stats_comp.status_effects.extend(copy.copy(status_effects))

        updated_status_effects_message = _format_status_effects_message(
            combat_stats_comp.status_effects
        )

        self._game.add_human_message(entity, updated_status_effects_message)

    #######################################################################################################################################
