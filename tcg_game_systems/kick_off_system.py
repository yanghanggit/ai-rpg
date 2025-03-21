from entitas import Entity, Matcher, ExecuteProcessor  # type: ignore
from overrides import override
from components.components_v_0_0_1 import (
    WorldSystemComponent,
    StageComponent,
    ActorComponent,
    KickOffMessageComponent,
    KickOffDoneFlagComponent,
    SystemMessageComponent,
    StageEnvironmentComponent,
)
from typing import Set, final, List
from game.tcg_game import TCGGame
from loguru import logger
from extended_systems.chat_request_handler import ChatRequestHandler


###############################################################################################################################################
def _generate_actor_kick_off_prompt(kick_off_message: str) -> str:
    return f"""# 游戏启动! 你将开始你的扮演。你将以此为初始状态，开始你的冒险。
## 这是你的启动消息
{kick_off_message}
## 输出要求
- 你的内心活动，尽量简短。"""


###############################################################################################################################################
def _generate_stage_kick_off_prompt(
    kick_off_message: str,
) -> str:
    return f"""# 游戏启动! 你将开始你的扮演。你将以此为初始状态，开始你的冒险。
## 这是你的启动消息
{kick_off_message}
## 输出要求
- 输出场景描述，尽量简短。"""


###############################################################################################################################################
def _generate_world_system_kick_off_prompt() -> str:
    return f"""# 游戏启动! 你将开始你的扮演。你将以此为初始状态，开始你的冒险。
## 这是你的启动消息
- 请回答你的职能与描述。
## 输出要求
- 确认你的职能，尽量简短。"""


###############################################################################################################################################


###############################################################################################################################################
@final
class KickOffSystem(ExecuteProcessor):

    ###############################################################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###############################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    ###############################################################################################################################################
    @override
    async def a_execute1(self) -> None:

        entities: Set[Entity] = self._game.get_group(
            Matcher(
                all_of=[SystemMessageComponent, KickOffMessageComponent],
                any_of=[ActorComponent, WorldSystemComponent, StageComponent],
                none_of=[KickOffDoneFlagComponent],
            )
        ).entities.copy()

        if len(entities) == 0:
            return

        # 添加系统消息
        self._add_system_message(entities)

        # 处理请求
        await self._process_kick_off_request(entities)

    ###############################################################################################################################################
    async def _process_kick_off_request(self, entities: Set[Entity]) -> None:

        # 添加请求处理器
        request_handlers: List[ChatRequestHandler] = []

        for entity1 in entities:
            # 不同实体生成不同的提示
            gen_prompt = self._generate_kick_off_prompt(entity1)
            # assert gen_prompt is not ""
            if gen_prompt == "":
                continue

            agent_short_term_memory = self._game.get_agent_short_term_memory(entity1)
            request_handlers.append(
                ChatRequestHandler(
                    name=entity1._name,
                    prompt=gen_prompt,
                    chat_history=agent_short_term_memory.chat_history,
                )
            )

        # 并发
        await self._game.langserve_system.gather(request_handlers=request_handlers)

        # 添加上下文。
        for request_handler in request_handlers:

            entity2 = self._game.get_entity_by_name(request_handler._name)
            assert entity2 is not None

            if request_handler.response_content == "":
                logger.error(
                    f"Agent: {request_handler._name}, Response is empty!!!!!!!!!!!!!!!!!!!!!!!!! KickOff Failed."
                )
                continue

            logger.warning(
                f"Agent: {request_handler._name}, Response:\n{request_handler.response_content}"
            )

            self._game.append_human_message(entity2, request_handler._prompt)
            self._game.append_ai_message(entity2, request_handler.response_content)

            # 必须执行
            entity2.replace(KickOffDoneFlagComponent, entity2._name)

            # 若是场景，用response替换narrate
            if entity2.has(StageComponent):
                entity2.replace(
                    StageEnvironmentComponent,
                    entity2._name,
                    request_handler.response_content,
                )
            elif entity2.has(ActorComponent):
                pass

    ###############################################################################################################################################
    def _generate_kick_off_prompt(self, entity: Entity) -> str:

        kick_off_message_comp = entity.get(KickOffMessageComponent)
        assert kick_off_message_comp is not None
        kick_off_message = kick_off_message_comp.content

        # 不同实体生成不同的提示
        gen_prompt = ""
        if entity.has(ActorComponent):
            # 角色的
            gen_prompt = _generate_actor_kick_off_prompt(kick_off_message)
        elif entity.has(StageComponent):
            # 舞台的
            gen_prompt = _generate_stage_kick_off_prompt(
                kick_off_message,
            )
        elif entity.has(WorldSystemComponent):
            # 世界系统的
            gen_prompt = _generate_world_system_kick_off_prompt()

        return gen_prompt

    ###############################################################################################################################################
    def _add_system_message(self, entities: Set[Entity]) -> None:
        for entity in entities:
            system_message_comp = entity.get(SystemMessageComponent)
            assert system_message_comp is not None
            self._game.append_system_message(entity, system_message_comp.content)

    ###############################################################################################################################################
