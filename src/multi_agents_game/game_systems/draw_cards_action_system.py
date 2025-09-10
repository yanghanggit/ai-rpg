import copy
from typing import Final, List, Optional, final, override
from loguru import logger
from pydantic import BaseModel, Field
from ..chat_services.client import ChatClient
from ..entitas import Entity, GroupEvent, Matcher
from ..game.tcg_game import TCGGame
from ..game_systems.base_action_reactive_system import BaseActionReactiveSystem
from ..models import (
    DrawCardsAction,
    HandComponent,
    SkillExecutionPlan,
    Skill,
    XCardPlayerComponent,
    StatusEffect,
    RPGCharacterProfileComponent,
)
from ..utils import json_format


#######################################################################################################################################
@final
class SkillResponse(BaseModel):
    name: str = Field(..., description="此技能名称")
    description: str = Field(..., description="此技能描述")
    effect: str = Field(..., description="此技能产生的效果以及造成的影响")
    target: str = Field(..., description="技能针对的场景内目标")
    reason: str = Field(..., description="技能使用原因")
    dialogue: str = Field(..., description="技能对话")


#######################################################################################################################################
@final
class DrawCardsResponse(BaseModel):
    update_hp: Optional[float] = Field(None, description="更新的生命值")
    skills: List[SkillResponse] = Field(..., description="生成的战斗技能列表")
    status_effects: List[StatusEffect] = Field(
        ...,
        description="你自身的状态效果列表，注意！场景，角色，已发生事件均可能对你产生影响！",
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
            SkillResponse(
                name="[技能名称]",
                description="[技能的基本描述和作用方式]",
                effect="[对目标的主要效果：伤害/治疗/护盾等具体数值和类型]。[可选：对目标附加的状态效果]。因为[技能消耗或副作用原因]，使用者[自身限制效果描述]",
                target="[目标角色的完整名称]",
                reason="[选择此目标和技能的战术原因]",
                dialogue="[角色使用技能时的台词]",
            ),
        ],
        status_effects=[
            StatusEffect(
                name="[已受到的状态效果名称]",
                description="[已受到的状态效果的具体描述和影响]",
                rounds=1,
            ),
        ],
    )

    return f"""# 指令！请你更新状态，并生成 {skill_creation_count} 个技能。

## (场景内角色) 行动顺序(从左到右)
{round_turns}

## 技能生成规则
1. **技能对目标的效果**：技能可以对目标造成伤害、提供治疗、添加护盾等，并可选择性地为目标附加状态效果(buff/debuff)
2. **技能对自身的限制**：每个技能使用后必须对使用者产生一个限制效果：  
   - 眩晕：无法行动  
   - 沉默：无法使用法术类技能  
   - 力竭：体力透支，无法防御  
   - 反噬：技能释放时自己也受到部分伤害或异常状态  
   - 虚弱：受到的伤害增加  
   - 致盲：命中率降低
   - 缴械：无法攻击
   - 技能威力越大，自身限制效果越严重，持续时间越长
3. **技能生成顺序**：按照角色的战斗循环顺序进行生成

## 效果更新规则
- 技能中产生的状态效果和限制效果只会在技能被使用后再更新到status_effects中

## 输出要求
- 涉及数值变化时必须明确具体数值(生命/物理攻击/物理防御/魔法攻击/魔法防御)
- 技能效果格式：主要效果 + 可选状态效果 + 自身限制效果
- 使用有趣、意想不到的风格描述效果产生的原因

## 输出格式(JSON)要求：
```json
{response_sample.model_dump_json(exclude_none=True, indent=2)}
```

### 注意
- 禁用换行/空行
- 请严格按照示例格式输出合规JSON
- 示例格式中的任何数字都不是实际值，请根据你的当前状态生成新的值"""


