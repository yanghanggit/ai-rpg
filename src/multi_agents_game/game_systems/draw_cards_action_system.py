from typing import Final, List, final, override

from loguru import logger
from pydantic import BaseModel

from ..chat_services.chat_request_handler import ChatRequestHandler
from ..entitas import Entity, GroupEvent, Matcher
from ..game.tcg_game import TCGGame
from ..game_systems.base_action_reactive_system import BaseActionReactiveSystem
from ..models import (
    DrawCardsAction,
    EnvironmentComponent,
    HandComponent,
    HandDetail,
    Skill,
    XCardPlayerComponent,
)
from ..utils import json_format


#######################################################################################################################################
@final
class SkillResponse(BaseModel):
    skill: Skill
    targets: List[str]
    reason: str
    dialogue: str


#######################################################################################################################################
@final
class DrawCardsResponse(BaseModel):
    gen_skill_reponse: List[SkillResponse]


#######################################################################################################################################
def _generate_prompt(
    skill_creation_count: int,
    current_stage: str,
    current_stage_narration: str,
    round_turns: List[str],
) -> str:
    assert skill_creation_count > 0
    if skill_creation_count <= 0:
        return ""

    response_example = DrawCardsResponse(
        gen_skill_reponse=[],
    )

    for i in range(skill_creation_count):

        skill_response_example = SkillResponse(
            skill=Skill(
                name=f"技能{i+1}",
                description=f"技能{i+1}描述",
                effect=f"技能{i+1}效果",
            ),
            targets=["目标1", "目标2"],
            reason=f"技能{i+1}使用原因",
            dialogue=f"技能{i+1}对话",
        )

        response_example.gen_skill_reponse.append(skill_response_example)

    return f"""# 请你生成 {skill_creation_count} 个技能，技能生成模式有两种，一种模式是生成一个防御技能和一个攻击技能。另一种模式是生成一个防御或攻击类型的技能，和一个观察并利用环境的技能。攻击和防御类型的技能受角色属性影响，观察和利用环境的技能不受角色属性影响。观察和利用环境的技能是角色观察周围环境来查看是否有可以利用的地方，如果有，就立即生效（注意，环境利用是指通过利用环境中的物品，产生的对敌方的间接的攻击或施加负面效果行为，或者是对己方的防御或施加增益效果的行为。同一环境物体在同一回合内不可重复利用，如果已有角色使用该物体，下一角色将不能利用该环境物体）。两种技能的生成模式根据人物的职业，性格和当前环境特点来决定选择哪种生成模式，并根据生成的技能来决定如何使用。
## 当前场景状态
{current_stage} | {current_stage_narration}
## (场景内角色) 行动顺序(从左到右)
{round_turns}
## 输出内容
- 注意，如生成技能提到了属性(生命/物理攻击/物理防御/魔法攻击/魔法防御)，请在技能描述与影响里明确说明改变的数值。
## 输出格式(JSON)
{response_example.model_dump_json()}
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
    async def a_execute2(self) -> None:

        if len(self._react_entities_copy) == 0:
            return

        if not self._game.current_engagement.is_on_going_phase:
            logger.error(f"not web_game.current_engagement.is_on_going_phase")
            return

        # 先清除
        self._game.clear_hands()

        # 处理请求
        await self._process_chat_requests(self._react_entities_copy)

    #######################################################################################################################################
    async def _process_chat_requests(self, react_entities: List[Entity]) -> None:

        # 处理角色规划请求
        request_handlers: List[ChatRequestHandler] = self._generate_requests(
            react_entities
        )

        # 语言服务
        await self._game.chat_system.gather(request_handlers=request_handlers)

        # 处理角色规划请求
        self._handle_responses(request_handlers)

    #######################################################################################################################################
    def _handle_responses(self, request_handlers: List[ChatRequestHandler]) -> None:

        for request_handler in request_handlers:

            if request_handler.last_message_content == "":
                continue

            entity2 = self._game.get_entity_by_name(request_handler._name)
            assert entity2 is not None
            self._handle_response(entity2, request_handler)

    #######################################################################################################################################
    def _handle_response(
        self, entity2: Entity, request_handler: ChatRequestHandler
    ) -> None:

        try:

            format_response = DrawCardsResponse.model_validate_json(
                json_format.strip_json_code_block(request_handler.last_message_content)
            )

            skills: List[Skill] = [
                skill_response.skill
                for skill_response in format_response.gen_skill_reponse
            ]

            details: List[HandDetail] = [
                HandDetail(
                    skill=skill_response.skill.name,
                    targets=skill_response.targets,
                    reason=skill_response.reason,
                    dialogue=skill_response.dialogue,
                )
                for skill_response in format_response.gen_skill_reponse
            ]

            if entity2.has(XCardPlayerComponent):
                # 如果是玩家，则需要更新玩家的手牌
                xcard_player_comp = entity2.get(XCardPlayerComponent)
                skills = [xcard_player_comp.skill]
                details = [
                    HandDetail(
                        skill=xcard_player_comp.skill.name,
                        targets=["根据技能描述和效果，所有适用的目标"],
                        reason="",
                        dialogue=f"看招！{xcard_player_comp.skill.name}！",
                    )
                ]

                # 只用这一次。
                entity2.remove(XCardPlayerComponent)

            entity2.replace(
                HandComponent,
                entity2._name,
                skills,
                details,
            )

        except Exception as e:
            logger.error(f"Exception: {e}")

    #######################################################################################################################################
    def _generate_requests(
        self, actor_entities: List[Entity]
    ) -> List[ChatRequestHandler]:

        request_handlers: List[ChatRequestHandler] = []

        last_round = self._game.current_engagement.last_round
        assert (
            not last_round.is_round_complete
        ), f"last_round.is_round_complete: {last_round.is_round_complete}"

        for entity in actor_entities:

            #
            current_stage = self._game.safe_get_stage_entity(entity)
            assert current_stage is not None

            # 生成消息
            message = _generate_prompt(
                self._skill_creation_count,
                current_stage._name,
                current_stage.get(EnvironmentComponent).narrate,
                last_round.round_turns,
            )

            # 生成请求处理器
            request_handlers.append(
                ChatRequestHandler(
                    agent_name=entity._name,
                    prompt=message,
                    chat_history=self._game.get_agent_short_term_memory(
                        entity
                    ).chat_history,
                )
            )

        return request_handlers

    #######################################################################################################################################
