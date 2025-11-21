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
    InventoryComponent,
    ItemType,
    Skill,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
# 做一个测试！
TEST_SKILLS_POOL: Final[List[Skill]] = [
    # 原有技能...
    Skill(
        name="时间窃贼",
        description="偷取目标的时间流，使其动作延迟3回合，但自己会加速衰老，永久损失部分最大生命值。",
    ),
    Skill(
        name="量子分身",
        description="同时存在于多个平行宇宙，闪避所有攻击并同时攻击所有敌人，结束后有几率迷失在错误的时间线中。",
    ),
    Skill(
        name="情绪感染",
        description="将自己的强烈情绪传递给敌人，使其陷入相同的精神状态（狂暴/恐惧/混乱），但自己也会情绪失控数回合。",
    ),
    Skill(
        name="维度折叠",
        description="将战场空间折叠，使所有远程攻击失效，但折叠的空间可能释放出未知的维度生物。",
    ),
    Skill(
        name="记忆掠夺",
        description="读取并复制目标的技能记忆，暂时获得对方的一个随机技能，但会承受对方的痛苦回忆作为精神伤害。",
    ),
    Skill(
        name="因果逆转",
        description="先设定结果再触发原因，本次攻击必中且暴击，但接下来3回合内自己的所有行动都会受到因果反噬。",
    ),
    Skill(
        name="血肉傀儡",
        description="用自己的血肉制造一个分身吸引火力，分身的生命值越高，自己流失的生命越多，且分身可能产生独立意识反叛。",
    ),
    Skill(
        name="梦境入侵",
        description="将敌人拉入自己编织的噩梦，造成持续精神伤害，但如果对方精神力过强，自己可能被困在共享噩梦中。",
    ),
    Skill(
        name="重力操控",
        description="瞬间改变局部重力，使敌人被压倒在地无法行动，但过度使用会导致自身骨骼承受巨大压力。",
    ),
    Skill(
        name="元素崩坏",
        description="打破元素平衡，引发随机元素爆炸，效果惊人但可能引发连锁反应，使战场环境变得极端危险。",
    ),
    Skill(
        name="幸运借贷",
        description="向未来借取幸运值，大幅提升暴击率和闪避率，但后续战斗会持续遭遇厄运，直到偿还 幸运债务。",
    ),
    Skill(
        name="感官共享",
        description="与目标共享五感，可以预判其行动并找到弱点，但也会承受对方受到的所有痛苦和负面感受。",
    ),
    Skill(
        name="概念抹除",
        description="暂时从概念上抹除自己的 存在 ，免疫一切伤害，但重新存在时可能被世界排斥，属性大幅下降。",
    ),
    Skill(
        name="生命共鸣",
        description="与战场上的所有生命体建立共鸣，每个活着的单位都会为自己提供治疗，但也会分担他们受到的伤害。",
    ),
    Skill(
        name="龙之化身",
        description="将自身变形为巨龙形态,获得强大的力量和飞行能力,但变身结束后会陷入虚弱状态。",
    ),
    Skill(
        name="物质重组",
        description="将敌人的装备或武器重组为无用物品，成功则削弱敌人，失败则自己的装备会被随机重组。",
    ),
    Skill(
        name="痛觉转化",
        description="将受到的伤害转化为攻击力，受伤越重攻击越强，但痛觉会被放大数倍，可能导致精神崩溃。",
    ),
    Skill(
        name="命运赌局",
        description="与命运之神进行赌局，50%几率秒杀目标，50%几率自己受到致命伤害，无法被复活技能抵消。",
    ),
    Skill(
        name="镜像世界",
        description="创造现实世界的镜像，所有攻击都会反射给攻击者，但镜像可能破碎，导致空间碎片伤害所有人。",
    ),
    Skill(
        name="空鲸形态",
        description="变身为游弋在空间裂缝中的虚空鲸,能够穿梭空间、吞噬敌人的空间攻击,但可能迷失在维度间隙中。",
    ),
]


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
) -> str:
    """
    生成战斗第一回合的卡牌抽取提示词。

    用于战斗开局时指导AI角色评估战场态势，生成初始行动卡牌和自身状态效果。
    此提示词不包含update_hp字段，因为第一回合尚未发生伤害计算。

    Args:
        card_creation_count: 需要生成的卡牌数量
        round_turns: 角色行动顺序列表，格式为["角色名1", "角色名2", ...]

    Returns:
        str: 格式化的提示词，包含行动顺序、生成规则和JSON输出格式
    """
    assert card_creation_count > 0, "card_creation_count must be greater than 0"
    assert len(action_order) > 0, "round_turns must not be empty"

    # 格式化技能列表
    skills_text = "\n".join(
        [f"- {skill.name}: {skill.description}" for skill in selected_skills]
    )

    return f"""# 指令！战斗开局，评估当前态势，生成你的初始 {card_creation_count} 张卡牌。

## 1. 场景内角色行动顺序(从左到右，先行动者可能影响战局与后续行动)

{action_order}

## 2. 可用技能池(必须从中选择)

{skills_text}

## 3. 生成内容规则

**卡牌(cards)**：你本回合可执行的行动
- 设计要求：
  * 优先组合2-3个技能创造复合行动
  * 技能组合产生协同效果但代价叠加
  * 单一技能仅用于简单直接行动
- 卡牌命名：基于技能效果创造新颖行动名称(禁止暴露技能名)
- 卡牌描述：行动方式、战斗目的、使用代价

**状态效果(status_effects)**：你当前回合新增的自身状态
- 战斗开局产生的初始状态（战斗准备、环境影响、心理状态、装备效果、过往经验等）
- 可同时存在多个状态效果
- 不要重复生成已存在的状态效果

## 4. 输出格式(JSON)

```json
{{
  "cards": [
    {{
      "name": "[组合技能效果的创意名称]",
      "description": "[先做什么,然后做什么的连贯动作描述]，[目的]。代价：[多重代价的叠加描述]",
      "target": "[目标角色完整名称]"
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
- status_effects的description可以包含具体数值
- description中禁止出现角色名称
- 禁用换行/空行，严格输出合规JSON"""


