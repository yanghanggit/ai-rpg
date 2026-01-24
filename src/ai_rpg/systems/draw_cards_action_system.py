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

from typing import Final, List, final, override
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
    CharacterStats,
    StatusEffect,
    CombatStatsComponent,
    InventoryComponent,
)
from ..utils import extract_json_from_code_block
from langchain_core.messages import AIMessage


#######################################################################################################################################
@final
class DrawCardsResponse(BaseModel):
    """单卡响应模型，每次生成一张卡牌"""

    name: str
    description: str
    final_attack: int
    final_defense: int


#######################################################################################################################################
def _generate_round_prompt(
    selected_skills: List[Skill],
    specified_targets: List[str],
    actor_stats: CharacterStats,
    actor_status_effects: List[StatusEffect],
    current_round_number: int,
) -> str:
    """
    生成战斗回合的卡牌抽取提示词。

    采用 Input → Transform → Output 结构，明确卡牌作为"战斗结算单元"的概念，
    要求LLM基于输入的基础属性、状态效果和技能，计算最终攻防数值并生成战斗卡牌。
    使用第一人称叙事风格，强调输出数值为最终值（非增量）。每次调用生成一张卡牌。

    Args:
        selected_skills: 使用的技能列表（固定为1个元素）
        specified_targets: 指定的目标列表（由系统确定）
        actor_stats: 角色当前属性数据（包含 hp/max_hp/attack/defense）
        actor_status_effects: 角色当前状态效果列表（第一人称描述）
        current_round_number: 当前回合数

    Returns:
        str: 格式化的完整提示词，包含卡牌概念说明、输入数据、转换规则和输出格式
    """

    # 格式化基础属性
    actor_stats_prompt = f"HP:{actor_stats.hp}/{actor_stats.max_hp} | 攻击:{actor_stats.attack} | 防御:{actor_stats.defense}"

    # 格式化技能列表
    skills_text = "\n".join(
        [f"- {skill.name}: {skill.description}" for skill in selected_skills]
    )

    # 格式化目标列表
    targets_text = "\n".join([f"- {target}" for target in specified_targets])

    # 格式化状态效果列表
    if actor_status_effects:
        effects_text = "\n".join(
            [
                f"- {effect.name}: {effect.description}"
                for effect in actor_status_effects
            ]
        )
    else:
        effects_text = "无"

    return f"""# 指令！第 {current_round_number} 回合：生成战斗卡牌(JSON)

**卡牌**封装本回合行动信息（名称、描述、攻防、目标），由战斗系统结算。

## 输入

**目标**: 
{targets_text}

**属性**: {actor_stats_prompt}

**状态**: 
{effects_text}

**技能**: 
{skills_text}

## 格式要求

**命名**: 基于技能效果创造名称，禁止暴露技能名

**描述**(必须包含段落标记)：
1. **【行动】** 第一人称动作与战术意图(1-2句)
2. **【机制】** 声明战斗规则，禁止"部分""可能"等模糊词
   - 示例: "本次攻击无视目标所有防御" "获得+2攻击"
3. **【代价】** 风险/消耗(可选)

**数值**: 增益/减益/复合/条件/环境类影响攻防。输出最终值(非增量)

## 输出JSON

```json
{{
  "name": "行动名",
  "description": "四段式描述",
  "final_attack": 0,
  "final_defense": 0
}}
```"""


#######################################################################################################################################
def _generate_compressd_round_prompt(
    current_round_number: int,
) -> str:
    """
    生成压缩版本的回合提示词，用于保存到上下文历史。

    与完整提示词相比，该版本极度简化，仅包含回合数和操作指令，
    用于减少上下文token消耗。

    Args:
        current_round_number: 当前回合数

    Returns:
        str: 压缩后的提示词
    """
    return f"""# 指令！第 {current_round_number} 回合：生成战斗卡牌(JSON)

**卡牌**封装行动信息，由战斗系统结算。"""


