from pydantic import BaseModel
from entitas import Entity, Matcher, GroupEvent  # type: ignore
from agent.chat_request_handler import ChatRequestHandler
from overrides import override
from typing import List, final
from loguru import logger
from components.actions2 import FeedbackAction2
from tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem
from tcg_models.v_0_0_1 import Effect
import format_string.json_format

# from components.components import CombatAttributesComponent


#######################################################################################################################################
@final
class FeedbackResponse(BaseModel):
    description: str
    effects: List[Effect]


#######################################################################################################################################
def _generate_prompt(
    # combat_attributes_component: CombatAttributesComponent,
    feedback_component: FeedbackAction2,
) -> str:

    feedback_response_example = FeedbackResponse(
        description="第一人称状态描述（<200字）",
        effects=[
            Effect(description="效果1描述", round=1),
            Effect(description="效果2描述", round=2),
        ],
    )

    return f"""# 提示！状态更新，根据战斗结果，更新状态并反馈！(仅反馈你自身状态)
## 战斗结果
### 计算摘要
{feedback_component.calculation}
### 演绎摘要
{feedback_component.performance}
## 输出内容
1. 状态感受：单段紧凑自述（禁用换行/空行）
2. 持续效果：仍将持续生效的效果列表。
    - 注意！效果描述和剩余回合数。
## 输出格式规范
{feedback_response_example.model_dump_json()}
- 数值精确，禁用文字修饰。
- 直接输出合规JSON"""


#######################################################################################################################################
@final
class FeedbackActionSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(FeedbackAction2): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(FeedbackAction2)

    #######################################################################################################################################
    @override
    async def a_execute2(self) -> None:
        if len(self._react_entities_copy) > 0:
            await self._process_request(self._react_entities_copy)

    #######################################################################################################################################
    async def _process_request(self, react_entities: List[Entity]) -> None:

        #
        chat_requests = self._generate_chat_requests(set(react_entities))

        # 用语言服务系统进行推理。
        await self._game.langserve_system.gather(request_handlers=chat_requests)

        # 处理返回结果。
        self._handle_chat_responses(chat_requests)

    #######################################################################################################################################
    def _handle_chat_responses(
        self, request_handlers: List[ChatRequestHandler]
    ) -> None:

        for request_handler in request_handlers:

            if request_handler.response_content == "":
                logger.error(f"Agent: {request_handler._name}, Response is empty.")
                continue

            # logger.warning(
            #     f"Agent: {request_handler._name}, Response:\n{request_handler.response_content}"
            # )

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

            logger.info(
                f"Agent: {entity._name}, Response = {format_response.model_dump_json()}"
            )

            pass

        except:
            logger.error(
                f"""返回格式错误, Response = \n{request_handler.response_content}"""
            )

    #######################################################################################################################################
    def _generate_chat_requests(
        self, actor_entities: set[Entity]
    ) -> List[ChatRequestHandler]:

        request_handlers: List[ChatRequestHandler] = []

        for entity in actor_entities:

            feedback_action2 = entity.get(FeedbackAction2)

            # combat_attributes_component = entity.get(CombatAttributesComponent)
            # assert combat_attributes_component is not None

            # 生成消息
            message = _generate_prompt(feedback_action2)
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
