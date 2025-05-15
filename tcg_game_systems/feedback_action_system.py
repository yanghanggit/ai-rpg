from pydantic import BaseModel
from entitas import Entity, Matcher, GroupEvent  # type: ignore
from chat_services.chat_request_handler import ChatRequestHandler
from overrides import override
from typing import List, final
from loguru import logger
from tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem
import format_string.json_format
from models_v_0_0_1 import RPGCharacterProfileComponent, StatusEffect, FeedbackAction


#######################################################################################################################################
@final
class FeedbackResponse(BaseModel):
    description: str
    update_hp: float
    update_max_hp: float
    status_effects: List[StatusEffect]


#######################################################################################################################################
def _generate_prompt(
    rpg_character_profile_component: RPGCharacterProfileComponent,
    feedback_component: FeedbackAction,
) -> str:

    response_example = FeedbackResponse(
        description="第一人称状态描述（<200字）",
        update_hp=rpg_character_profile_component.rpg_character_profile.hp,
        update_max_hp=rpg_character_profile_component.rpg_character_profile.max_hp,
        status_effects=[
            StatusEffect(name="效果1的名字", description="效果1的描述", rounds=1),
            StatusEffect(name="效果2的名字", description="效果2的描述", rounds=2),
        ],
    )

    return f"""# 提示！根据战斗结果，更新状态并反馈！(仅反馈你自身状态)
## 战斗结果

### 计算摘要
{feedback_component.calculation}

### 演出摘要
{feedback_component.performance}

## 输出内容
1. 状态感受：单段紧凑自述（禁用换行/空行）
3. 生命值：根据‘战斗结果-计算摘要’，更新hp/max_hp。
2. 在你身上的持续效果：生成效果列表，包含效果名、效果描述、剩余回合数。
    
## 输出格式规范
{response_example.model_dump_json()}
- 直接输出合规JSON
- 数值精确，禁用文字修饰。
- 直接输出合规JSON"""


#######################################################################################################################################
@final
class FeedbackActionSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(FeedbackAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(FeedbackAction)

    #######################################################################################################################################
    @override
    async def a_execute2(self) -> None:
        if len(self._react_entities_copy) > 0:

            assert self._game.current_engagement.is_on_going_phase

            # 处理请求
            await self._process_request(self._react_entities_copy)

            # 清理不完整的反馈
            self._cleanup_incomplete_feedback(self._react_entities_copy)

    #######################################################################################################################################
    def _cleanup_incomplete_feedback(self, react_entities_copy: List[Entity]) -> None:
        for entity in react_entities_copy:
            feedback_action = entity.get(FeedbackAction)
            if (
                feedback_action.calculation == ""
                or feedback_action.performance == ""
                or feedback_action.description == ""
            ):
                logger.error(
                    f"FeedbackActionSystem: {entity._name}, FeedbackAction is not complete."
                )
                entity.remove(FeedbackAction)
                continue

    #######################################################################################################################################
    async def _process_request(self, react_entities: List[Entity]) -> None:

        #
        chat_requests = self._generate_requests(set(react_entities))

        # 用语言服务系统进行推理。
        await self._game.chat_system.gather(request_handlers=chat_requests)

        # 处理返回结果。
        self._handle_responses(chat_requests)

    #######################################################################################################################################
    def _handle_responses(self, request_handlers: List[ChatRequestHandler]) -> None:

        for request_handler in request_handlers:

            if request_handler.response_content == "":
                continue

            entity2 = self._game.get_entity_by_name(request_handler._name)
            assert entity2 is not None
            self._handle_response(entity2, request_handler)

    #######################################################################################################################################
    def _handle_response(
        self, entity: Entity, request_handler: ChatRequestHandler
    ) -> None:

        try:

            format_response = FeedbackResponse.model_validate_json(
                format_string.json_format.strip_json_code_block(
                    request_handler.response_content
                )
            )

            feedback_action2 = entity.get(FeedbackAction)
            assert feedback_action2 is not None

            entity.replace(
                FeedbackAction,
                feedback_action2.name,
                feedback_action2.calculation,
                feedback_action2.performance,
                format_response.description,
                int(format_response.update_hp),
                int(format_response.update_max_hp),
                format_response.status_effects,
            )

        except Exception as e:
            logger.error(f"Exception: {e}")

    #######################################################################################################################################
    def _generate_requests(
        self, actor_entities: set[Entity]
    ) -> List[ChatRequestHandler]:

        request_handlers: List[ChatRequestHandler] = []

        for entity in actor_entities:

            feedback_action = entity.get(FeedbackAction)
            assert feedback_action is not None

            rpg_character_profile_component = entity.get(RPGCharacterProfileComponent)
            assert rpg_character_profile_component is not None

            # 生成消息
            message = _generate_prompt(rpg_character_profile_component, feedback_action)
            # 生成请求处理器
            request_handlers.append(
                ChatRequestHandler(
                    name=entity._name,
                    prompt=message,
                    chat_history=self._game.get_agent_short_term_memory(
                        entity
                    ).chat_history,
                )
            )

        return request_handlers

    #######################################################################################################################################
