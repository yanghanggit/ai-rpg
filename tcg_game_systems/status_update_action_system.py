from entitas import Entity, Matcher, GroupEvent  # type: ignore
from typing import List, Set, Tuple, final, override
from components.components import StageComponent, ActorComponent
from components.actions2 import (
    StatusUpdateAction,
)
from tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem
from agent.chat_request_handler import ChatRequestHandler
from loguru import logger


@final
class StatusUpdateActionSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(StatusUpdateAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(StatusUpdateAction)

    ####################################################################################################################################
    @override
    async def a_execute2(self) -> None:

        # 准备数据
        stage_entities, actor_entities = self._prepare_entities()

        # 合并一下 request 任务。
        request_handlers: List[ChatRequestHandler] = []
        request_handlers.extend(self._gen_stages_requests(stage_entities))
        request_handlers.extend(self._gen_actors_requests(actor_entities))

        # 并发执行。
        await self._game.langserve_system.gather(request_handlers=request_handlers)

        # 后续处理
        for request_handler in request_handlers:

            if request_handler.response_content == "":
                continue

            entity2 = self._game.get_entity_by_name(request_handler._name)
            assert entity2 is not None

            # 分开处理
            if entity2.has(StageComponent):
                # 处理场景
                self._handle_stage_response(entity2, request_handler)
            elif entity2.has(ActorComponent):
                # 处理角色
                self._handle_actor_response(entity2, request_handler)
            else:
                assert False, f"Unknown entity type: {entity2}"

    ####################################################################################################################################
    def _prepare_entities(self) -> Tuple[Set[Entity], Set[Entity]]:
        stage_entities: Set[Entity] = set()
        actor_entities: Set[Entity] = set()

        # 先分类
        for entity in self._react_entities_copy:

            # 找所在场景
            stage_entity = self._game.safe_get_stage_entity(entity)
            assert stage_entity is not None
            stage_entities.add(stage_entity)

            # 找所在角色
            actor_entities.update(self._game.retrieve_actors_on_stage(stage_entity))

        return stage_entities, actor_entities

    ####################################################################################################################################
    def _gen_stages_requests(
        self, stage_entities: Set[Entity]
    ) -> List[ChatRequestHandler]:

        ret: List[ChatRequestHandler] = []

        for stage_entity in stage_entities:

            assert stage_entity.has(StageComponent)

            message = "# 提示: 将你目前的状态与全部信息告诉我。保持内容简洁，但不要遗漏重要信息。"

            agent_short_term_memory = self._game.get_agent_short_term_memory(
                stage_entity
            )

            ret.append(
                ChatRequestHandler(
                    name=stage_entity._name,
                    prompt=message,
                    chat_history=agent_short_term_memory.chat_history,
                )
            )
        return ret

    ####################################################################################################################################
    def _gen_actors_requests(
        self, actor_entities: Set[Entity]
    ) -> List[ChatRequestHandler]:

        ret: List[ChatRequestHandler] = []

        for actor_entity in actor_entities:

            assert actor_entity.has(ActorComponent)

            message = "# 提示: 将你目前的状态与全部信息告诉我。保持内容简洁，但不要遗漏重要信息。"

            agent_short_term_memory = self._game.get_agent_short_term_memory(
                actor_entity
            )

            ret.append(
                ChatRequestHandler(
                    name=actor_entity._name,
                    prompt=message,
                    chat_history=agent_short_term_memory.chat_history,
                )
            )
        return ret

    ####################################################################################################################################
    def _handle_stage_response(
        self, stage_entity: Entity, request_handler: ChatRequestHandler
    ) -> None:
        assert stage_entity.has(StageComponent)
        assert stage_entity._name == request_handler._name

        # self._game.append_human_message(stage_entity, request_handler._prompt)
        # self._game.append_ai_message(stage_entity, request_handler.response_content)

        logger.debug(
            f"Stage: {stage_entity._name}, Response:\n{request_handler.response_content}"
        )

    ####################################################################################################################################
    def _handle_actor_response(
        self, actor_entity: Entity, request_handler: ChatRequestHandler
    ) -> None:
        assert actor_entity.has(ActorComponent)
        assert actor_entity._name == request_handler._name

        # self._game.append_human_message(actor_entity, request_handler._prompt)
        # self._game.append_ai_message(actor_entity, request_handler.response_content)

        logger.debug(
            f"Actor: {actor_entity._name}, Response:\n{request_handler.response_content}"
        )

    ####################################################################################################################################
