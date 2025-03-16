from entitas import Entity, Matcher, GroupEvent  # type: ignore
from agent.chat_request_handler import ChatRequestHandler
from overrides import override
from typing import List, final
from loguru import logger
from components.actions2 import FeedbackAction2
from tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem


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

            logger.warning(
                f"Agent: {request_handler._name}, Response:\n{request_handler.response_content}"
            )

            entity2 = self._game.get_entity_by_name(request_handler._name)
            assert entity2 is not None
            self._handle_response(entity2, request_handler)

    #######################################################################################################################################
    def _handle_response(
        self, entity: Entity, request_handler: ChatRequestHandler
    ) -> None:

        try:
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

            # 生成消息
            message = f"""# 请根据发生事件，更新你的状态。
## 输出要求
- 使用第一人称描述。
- 输出一整段文字来描述你目前有的状态。
- 明确哪些是增益状态，哪些是减益状态。
- 请不要使用换行与空行。"""
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
