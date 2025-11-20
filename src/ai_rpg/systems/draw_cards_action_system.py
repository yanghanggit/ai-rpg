import copy
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
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class DrawCardsResponse(BaseModel):
    update_hp: Optional[float] = None
    cards: List[Card] = []
    status_effects: List[StatusEffect] = []


#######################################################################################################################################
def _generate_prompt1(
    card_creation_count: int,
    round_turns: List[str],
) -> str:
    assert card_creation_count > 0

    return f"""# 指令！战斗开局，评估当前态势，生成你的初始 {card_creation_count} 张卡牌。

## 1. 场景内角色行动顺序(从左到右，先行动者可能影响战局与后续行动)

{round_turns}

## 2. 生成内容规则

**卡牌(cards)**：你本回合可执行的行动
- 每张卡牌对目标产生效果：伤害/治疗/护盾/buff/debuff等
- 每张卡牌使用后对自己产生代价：限制状态，效果越强代价越重

**状态效果(status_effects)**：你当前回合新增的自身状态
- 战斗开局产生的初始状态（战斗准备、环境影响、心理状态、装备效果、过往经验等）
- 可同时存在多个状态效果
- 不要重复生成已存在的状态效果

## 3. 输出格式(JSON)

```json
{{
  "cards": [
    {{
      "name": "[卡牌名称]",
      "description": "[作用方式与意图]。[附加状态效果]。代价：[使用代价描述]",
      "target": "[目标角色完整名称]"
    }}
  ],
  "status_effects": [
    {{
      "name": "[状态名称]",
      "description": "[状态产生原因的生动有趣描述]，[状态效果的具体影响]",
      "duration": [持续回合数]
    }}
  ]
}}
```

**约束规则**：
- description中禁止出现角色名称
- 禁用换行/空行，严格输出合规JSON"""