#######################################################################################################################################
def _generate_subsequent_round_prompt(
    actor_name: str,
    card_creation_count: int,
    action_order: List[str],
    selected_skills: List[Skill],
) -> str:
    """
    生成战斗第二回合及以后的卡牌抽取提示词。

    用于指导AI角色回顾战斗历史，更新自身状态，并生成后续行动卡牌。
    此提示词包含update_hp字段，要求从"计算过程"中提取当前生命值。

    Args:
        actor_name: 角色名称
        card_creation_count: 需要生成的卡牌数量
        round_turns: 角色行动顺序列表，格式为["角色名1", "角色名2", ...]

    Returns:
        str: 格式化的提示词，包含行动顺序、生成规则和JSON输出格式
    """
    assert card_creation_count > 0, "card_creation_count must be greater than 0"
    assert len(action_order) > 0, "round_turns must not be empty"

    # 格式化技能列表
    skills_text = "\n".join(
        [f"- {skill.name}: {skill.description}" for skill in selected_skills]
    )

    return f"""# 指令！回顾战斗历史，评估当前态势，生成你的 {card_creation_count} 张卡牌。

## 1. 场景内角色行动顺序(从左到右，先行动者可能影响战局与后续行动)

{action_order}

## 2. 可用技能池(必须从中选择)

{skills_text}

## 3. 生成内容规则

**update_hp**：你的当前生命值(从最近"计算过程"的角色状态中提取当前HP数值)

**卡牌(cards)**：你本回合可执行的行动
- 设计要求：
  * 优先组合2-3个技能创造复合行动
  * 技能组合产生协同效果但代价叠加
  * 单一技能仅用于简单直接行动
- 卡牌命名：基于技能效果创造新颖行动名称(禁止暴露技能名)
- 卡牌描述：行动方式、战斗目的、使用代价

**状态效果(status_effects)**：你当前回合新增的自身状态
- 上回合受到的卡牌效果和使用代价产生的状态
- 可同时存在多个状态效果
- 不要重复生成已存在的状态效果

**特殊情况**：如果你已死亡(HP≤0)或认为战斗结束，则cards和status_effects填空数组，但update_hp仍需填写

## 4. 输出格式(JSON)

```json
{{
  "update_hp": [当前HP数值],
  "cards": [
    {{
      "name": "[组合技能效果的创意名称]",
      "description": "[先做什么,然后做什么的连贯动作描述]，[目的]。代价：[多重代价的叠加描述]",
      "target": "[目标角色完整名称]"
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
- status_effects的description可以包含具体数值
- description中禁止出现角色名称
- 禁用换行/空行，严格输出合规JSON"""


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
def _format_removed_status_effects_message(removed_effects: List[StatusEffect]) -> str:
    """
    格式化被移除的状态效果列表为通知消息。

    Args:
        removed_effects: 被移除的状态效果列表

    Returns:
        str: 格式化的状态效果移除通知消息
    """
    effects_text = (
        "\n".join([f"- {e.name}: {e.description}" for e in removed_effects])
        if len(removed_effects) > 0
        else "- 无"
    )

    return f"""# 通知！如下 状态效果(status_effects) 被移除

{effects_text}"""


