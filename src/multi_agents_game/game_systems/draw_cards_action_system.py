import copy
from typing import Final, List, final, override
from loguru import logger
from pydantic import BaseModel, Field
from ..chat_services.client import ChatClient
from ..entitas import Entity, GroupEvent, Matcher
from ..game.tcg_game import TCGGame
from ..game_systems.base_action_reactive_system import BaseActionReactiveSystem
from ..models import (
    DrawCardsAction,
    HandComponent,
    ActionDetail,
    Skill,
    XCardPlayerComponent,
    StatusEffect,
    RPGCharacterProfileComponent,
)
from ..utils import json_format


#######################################################################################################################################
@final
class SkillGeneration(BaseModel):
    skill: Skill = Field(..., description="生成的技能对象")
    target: str = Field(..., description="技能针对的场景内目标")
    reason: str = Field(..., description="技能使用原因")
    dialogue: str = Field(..., description="技能对话")


#######################################################################################################################################
@final
class CombatStatusUpdate(BaseModel):
    update_hp: float = Field(..., description="更新的生命值")
    update_max_hp: float = Field(..., description="更新的最大生命值")
    status_effects: List[StatusEffect] = Field(
        ...,
        description="你自身的状态效果列表，注意！场景与角色，已发生事件均可能对你产生影响！",
    )


#######################################################################################################################################
@final
class DrawCardsResponse(BaseModel):
    combat_skills: List[SkillGeneration] = Field(..., description="生成的战斗技能列表")
    combat_status: CombatStatusUpdate = Field(..., description="战斗状态更新")