#######################################################################################################################################
@final
class DrawCardsActionSystem(ReactiveProcessor):
    """
    卡牌抽取系统

    负责在战斗回合中为每个角色生成行动卡牌。

    工作流程：
    - 接收 DrawCardsAction（包含技能、目标、状态效果）
    - 为每个角色创建LLM请求，生成卡牌名称、描述和数值
    - 数值设计：基础属性 × 状态效果修正
    - 每个DrawCardsAction生成一张卡牌
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
            logger.debug(f"last_round.has_ended, so setup new round")
            self._game.create_next_round()

        # logger.debug(
        #     f"当前回合数: {len(self._game.current_combat_sequence.current_rounds)}"
        # )
        assert (
            len(self._game.current_combat_sequence.current_rounds) > 0
        ), "当前没有进行中的战斗，不能设置回合。"

        # 清除手牌，准备重新生成
        self._game.clear_hands()

        # 为每个实体创建聊天客户端
        chat_clients: List[ChatClient] = []
        for entity in entities:
            draw_cards_action = entity.get(DrawCardsAction)
            assert (
                draw_cards_action is not None
            ), f"Entity {entity.name} must have DrawCardsAction"
            assert (
                draw_cards_action.skill is not None
            ), f"DrawCardsAction.skill must not be None for {entity.name}"

            chat_client = self._create_chat_client(
                entity,
                draw_cards_action.skill,
                draw_cards_action.targets,
                draw_cards_action.status_effects,
            )
            chat_clients.append(chat_client)

        # 语言服务
        await ChatClient.batch_chat(clients=chat_clients)

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
    def _process_draw_cards_response(
        self, entity: Entity, chat_client: ChatClient
    ) -> None:
        """
        处理LLM返回的抽卡响应并应用到实体。

        解析ChatClient的JSON响应，提取卡牌名称、描述和数值，
        然后更新实体的HandComponent。
        如果解析失败，会记录错误日志但不会中断游戏流程。

        Args:
            entity: 目标角色实体
            chat_client: 包含LLM响应内容的聊天客户端
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

            # 从响应构建 CharacterStats
            card_stats = CharacterStats(
                # hp=validated_response.hp,
                max_hp=0,  # max_hp 不由 Agent 生成
                attack=validated_response.final_attack,
                defense=validated_response.final_defense,
            )

            # 创建完整的Card对象
            card = Card(
                name=validated_response.name,
                description=validated_response.description,
                stats=card_stats,
                targets=specified_targets,
                status_effects=draw_cards_action.status_effects,
            )

            # 从InventoryComponent继承物品词条到卡牌词条
            inventory_comp = entity.get(InventoryComponent)
            assert (
                inventory_comp is not None
            ), f"Entity {entity.name} must have InventoryComponent"
            for item in inventory_comp.items:
                card.affixes.extend(item.affixes)

            # 更新手牌
            entity.replace(
                HandComponent,
                entity.name,
                [card],
            )

        except Exception as e:
            logger.error(f"{chat_client.response_content}")
            logger.error(f"Exception: {e}")

    #######################################################################################################################################
    def _create_chat_client(
        self,
        entity: Entity,
        skill: Skill,
        targets: List[str],
        status_effects: List[StatusEffect],
    ) -> ChatClient:
        """
        为单个角色实体创建聊天客户端以请求LLM生成卡牌。

        Args:
            entity: 角色实体
            skill: 使用的技能
            targets: 目标列表
            status_effects: 状态效果列表

        Returns:
            ChatClient: 准备好的聊天客户端
        """
        # 获取当前战斗的最新回合
        last_round = self._game.current_combat_sequence.latest_round
        assert not last_round.is_completed, "当前没有进行中的战斗回合，不能生成卡牌。"

        # 获取当前回合数
        current_round_number = len(self._game.current_combat_sequence.current_rounds)

        # 获取角色属性信息
        combat_stats_comp = entity.get(CombatStatsComponent)
        assert (
            combat_stats_comp is not None
        ), f"Entity {entity.name} must have CombatStatsComponent"

        # 生成提示词
        prompt = _generate_round_prompt(
            selected_skills=[skill],
            specified_targets=targets,
            actor_stats=combat_stats_comp.stats,
            actor_status_effects=status_effects,
            current_round_number=current_round_number,
        )

        # 创建并返回聊天客户端
        return ChatClient(
            name=entity.name,
            prompt=prompt,
            context=self._game.get_agent_context(entity).context,
        )

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
        current_round_number = len(self._game.current_combat_sequence.current_rounds)

        for entity in entities:

            if entity.has(HandComponent) or entity.has(DeathComponent):
                continue

            # 兜底卡牌的目标固定为自己
            fallback_card = Card(
                name="应急应对",
                description="行动计划出现偏差，暂时采取保守策略观察战局",
                stats=CharacterStats(hp=0, max_hp=0, attack=0, defense=0),
                targets=[entity.name],
                status_effects=[],
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
                    current_round_number=current_round_number,
                ),
            )

            # 模拟AI响应，将fallback_card序列化为JSON格式
            fallback_response = DrawCardsResponse(
                name=fallback_card.name,
                description=fallback_card.description,
                final_attack=fallback_card.stats.attack,
                final_defense=fallback_card.stats.defense,
            )
            fallback_json = fallback_response.model_dump_json(indent=2)

            self._game.add_ai_message(
                entity,
                [AIMessage(content=f"```json\n{fallback_json}\n```")],
            )

    #######################################################################################################################################