#######################################################################################################################################
def _generate_prompt2(
    skill_creation_count: int,
    round_turns: List[str],
) -> str:
    assert skill_creation_count > 0

    # 生成抽象化规则示例
    response_sample = DrawCardsResponse(
        update_hp=85.0,
        skills=[
            SkillResponse(
                name="[技能名称]",
                description="[技能的基本描述和作用方式]",
                effect="[对目标的主要效果：伤害/治疗/护盾等具体数值和类型]。[可选：对目标附加的状态效果]。因为[技能消耗或副作用原因]，使用者[自身限制效果描述]",
                target="[目标角色的完整名称]",
                reason="[选择此目标和技能的战术原因]",
                dialogue="[角色使用技能时的台词]",
            ),
        ],
        status_effects=[
            StatusEffect(
                name="[新增状态效果名称]",
                description="[新增状态效果的具体描述和影响]",
                rounds=1,
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
2. **技能对自身的限制**：每个技能使用后必须对使用者产生一个限制效果：  
   - 眩晕：无法行动  
   - 沉默：无法使用法术类技能  
   - 力竭：体力透支，无法防御  
   - 反噬：技能释放时自己也受到部分伤害或异常状态  
   - 虚弱：受到的伤害增加  
   - 致盲：命中率降低
   - 缴械：无法攻击
   - 技能威力越大，自身限制效果越严重，持续时间越长
3. **技能生成顺序**：按照角色的战斗循环顺序进行生成



## 输出要求
- 涉及数值变化时必须明确具体数值(生命/物理攻击/物理防御/魔法攻击/魔法防御)
- 技能效果格式：主要效果 + 可选状态效果 + 自身限制效果
- 使用有趣、意想不到的风格描述效果产生的原因

## 输出格式(JSON)要求：
```json
{response_sample.model_dump_json(exclude_none=True, indent=2)}
```

### 特殊规则
- 根据最近的[发生事件！战斗回合]，来更新你的生命值，update_hp应当是你事件更新后的生命值。
- 更新你当前身上的状态效果，包括环境影响、之前行动的后果等
- 如果你已经死亡，即update_hp<=0，则不需要生成技能与状态，返回空列表即可。

### 注意
- 禁用换行/空行
- 请严格按照示例格式输出合规JSON
- 示例格式中的任何数字都不是实际值，请根据你的当前状态生成新的值"""


#######################################################################################################################################
@final
class DrawCardsActionSystem(BaseActionReactiveSystem):

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
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

        if not self._game.current_engagement.is_on_going_phase:
            logger.error(f"not web_game.current_engagement.is_on_going_phase")
            return

        last_round = self._game.current_engagement.last_round
        if last_round.has_ended:
            logger.error(f"last_round.has_ended, so setup new round")
            self._game.new_round()

        assert (
            len(self._game.current_engagement.rounds) > 0
        ), "当前没有进行中的战斗，不能设置回合。"
        if len(self._game.current_engagement.rounds) == 1:
            logger.debug(f"是第一局，一些数据已经被初始化了！")
            # 处理角色规划请求
            prompt = _generate_prompt1(
                self._skill_creation_count,
                last_round.round_turns,
            )
        else:

            logger.debug(f"不是第一局，继续当前数据！")

            # 注意！因为是第二局及以后，所以状态效果需要结算
            self._process_status_effects_settlement(entities)

            # 处理角色规划请求
            prompt = _generate_prompt2(
                self._skill_creation_count,
                last_round.round_turns,
            )

        # 先清除
        self._clear_hands()

        # 生成请求
        request_handlers: List[ChatClient] = self._generate_requests(entities, prompt)

        # 语言服务
        await self._game.chat_system.gather(request_handlers=request_handlers)

        # 处理角色规划请求
        for request_handler in request_handlers:
            entity2 = self._game.get_entity_by_name(request_handler._name)
            assert entity2 is not None
            self._handle_response(
                entity2, request_handler, len(self._game.current_engagement.rounds) > 1
            )

        # 最后的兜底，遍历所有参与的角色，如果没有手牌，说明_handle_response出现了错误，可能是LLM返回的内容无法正确解析。
        # 此时，就需要给角色一个默认的手牌，避免游戏卡死。
        self._ensure_all_entities_have_hands(entities)

    #######################################################################################################################################
    def _clear_hands(self) -> None:
        actor_entities = self._game.get_group(Matcher(HandComponent)).entities.copy()
        for entity in actor_entities:
            logger.debug(f"clear hands: {entity._name}")
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
            if not entity.has(HandComponent):
                wait_skill = Skill(
                    name="等待",
                    description="什么都不做，等待下一回合。",
                    effect="不产生任何效果",
                )

                wait_action_detail = SkillExecutionPlan(
                    skill=wait_skill.name,
                    target=entity._name,
                    reason="无",
                    dialogue="无",
                )

                logger.warning(
                    f"entity {entity._name} has no HandComponent, add default skill"
                )
                entity.replace(
                    HandComponent,
                    entity._name,
                    [wait_skill],
                    [wait_action_detail],
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
            execution_plans: List[SkillExecutionPlan] = []
            for skill_response in validated_response.skills:
                skills.append(
                    Skill(
                        name=skill_response.name,
                        description=skill_response.description,
                        effect=skill_response.effect,
                    )
                )
                execution_plans.append(
                    SkillExecutionPlan(
                        skill=skill_response.name,
                        target=skill_response.target,
                        reason=skill_response.reason,
                        dialogue=skill_response.dialogue,
                    )
                )

            # TODO: XCard就是全换掉。
            if entity2.has(XCardPlayerComponent):
                # 如果是玩家，则需要更新玩家的手牌
                xcard_player_comp = entity2.get(XCardPlayerComponent)
                skills = [xcard_player_comp.skill]
                execution_plans = [
                    SkillExecutionPlan(
                        skill=xcard_player_comp.skill.name,
                        target="根据技能描述和效果，所有适用的目标",
                        reason="",
                        dialogue=f"看招！{xcard_player_comp.skill.name}！",
                    )
                ]

                # 只用这一次。
                entity2.remove(XCardPlayerComponent)

            # 更新手牌。
            entity2.replace(
                HandComponent,
                entity2._name,
                skills,
                execution_plans,
            )

            # 更新健康属性。
            if need_update_health:
                self._update_combat_health(
                    entity2,
                    validated_response.update_hp,
                )

            # 更新状态效果。
            self._append_status_effects(entity2, validated_response.status_effects)

        except Exception as e:
            logger.error(f"Exception: {e}")

    #######################################################################################################################################
    def _generate_requests(
        self, actor_entities: List[Entity], prompt: str
    ) -> List[ChatClient]:
        request_handlers: List[ChatClient] = []

        for entity in actor_entities:

            request_handlers.append(
                ChatClient(
                    agent_name=entity._name,
                    prompt=prompt,
                    chat_history=self._game.get_agent_short_term_memory(
                        entity
                    ).chat_history,
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
                f"update_combat_health: {entity._name} => hp: {character_profile_component.rpg_character_profile.hp}"
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
            f"update_combat_status_effects: {entity._name} => {'\n'.join([e.model_dump_json() for e in character_profile_component.status_effects])}"
        )

        updated_status_effects_message = f"""# 提示！你的状态效果已更新
## 当前状态效果
{'\n'.join([f'- {e.name} (剩余回合: {e.rounds}): {e.description}' for e in character_profile_component.status_effects]) if len(character_profile_component.status_effects) > 0 else '无'}"""

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
            status_effect.rounds -= 1
            status_effect.rounds = max(0, status_effect.rounds)

            # status_effect持续回合数大于0，继续保留，否则移除
            if status_effect.rounds > 0:
                remaining_effects.append(status_effect)
            else:
                # 添加到移除列表
                removed_effects.append(status_effect)

        # 更新角色的状态效果列表，只保留剩余的效果
        character_profile_component.status_effects = remaining_effects

        logger.info(
            f"settle_status_effects: {entity._name} => "
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
                f"settle_status_effects: {entity._name} => "
                f"remaining: {len(remaining_effects)}, removed: {len(removed_effects)}"
            )

            updated_status_effects_message = f"""# 提示！你的状态效果已更新：
## 移除的状态效果
{'\n'.join([f'- {e.name}: {e.description}' for e in removed_effects]) if len(removed_effects) > 0 else '无'}"""

            self._game.append_human_message(entity, updated_status_effects_message)

    #######################################################################################################################################
