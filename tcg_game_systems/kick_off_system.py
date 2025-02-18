from entitas import Entity, Matcher, ExecuteProcessor  # type: ignore
from overrides import override
from components.components import (
    WorldSystemComponent,
    StageComponent,
    ActorComponent,
    KickOffMessageComponent,
    KickOffFlagComponent,
    SystemMessageComponent,
)
from typing import Set, final, cast, List
from game.tcg_game_context import TCGGameContext
from game.tcg_game import TCGGame
from loguru import logger
from agent.chat_request_handler import ChatRequestHandler


###############################################################################################################################################
def _generate_actor_kick_off_prompt(kick_off_message: str, epoch_script: str) -> str:
    return f"""# 游戏启动!
你将开始你的扮演，此时的世界背景如下，请仔细阅读并牢记，以确保你的行为和言语符合游戏设定，不会偏离时代背景。

## 当前世界背景
{epoch_script}

## 你的初始设定
{kick_off_message}

## 输出要求
请简短回复。"""


###############################################################################################################################################


######################################################################################################################################################
@final
class KickOffSystem(ExecuteProcessor):

    def __init__(self, context: TCGGameContext) -> None:
        self._context: TCGGameContext = context
        self._game: TCGGame = cast(TCGGame, context._game)
        assert self._game is not None

    ######################################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    ######################################################################################################################################################
    @override
    async def a_execute1(self) -> None:

        entities: Set[Entity] = self._context.get_group(
            Matcher(
                all_of=[SystemMessageComponent, KickOffMessageComponent],
                any_of=[ActorComponent, WorldSystemComponent],
                none_of=[KickOffFlagComponent, StageComponent],  # todo 场景先不要
            )
        ).entities.copy()

        if len(entities) == 0:
            return

        # 添加系统消息
        self._add_system_message(entities)

        # 处理请求
        await self._process_kick_off_request(entities)

    ######################################################################################################################################################
    async def _process_kick_off_request(self, entities: Set[Entity]) -> None:

        # 添加请求处理器
        request_handlers: List[ChatRequestHandler] = []

        for entity1 in entities:

            kick_off_message_comp = entity1.get(KickOffMessageComponent)
            assert kick_off_message_comp is not None
            kick_off_message = kick_off_message_comp.content

            agent_short_term_memory = self._game.get_agent_short_term_memory(entity1)

            request_handlers.append(
                ChatRequestHandler(
                    name=entity1._name,
                    # prompt=kick_off_message,
                    prompt=_generate_actor_kick_off_prompt(
                        kick_off_message, self._game.world_runtime.root.epoch_script
                    ),
                    chat_history=agent_short_term_memory.chat_history,
                )
            )

        # 并发
        await self._game.langserve_system.gather(request_handlers=request_handlers)

        # 添加上下文。
        for request_handler in request_handlers:
            logger.warning(
                f"Agent: {request_handler._name}, Response:\n{request_handler.response_content}"
            )

            if request_handler.response_content == "":
                logger.warning(f"Agent: {request_handler._name}, Response is empty.")
                continue

            entity2 = self._context.get_entity_by_name(request_handler._name)
            assert entity2 is not None
            self._game.append_human_message(entity2, request_handler._prompt)
            self._game.append_ai_message(entity2, request_handler.response_content)

            entity2.replace(KickOffFlagComponent, entity2._name)

    ######################################################################################################################################################
    def _add_system_message(self, entities: Set[Entity]) -> None:
        for entity in entities:
            system_message_comp = entity.get(SystemMessageComponent)
            assert system_message_comp is not None
            self._game.append_system_message(entity, system_message_comp.content)

    ######################################################################################################################################################
