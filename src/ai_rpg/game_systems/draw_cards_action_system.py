import copy
from typing import Final, List, Optional, final, override
from loguru import logger
from pydantic import BaseModel, Field
from ..chat_services.client import ChatClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame

# from ..game_systems.base_action_reactive_system import BaseActionReactiveSystem
from ..models import (
    DrawCardsAction,
    HandComponent,
    Skill,
    XCardPlayerComponent,
    StatusEffect,
    RPGCharacterProfileComponent,
    InventoryComponent,
    ItemType,
)
from ..utils import json_format


#######################################################################################################################################
@final
class DrawCardsResponse(BaseModel):
    update_hp: Optional[float] = Field(None, description="更新后的生命值")
    skills: List[Skill] = Field(..., description="生成的战斗技能列表")
    status_effects: List[StatusEffect] = Field(
        ...,
        description="你自身的状态效果列表，注意！场景，角色，设定，kick_off_message，和已发生事件都会对你产生影响并生成状态效果！",
    )


#######################################################################################################################################
def _generate_prompt1(
    skill_creation_count: int,
    round_turns: List[str],
) -> str:
    assert skill_creation_count > 0

    # 生成抽象化规则示例
    response_sample = DrawCardsResponse(
        update_hp=None,
        skills=[
            Skill(
                name="[技能名称]",
                description="[技能的基本描述和作用方式][技能的主要效果：伤害/治疗/护盾等具体数值和类型]。[可选：技能附加的状态效果]。因为[技能消耗或副作用原因]，使用者[自身限制状态描述]",
                target="[目标角色的完整名称]",
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

    return f"""# 指令！请你更新状态，并生成 {skill_creation_count} 个技能。

## (场景内角色) 行动顺序(从左到右)
{round_turns}

## 技能生成规则
1. **技能对目标的效果**：技能可以对目标造成伤害、提供治疗、添加护盾等，并可选择性地为目标附加状态效果(buff/debuff)
2. **技能对自身的限制**：每个技能使用后必须对使用者产生一个限制状态，下面是状态示例：  
   - 眩晕：无法行动  
   - 沉默：无法使用魔法，法术类技能  
   - 力竭：体力透支，无法防御  
   - 反噬：技能释放时自己也受到部分伤害或异常状态  
   - 虚弱：受到的伤害增加  
   - 致盲：命中率降低
   - 缴械：无法攻击
   - 技能威力越大，自身限制状态越严重，持续时间越长
3. **技能生成顺序**：按照角色的战斗循环顺序进行生成

## 输出要求
- 涉及数值变化时必须明确具体数值(生命/物理攻击/物理防御/魔法攻击/魔法防御)
- 技能效果格式：主要效果 + 可选状态效果 + 自身限制状态
- 技能的description里禁止包含角色名称
- 第一局一定会有新增的status_effects，根据角色进入战斗时的设定，kick_off_message，环境，内心活动，和其他角色的情况生成，而不是技能里提到的状态
- 同一时间可以出现多个status_effects
- 使用有趣、意想不到的风格描述效果产生的原因

## 输出格式(JSON)要求：
```json
{response_sample.model_dump_json(exclude_none=True, indent=2)}
```

### 注意
- 禁用换行/空行
- 请严格按照输出格式来输出合规JSON
- 输出格式要求response_sample中的任何数字都不是正确的值，请根据‘计算过程’后的状态更新为正确的值"""


#######################################################################################################################################
def _generate_prompt2(
    skill_creation_count: int,
    round_turns: List[str],
) -> str:
    assert skill_creation_count > 0

    # 生成抽象化规则示例
    response_sample = DrawCardsResponse(
        update_hp=0.0,
        skills=[
            Skill(
                name="[技能名称]",
                description="[技能的基本描述和作用方式][技能的主要效果：伤害/治疗/护盾等具体数值和类型]。[可选：技能附加的状态效果]。因为[技能消耗或副作用原因]，使用者[自身限制状态描述]",
                target="[目标角色的完整名称]",
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
        skills=[],
        update_hp=0.0,
        status_effects=[],
    )

    return f"""# 指令！请你回顾战斗内发生事件及对你的影响，然后更新自身状态，并生成 {skill_creation_count} 个技能。

## (场景内角色) 行动顺序(从左到右)
{round_turns}

## 技能生成规则
1. **技能对目标的效果**：技能可以对目标造成伤害、提供治疗、添加护盾等，并可选择性地为目标附加状态效果(buff/debuff)
2. **技能对自身的限制**：每个技能使用后必须对使用者产生一个限制状态，下面是状态示例：  
   - 眩晕：无法行动  
   - 沉默：无法使用魔法，法术类技能  
   - 力竭：体力透支，无法防御  
   - 反噬：技能释放时自己也受到部分伤害或异常状态  
   - 虚弱：受到的伤害增加  
   - 致盲：命中率降低
   - 缴械：无法攻击
   - 技能威力越大，自身限制效果越严重，持续时间越长
3. **技能生成顺序**：按照角色的战斗循环顺序进行生成


## 输出要求
- 涉及数值变化时必须明确具体数值(生命/物理攻击/物理防御/魔法攻击/魔法防御)
- 技能效果格式：主要效果 + 可选状态效果 + 自身限制状态
- 根据最近的[发生事件！战斗回合]中的”计算过程“结果来更新你的update_hp，而不是使用已有的值。
- 技能的description里禁止包含角色名称
- status_effects根据角色上回合结束时受到的其他角色的技能状态效果和自身技能的限制状态生成，而不是这回合生成的技能里提到的状态
- 同一时间可以存在多个status_effects
- 使用有趣、意想不到的风格描述效果产生的原因

## 输出格式(JSON)要求：
```json
{response_sample.model_dump_json(exclude_none=True, indent=2)}
```

### 特殊规则
- 更新你当前身上的状态效果，包括环境影响、之前行动的后果等
- 如果你已经死亡，即update_hp<=0，则不需要生成技能与状态，返回如下对象:
```json
{response_empty_sample.model_dump_json(exclude_none=True, indent=2)}
```
- 如果你认为战斗已经结束，也不需要生成技能，返回如下对象:
```json
{response_empty_sample.model_dump_json(exclude_none=True, indent=2)}
```
但是血量和状态效果仍然需要更新。

### 注意
- 禁用换行/空行
- 请严格按照输出格式来输出合规JSON
- 输出格式要求response_sample和response_empty_sample中的任何数字都不是正确值，请根据你‘计算过程’后的状态更新为正确的值"""


#######################################################################################################################################
@final
class DrawCardsActionSystem(ReactiveProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: TCGGame = game_context
        self._skill_creation_count: Final[int] = 2

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

        if not self._game.current_engagement.is_ongoing:
            logger.error(f"not web_game.current_engagement.is_on_going_phase")
            return

        last_round = self._game.current_engagement.latest_round
        if last_round.has_ended:
            logger.success(f"last_round.has_ended, so setup new round")
            self._game.start_new_round()

        logger.debug(f"当前回合数: {len(self._game.current_engagement.current_rounds)}")

        # 测试道具的问题
        self._test_unique_item(entities)

        assert (
            len(self._game.current_engagement.current_rounds) > 0
        ), "当前没有进行中的战斗，不能设置回合。"
        if len(self._game.current_engagement.current_rounds) == 1:
            logger.debug(f"是第一局，一些数据已经被初始化了！")
            # 处理角色规划请求
            prompt = _generate_prompt1(
                self._skill_creation_count,
                last_round.action_order,
            )
        else:

            logger.debug(f"不是第一局，继续当前数据！")

            # 注意！因为是第二局及以后，所以状态效果需要结算
            self._process_status_effects_settlement(entities)

            # 处理角色规划请求
            prompt = _generate_prompt2(
                self._skill_creation_count,
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
                len(self._game.current_engagement.current_rounds) > 1,
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
        可能是LLM返回的内容无法正确解析。此时给角色一个默认的等待技能，避免游戏卡死。

        Args:
            entities: 需要检查的实体列表
        """
        for entity in entities:
            if entity.has(HandComponent):
                continue

            character_profile_component = entity.get(RPGCharacterProfileComponent)
            assert character_profile_component is not None
            if character_profile_component.rpg_character_profile.hp <= 0:
                # 如果角色已经死亡，就不需要添加等待技能了。
                logger.warning(
                    f"entity {entity.name} is dead (hp <= 0), no need to add default skill"
                )
                continue

            wait_skill = Skill(
                name="等待",
                description="什么都不做，等待下一回合。",
                target=entity.name,
            )

            logger.warning(
                f"entity {entity.name} has no HandComponent, add default skill"
            )
            entity.replace(
                HandComponent,
                entity.name,
                [wait_skill],
            )

    #######################################################################################################################################
    def _handle_response(
        self, entity2: Entity, request_handler: ChatClient, need_update_health: bool
    ) -> None:

        try:

            json_code = json_format.strip_json_code_block(
                request_handler.response_content
            )

            validated_response = DrawCardsResponse.model_validate_json(json_code)

            # 生成的结果。
            skills: List[Skill] = []
            for skill_response in validated_response.skills:
                skills.append(
                    Skill(
                        name=skill_response.name,
                        description=skill_response.description,
                        # effect=skill_response.effect,
                        target=skill_response.target,
                    )
                )

            # TODO: XCard就是全换掉。
            if entity2.has(XCardPlayerComponent):
                # 如果是玩家，则需要更新玩家的手牌
                xcard_player_comp = entity2.get(XCardPlayerComponent)
                # 更新技能的target字段
                xcard_skill = Skill(
                    name=xcard_player_comp.skill.name,
                    description=xcard_player_comp.skill.description,
                    target=xcard_player_comp.skill.target,
                )
                skills = [xcard_skill]

                # 只用这一次。
                entity2.remove(XCardPlayerComponent)

            # 更新手牌。
            if len(skills) > 0:
                entity2.replace(
                    HandComponent,
                    entity2.name,
                    skills,
                )
            else:
                logger.debug(f"entity {entity2.name} has no skills from LLM response")

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
                    chat_history=self._game.get_agent_chat_history(entity).chat_history,
                )
            )

        return request_handlers

    #######################################################################################################################################
    def _update_combat_health(self, entity: Entity, update_hp: Optional[float]) -> None:

        character_profile_component = entity.get(RPGCharacterProfileComponent)
        assert character_profile_component is not None

        if update_hp is not None:
            character_profile_component.rpg_character_profile.hp = int(update_hp)
            logger.debug(
                f"update_combat_health: {entity.name} => hp: {character_profile_component.rpg_character_profile.hp}"
            )

    ###############################################################################################################################################
    def _append_status_effects(
        self, entity: Entity, status_effects: List[StatusEffect]
    ) -> None:

        # 效果更新
        assert entity.has(RPGCharacterProfileComponent)
        character_profile_component = entity.get(RPGCharacterProfileComponent)
        character_profile_component.status_effects.extend(copy.copy(status_effects))
        logger.info(
            f"update_combat_status_effects: {entity.name} => {'\n'.join([e.model_dump_json() for e in character_profile_component.status_effects])}"
        )

        updated_status_effects_message = f"""# 提示！你的状态效果已更新
## 当前状态效果
{'\n'.join([f'- {e.name} (剩余回合: {e.duration}): {e.description}' for e in character_profile_component.status_effects]) if len(character_profile_component.status_effects) > 0 else '无'}"""

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
        assert entity.has(RPGCharacterProfileComponent)
        character_profile_component = entity.get(RPGCharacterProfileComponent)
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

            updated_status_effects_message = f"""# 提示！你的状态效果已更新：
## 移除的状态效果
{'\n'.join([f'- {e.name}: {e.description}' for e in removed_effects]) if len(removed_effects) > 0 else '无'}"""

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