#######################################################################################################################################
def _generate_prompt(
    skill_creation_count: int,
    round_turns: List[str],
) -> str:
    assert skill_creation_count > 0

    # 生成示例
    response_sample = DrawCardsResponse(
        combat_skills=[
            SkillGeneration(
                skill=Skill(
                    name="炽热斩击",
                    description="挥舞燃烧的利刃对敌人造成火焰伤害",
                    effect="对目标造成120点火焰伤害，附加灼烧效果2回合。因为过度燃烧体力，使用者下回合物理攻击力减少30%",
                ),
                target="敌方角色的全名",
                reason="敌人防御较弱，使用火焰攻击可以造成更大伤害",
                dialogue="感受烈火的力量吧！炽热斩击！",
            ),
            SkillGeneration(
                skill=Skill(
                    name="守护壁垒",
                    description="召唤魔法护盾保护自己和队友",
                    effect="为自己和所有队友提供80点护盾值，持续3回合。因为耗费大量魔力，使用者下回合无法使用魔法类技能",
                ),
                target="己方角色的全名",
                reason="当前生命值较低，需要防御来保护团队",
                dialogue="魔法的力量，守护我们！守护壁垒！",
            ),
        ],
        combat_status=CombatStatusUpdate(
            update_hp=85.0,
            update_max_hp=100.0,
            status_effects=[
                StatusEffect(
                    name="战斗专注",
                    description="进入战斗状态，注意力高度集中",
                    rounds=3,
                ),
                StatusEffect(
                    name="轻微疲劳", description="连续战斗导致的轻微疲劳感", rounds=2
                ),
            ],
        ),
    )

    return f"""# 指令！请你更新自身状态，并生成 {skill_creation_count} 个技能。

## 技能生成规则
1. 技能效果中必须有一个对角色自身的限制效果：  
       限制效果示例（特殊状态）：
       - 眩晕：下回合无法行动  
       - 沉默：下回合无法使用法术类技能  
       - 力竭：体力透支，下一回合无法防御  
       - 反噬：下回合技能释放时自己也受到部分伤害或异常状态  
       - 虚弱：下回合受到的伤害增加  
       - 致盲：下回合命中率降低
       - 缴械：下回合无法攻击
   - 技能本身的威力/数值越大，限制效果越严重，持续时间越长。  
2. 技能生成格式统一为：技能描述 → 技能效果 = 技能本身效果 + 限制效果（格式：因为什么产生了什么效果。使用有趣，意想不到的风格来描述。）。
3. 技能生成必须按照角色的战斗循环顺序进行生成。

## (场景内角色) 行动顺序(从左到右)
{round_turns}

## 输出内容
- 注意，如生成技能提到了属性(生命/物理攻击/物理防御/魔法攻击/魔法防御)，请在技能描述与影响里明确说明改变的数值。

## 输出格式(JSON)示意：
{response_sample.model_dump_json()}

### 注意
- 禁用换行/空行。
- 直接输出合规JSON。"""


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

        # 先清除
        self._clear_hands()

        # 处理角色规划请求
        request_handlers: List[ChatClient] = self._generate_requests(entities)

        # 语言服务
        await self._game.chat_system.gather(request_handlers=request_handlers)

        # 处理角色规划请求
        for request_handler in request_handlers:
            entity2 = self._game.get_entity_by_name(request_handler._name)
            assert entity2 is not None
            self._handle_response(entity2, request_handler)

        self._test()

    #######################################################################################################################################
    def _clear_hands(self) -> None:
        actor_entities = self._game.get_group(Matcher(HandComponent)).entities.copy()
        for entity in actor_entities:
            logger.debug(f"clear hands: {entity._name}")
            entity.remove(HandComponent)

    #######################################################################################################################################
    def _handle_response(self, entity2: Entity, request_handler: ChatClient) -> None:

        try:

            validated_response = DrawCardsResponse.model_validate_json(
                json_format.strip_json_code_block(request_handler.response_content)
            )

            # 生成的结果。
            skills: List[Skill] = []
            action_details: List[ActionDetail] = []
            for skill_response in validated_response.combat_skills:
                skills.append(skill_response.skill)
                action_details.append(
                    ActionDetail(
                        skill=skill_response.skill.name,
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
                action_details = [
                    ActionDetail(
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
                action_details,
            )

            # 更新健康属性。
            self._update_combat_health(
                entity2,
                validated_response.combat_status.update_hp,
                validated_response.combat_status.update_max_hp,
            )

            # 更新状态效果。
            self._append_status_effects(
                entity2, validated_response.combat_status.status_effects
            )

            # 添加上下文。
            # self._game.append_human_message(
            #     entity=entity2,
            #     chat=request_handler._prompt
            # )
            # self._game.append_ai_message(entity2, request_handler.ai_messages)

        except Exception as e:
            logger.error(f"Exception: {e}")

    #######################################################################################################################################
    def _generate_requests(self, actor_entities: List[Entity]) -> List[ChatClient]:

        request_handlers: List[ChatClient] = []

        last_round = self._game.current_engagement.last_round
        assert (
            not last_round.has_ended
        ), f"last_round.is_round_complete: {last_round.has_ended}"

        for entity in actor_entities:

            #
            current_stage = self._game.safe_get_stage_entity(entity)
            assert current_stage is not None

            # 生成消息
            message = _generate_prompt(
                self._skill_creation_count,
                last_round.round_turns,
            )

            # 生成请求处理器
            request_handlers.append(
                ChatClient(
                    agent_name=entity._name,
                    prompt=message,
                    chat_history=self._game.get_agent_short_term_memory(
                        entity
                    ).chat_history,
                )
            )

        return request_handlers

    #######################################################################################################################################
    def _update_combat_health(
        self,
        entity: Entity,
        update_hp: float,
        update_max_hp: float,
    ) -> None:

        character_profile_component = entity.get(RPGCharacterProfileComponent)
        assert character_profile_component is not None
        character_profile_component.rpg_character_profile.hp = int(update_hp)

    ###############################################################################################################################################
    def _append_status_effects(
        self, entity: Entity, status_effects: List[StatusEffect]
    ) -> None:

        # 效果更新
        assert entity.has(RPGCharacterProfileComponent)
        character_profile_component = entity.get(RPGCharacterProfileComponent)
        character_profile_component.status_effects.extend(copy.copy(status_effects))

        logger.debug(f"update_combat_status_effects: {entity._name} => ")
        for e in character_profile_component.status_effects:
            logger.debug(f"status_effects: {e.model_dump_json()}")

    #######################################################################################################################################
    def _test(self) -> None:

        # 测试
        actor_entities1 = self._game.get_group(Matcher(HandComponent)).entities.copy()
        for entity in actor_entities1:
            hand_comp = entity.get(HandComponent)
            assert hand_comp is not None
            logger.debug(f"{entity._name} hands: {hand_comp.model_dump_json()}")

        # 测试
        actor_entities2 = self._game.get_group(
            Matcher(RPGCharacterProfileComponent)
        ).entities.copy()
        for entity2 in actor_entities2:
            rpg_character_profile_comp = entity2.get(RPGCharacterProfileComponent)
            assert rpg_character_profile_comp is not None
            logger.debug(
                f"{entity2._name} rpg_character_profile: {rpg_character_profile_comp.model_dump_json()}"
            )

    #######################################################################################################################################