#######################################################################################################################################
def _generate_prompt2(
    card_creation_count: int,
    round_turns: List[str],
) -> str:
    assert card_creation_count > 0

    # 生成抽象化规则示例
    response_sample = DrawCardsResponse(
        update_hp=999.0,  # 占位符：填写你从计算过程中找到的当前HP值
        cards=[
            Card(
                name="[卡牌名称]",
                description="[作用方式与效果]：[具体数值效果]。[附加状态效果]。代价：[使用后的自身限制]",
                target="[目标角色完整名称]",
            ),
        ],
        status_effects=[
            StatusEffect(
                name="[状态效果名称]",
                description="[状态效果生成的原因，具体描述和影响]",
                duration=1,
            ),
        ],
    )

    response_empty_sample = DrawCardsResponse(
        cards=[],
        update_hp=0.0,
        status_effects=[],
    )

    return f"""# 指令！请你回顾战斗内发生事件及对你的影响，然后更新自身状态，并生成 {card_creation_count} 张卡牌。

## (场景内角色) 行动顺序(从左到右)

{round_turns}

## 卡牌生成规则

1. **卡牌效果**：卡牌可对目标造成伤害、提供治疗、添加护盾等，并可选择性地为目标附加状态效果(buff/debuff)
2. **使用代价**：每张卡牌使用后必须对使用者产生一个限制状态作为代价，下面是代价示例：  
   - 眩晕：无法行动  
   - 沉默：无法使用魔法、法术类卡牌  
   - 力竭：体力透支，无法防御  
   - 反噬：使用时自己也受到部分伤害或异常状态  
   - 虚弱：受到的伤害增加  
   - 致盲：命中率降低
   - 缴械：无法攻击
   - 卡牌效果越强，使用代价越严重，持续时间越长
3. **生成顺序**：按照角色的行动顺序依次生成卡牌


## 输出要求

- 涉及数值变化时必须明确具体数值(生命/物理攻击/物理防御/魔法攻击/魔法防御)
- 卡牌描述格式：作用方式 + 主要效果 + 附加状态 + 使用代价
- **【重要】update_hp字段必须填写你的最终当前HP值(不是变化量)**:
  - 在最近的[发生事件！战斗回合]的"计算过程"末尾，会明确列出"角色状态"部分，格式为"角色.xxx.当前HP/最大HP"
  - 找到关于**你**的那一条，将"当前HP"的数值填入update_hp字段
  - 例如：如果看到"角色.战士.卡恩.1050/1050(HP保持不变)"，则update_hp应该填1050.0
  - 例如：如果看到"角色.法师.奥露娜.989/1050(受到伤害)"，则update_hp应该填989.0
- 卡牌的description里禁止包含角色名称
- status_effects根据角色上回合结束时受到的其他角色的卡牌效果和自身使用代价生成，而不是这回合生成的卡牌里提到的状态
- **状态效果去重**: 如果你已经拥有某个长期状态效果(如传奇道具效果)，不需要重复输出，系统会自动维护。只输出本回合**新增**的状态效果。
- 同一时间可以存在多个status_effects
- 使用有趣、意想不到的风格描述效果产生的原因

## 输出格式(JSON)要求：

```json
{response_sample.model_dump_json(exclude_none=True, indent=2)}
```
### 特殊规则

- 更新你当前身上的状态效果，包括环境影响、之前行动的后果等
- 如果你已经死亡，即update_hp<=0，则不需要生成卡牌与状态，返回如下对象:
```json
{response_empty_sample.model_dump_json(exclude_none=True, indent=2)}
```
- 如果你认为战斗已经结束，也不需要生成卡牌，返回如下对象:
```json
{response_empty_sample.model_dump_json(exclude_none=True, indent=2)}
```
但是血量和状态效果仍然需要更新。

### 注意

- 禁用换行/空行
- 请严格按照输出格式来输出合规JSON
- **update_hp字段必须填写从"计算过程"中提取的你的当前HP数值,不要填0.0除非你真的HP为0**
- 输出格式要求response_sample和response_empty_sample中的任何数字都不是正确值，请根据你'计算过程'后的状态更新为正确的值"""


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

        if len(entities) == 0:
            return

        if not self._game.current_combat_sequence.is_ongoing:
            logger.error(f"not web_game.current_engagement.is_on_going_phase")
            return

        last_round = self._game.current_combat_sequence.latest_round
        if last_round.has_ended:
            logger.success(f"last_round.has_ended, so setup new round")
            self._game.start_new_round()

        logger.debug(
            f"当前回合数: {len(self._game.current_combat_sequence.current_rounds)}"
        )

        # 测试道具的问题
        self._test_unique_item(entities)

        assert (
            len(self._game.current_combat_sequence.current_rounds) > 0
        ), "当前没有进行中的战斗，不能设置回合。"
        if len(self._game.current_combat_sequence.current_rounds) == 1:
            logger.debug(f"是第一局，一些数据已经被初始化了！")
            # 处理角色规划请求
            prompt = _generate_prompt1(
                self._card_creation_count,
                last_round.action_order,
            )
        else:

            logger.debug(f"不是第一局，继续当前数据！")

            # 注意！因为是第二局及以后，所以状态效果需要结算
            self._process_status_effects_settlement(entities)

            # 处理角色规划请求
            prompt = _generate_prompt2(
                self._card_creation_count,
                last_round.action_order,
            )

        # 先清除
        self._clear_hands()

        # 生成请求
        request_handlers: List[ChatClient] = self._generate_requests(entities, prompt)

        # 语言服务
        await ChatClient.gather_request_post(clients=request_handlers)

        # 处理角色规划请求
        for request_handler in request_handlers:
            entity2 = self._game.get_entity_by_name(request_handler.name)
            assert entity2 is not None
            self._handle_response(
                entity2,
                request_handler,
                len(self._game.current_combat_sequence.current_rounds) > 1,
            )

        # 最后的兜底，遍历所有参与的角色，如果没有手牌，说明_handle_response出现了错误，可能是LLM返回的内容无法正确解析。
        # 此时，就需要给角色一个默认的手牌，避免游戏卡死。
        self._ensure_all_entities_have_hands(entities)

    #######################################################################################################################################
    def _clear_hands(self) -> None:
        actor_entities = self._game.get_group(Matcher(HandComponent)).entities.copy()
        for entity in actor_entities:
            logger.debug(f"clear hands: {entity.name}")
            entity.remove(HandComponent)

    #######################################################################################################################################
    def _ensure_all_entities_have_hands(self, entities: List[Entity]) -> None:
        """
        确保所有实体都有手牌组件的兜底机制。
        如果某个实体缺少HandComponent，说明_handle_response出现了错误，
        可能是LLM返回的内容无法正确解析。此时给角色一个默认的等待，避免游戏卡死。

        Args:
            entities: 需要检查的实体列表
        """
        for entity in entities:
            if entity.has(HandComponent):
                continue

            character_profile_component = entity.get(CombatStatsComponent)
            assert character_profile_component is not None
            if character_profile_component.stats.hp <= 0:
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

            logger.warning(
                f"entity {entity.name} has no HandComponent, add default card"
            )
            entity.replace(
                HandComponent,
                entity.name,
                [wait_card],
            )

    #######################################################################################################################################
    def _handle_response(
        self, entity2: Entity, request_handler: ChatClient, need_update_health: bool
    ) -> None:

        try:

            json_code = extract_json_from_code_block(request_handler.response_content)

            validated_response = DrawCardsResponse.model_validate_json(json_code)

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
                entity2.replace(
                    HandComponent,
                    entity2.name,
                    cards,
                )
            else:
                logger.debug(f"entity {entity2.name} has no cards from LLM response")

            # 更新健康属性。
            if need_update_health:
                self._update_combat_health(
                    entity2,
                    validated_response.update_hp,
                )

            # 更新状态效果。
            self._append_status_effects(entity2, validated_response.status_effects)

        except Exception as e:
            logger.error(f"{request_handler.response_content}")
            logger.error(f"Exception: {e}")

    #######################################################################################################################################
    def _generate_requests(
        self, actor_entities: List[Entity], prompt: str
    ) -> List[ChatClient]:
        request_handlers: List[ChatClient] = []

        for entity in actor_entities:

            request_handlers.append(
                ChatClient(
                    name=entity.name,
                    prompt=prompt,
                    context=self._game.get_agent_context(entity).context,
                )
            )

        return request_handlers

    #######################################################################################################################################
    def _update_combat_health(self, entity: Entity, update_hp: Optional[float]) -> None:

        character_profile_component = entity.get(CombatStatsComponent)
        assert character_profile_component is not None

        if update_hp is not None:
            character_profile_component.stats.hp = int(update_hp)
            logger.debug(f"{entity.name} => hp: {character_profile_component.stats.hp}")

    ###############################################################################################################################################
    def _append_status_effects(
        self, entity: Entity, status_effects: List[StatusEffect]
    ) -> None:

        # 效果更新
        assert entity.has(CombatStatsComponent)
        character_profile_component = entity.get(CombatStatsComponent)
        character_profile_component.status_effects.extend(copy.copy(status_effects))
        # logger.info(
        #     f"{entity.name} => {'\n'.join([e.model_dump_json() for e in character_profile_component.status_effects])}"
        # )

        updated_status_effects_message = f"""# 通知！你的 状态/效果 已更新

{'\n'.join([f'{e.name} (剩余回合: {e.duration}): {e.description}' for e in character_profile_component.status_effects]) if len(character_profile_component.status_effects) > 0 else '无'}"""

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
        assert entity.has(CombatStatsComponent)
        character_profile_component = entity.get(CombatStatsComponent)
        assert character_profile_component is not None

        remaining_effects = []
        removed_effects = []

        for status_effect in character_profile_component.status_effects:
            # 效果回合数扣除
            status_effect.duration -= 1
            status_effect.duration = max(0, status_effect.duration)

            # status_effect持续回合数大于0，继续保留，否则移除
            if status_effect.duration > 0:
                remaining_effects.append(status_effect)
            else:
                # 添加到移除列表
                removed_effects.append(status_effect)

        # 更新角色的状态效果列表，只保留剩余的效果
        character_profile_component.status_effects = remaining_effects

        logger.info(
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

            updated_status_effects_message = f"""# 通知！如下 状态/效果 被移除

{'\n'.join([f'{e.name}: {e.description}' for e in removed_effects]) if len(removed_effects) > 0 else '无'}"""

            self._game.append_human_message(entity, updated_status_effects_message)

    #######################################################################################################################################
    def _test_unique_item(self, entities: List[Entity]) -> None:

        for entity in entities:

            if not entity.has(InventoryComponent):
                continue

            inventory_component = entity.get(InventoryComponent)
            assert inventory_component is not None
            if len(inventory_component.items) == 0:
                continue

            for item in inventory_component.items:
                if item.type == ItemType.UNIQUE_ITEM:
                    logger.debug(
                        f"entity {entity.name} has unique item {item.model_dump_json()}"
                    )

                    existing_human_messages = (
                        self._game.find_human_messages_by_attribute(
                            actor_entity=entity,
                            attribute_key="test_unique_item",
                            attribute_value=item.name,
                        )
                    )

                    if len(existing_human_messages) > 0:
                        self._game.delete_human_messages_by_attribute(
                            actor_entity=entity,
                            human_messages=existing_human_messages,
                        )

                    duplicate_message_test = (
                        self._game.find_human_messages_by_attribute(
                            actor_entity=entity,
                            attribute_key="test_unique_item",
                            attribute_value=item.name,
                        )
                    )
                    assert (
                        len(duplicate_message_test) == 0
                    ), f"test_unique_item not deleted!"

                    self._game.append_human_message(
                        entity,
                        f"""# 提示！你拥有道具: {item.name}。\n{item.model_dump_json()}""",
                        test_unique_item=item.name,
                    )
                else:
                    logger.debug(
                        f"entity {entity.name} has item {item.model_dump_json()}, 暂时不处理！"
                    )

    #######################################################################################################################################