#######################################################################################################################################
def _test_and_notify_unique_items(game: TCGGame, entities: List[Entity]) -> None:
    """
    TODO, 后续会在其他系统做实现，放在这里仅测试。
    这是一个测试函数,用于验证实体是否正确拥有唯一道具,并确保相关提示词的唯一性。
    如果实体拥有唯一道具,则会在其对话中添加一条提示消息,说明其拥有该道具。
    同时,确保不会重复添加相同的提示消息。
    Args:
        entities: 需要检查的实体列表
    """

    for entity in entities:

        if not entity.has(InventoryComponent):
            continue

        inventory_comp = entity.get(InventoryComponent)
        assert inventory_comp is not None, "Entity must have InventoryComponent"
        if len(inventory_comp.items) == 0:
            continue

        for item in inventory_comp.items:
            if item.type == ItemType.UNIQUE_ITEM:
                logger.debug(
                    f"entity {entity.name} has unique item {item.model_dump_json()}"
                )

                existing_human_messages = game.find_human_messages_by_attribute(
                    actor_entity=entity,
                    attribute_key="test_unique_item",
                    attribute_value=item.name,
                )

                if len(existing_human_messages) > 0:
                    game.delete_human_messages_by_attribute(
                        actor_entity=entity,
                        human_messages=existing_human_messages,
                    )

                duplicate_message_test = game.find_human_messages_by_attribute(
                    actor_entity=entity,
                    attribute_key="test_unique_item",
                    attribute_value=item.name,
                )
                assert (
                    len(duplicate_message_test) == 0
                ), f"test_unique_item not deleted!"

                game.append_human_message(
                    entity,
                    f"""# 提示！你拥有道具: {item.name}。\n{item.model_dump_json()}""",
                    test_unique_item=item.name,
                )
            else:
                logger.debug(
                    f"entity {entity.name} has item {item.model_dump_json()}, 暂时不处理！"
                )


#######################################################################################################################################
@final
class DrawCardsActionSystem(ReactiveProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: TCGGame = game_context
        self._card_creation_count: Final[int] = 2

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(DrawCardsAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(DrawCardsAction)

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
            self._game.start_new_round()

        logger.debug(
            f"当前回合数: {len(self._game.current_combat_sequence.current_rounds)}"
        )
        assert (
            len(self._game.current_combat_sequence.current_rounds) > 0
        ), "当前没有进行中的战斗，不能设置回合。"

        # 测试道具的问题
        _test_and_notify_unique_items(self._game, entities)

        # 根据当前回合数选择提示词生成方式
        if len(self._game.current_combat_sequence.current_rounds) == 1:
            logger.debug("第一回合卡牌生成")
        else:

            logger.debug("第二回合及以后卡牌生成")
            # 注意！因为是第二局及以后，所以状态效果需要结算
            self._process_status_effects_settlement(entities)

        # 先清除
        self._clear_hands()

        # 生成请求
        request_handlers: List[ChatClient] = self._create_chat_clients(
            entities, len(self._game.current_combat_sequence.current_rounds) == 1
        )

        # 语言服务
        await ChatClient.gather_request_post(clients=request_handlers)

        # 处理角色规划请求
        for chat_client in request_handlers:

            entity = self._game.get_entity_by_name(chat_client.name)
            assert entity is not None, f"Entity {chat_client.name} not found in game."

            self._process_draw_cards_response(
                entity,
                chat_client,
                len(self._game.current_combat_sequence.current_rounds) > 1,
            )

        # 最后的兜底，遍历所有参与的角色，如果没有手牌，说明_process_draw_cards_response出现了错误，可能是LLM返回的内容无法正确解析。
        # 此时，就需要给角色一个默认的手牌，避免游戏卡死。
        self._ensure_all_entities_have_hands(entities)

    #######################################################################################################################################
    def _clear_hands(self) -> None:
        """
        清除所有角色实体的手牌组件。

        在新回合开始前调用，移除所有角色的HandComponent，
        为生成新的手牌做准备。这是每回合卡牌抽取流程的第一步。
        """
        actor_entities = self._game.get_group(Matcher(HandComponent)).entities.copy()
        for entity in actor_entities:
            logger.debug(f"clear hands: {entity.name}")
            entity.remove(HandComponent)

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

            if entity.has(HandComponent):
                continue

            combat_stats_comp = entity.get(CombatStatsComponent)
            assert combat_stats_comp is not None
            if combat_stats_comp.stats.hp <= 0:

                # 如果角色已经死亡，就不需要添加等待。
                logger.warning(
                    f"entity {entity.name} is dead (hp <= 0), no need to add default card"
                )
                continue

            wait_card = Card(
                name="等待",
                description="什么都不做，等待下一回合。",
                target=entity.name,
            )

            entity.replace(
                HandComponent,
                entity.name,
                [wait_card],
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

            # 生成的结果。
            cards: List[Card] = []
            for card_response in validated_response.cards:
                cards.append(
                    Card(
                        name=card_response.name,
                        description=card_response.description,
                        target=card_response.target,
                    )
                )

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
            skill_pool_size = min(self._card_creation_count * 2, len(TEST_SKILLS_POOL))
            selected_skills = random.sample(TEST_SKILLS_POOL, skill_pool_size)

            # 根据当前回合数选择提示词生成方式
            if is_first_round:
                # 处理战斗第一回合请求
                prompt = _generate_first_round_prompt(
                    actor_name=entity.name,
                    card_creation_count=self._card_creation_count,
                    action_order=last_round.action_order,
                    selected_skills=selected_skills,
                )
            else:
                # 处理战斗后续回合请求
                prompt = _generate_subsequent_round_prompt(
                    actor_name=entity.name,
                    card_creation_count=self._card_creation_count,
                    action_order=last_round.action_order,
                    selected_skills=selected_skills,
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

        self._game.append_human_message(entity, updated_status_effects_message)

    ###############################################################################################################################################
    def _settle_status_effects(
        self, entity: Entity
    ) -> tuple[List[StatusEffect], List[StatusEffect]]:
        """
        结算一次status_effect。
        所有的status_effect全部round - 1，如果round == 0则删除。

        Args:
            entity: 需要结算状态效果的实体

        Returns:
            tuple: (剩余的状态效果列表, 被移除的状态效果列表)
        """
        # 确保实体有RPGCharacterProfileComponent
        # assert entity.has(CombatStatsComponent)
        combat_stats_comp = entity.get(CombatStatsComponent)
        assert combat_stats_comp is not None, "Entity must have CombatStatsComponent"

        remaining_effects = []
        removed_effects = []

        for status_effect in combat_stats_comp.status_effects:
            # 效果回合数扣除
            status_effect.duration -= 1
            status_effect.duration = max(0, status_effect.duration)

            # status_effect持续回合数大于0，继续保留，否则移除
            if status_effect.duration > 0:
                # 添加到剩余列表
                remaining_effects.append(status_effect)
            else:
                # 添加到移除列表
                removed_effects.append(status_effect)

        # 更新角色的状态效果列表，只保留剩余的效果
        combat_stats_comp.status_effects = remaining_effects

        logger.debug(
            f"settle_status_effects: {entity.name} => "
            f"remaining: {len(remaining_effects)}, removed: {len(removed_effects)}"
        )

        # 外部返回
        return remaining_effects, removed_effects

    ###############################################################################################################################################
    def _process_status_effects_settlement(self, entities: List[Entity]) -> None:
        """
        处理状态效果结算。
        为每个实体结算状态效果，并发送更新消息给角色。

        Args:
            entities: 需要结算状态效果的实体列表
        """
        for entity in entities:
            remaining_effects, removed_effects = self._settle_status_effects(entity)

            logger.debug(
                f"settle_status_effects: {entity.name} => "
                f"remaining: {len(remaining_effects)}, removed: {len(removed_effects)}"
            )

            updated_status_effects_message = _format_removed_status_effects_message(
                removed_effects
            )

            self._game.append_human_message(entity, updated_status_effects_message)

    #######################################################################################################################################
