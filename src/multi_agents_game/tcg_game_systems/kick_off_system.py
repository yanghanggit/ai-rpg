from loguru import logger
from ..entitas import Entity, Matcher, ExecuteProcessor
from overrides import override
from ..models import (
    WorldSystemComponent,
    StageComponent,
    ActorComponent,
    KickOffMessageComponent,
    KickOffDoneComponent,
    EnvironmentComponent,
)
from typing import Set, final, List
from ..game.tcg_game import TCGGame
from ..chat_services.chat_request_handler import ChatRequestHandler


###############################################################################################################################################
def _generate_actor_kick_off_prompt(kick_off_message: str) -> str:
    return f"""# 游戏启动! 你将开始你的扮演。你将以此为初始状态，开始你的冒险。
## 这是你的启动消息
{kick_off_message}
## 输出要求
- 你的内心活动，单段紧凑自述（禁用换行/空行）"""


###############################################################################################################################################
def _generate_stage_kick_off_prompt(
    kick_off_message: str,
) -> str:
    return f"""# 游戏启动! 你将开始你的扮演。你将以此为初始状态，开始你的冒险。
## 这是你的启动消息
{kick_off_message}
## 输出要求
- 输出场景描述，单段紧凑自述（禁用换行/空行）"""


###############################################################################################################################################
def _generate_world_system_kick_off_prompt() -> str:
    return f"""# 游戏启动! 你将开始你的扮演。你将以此为初始状态，开始你的冒险。
## 这是你的启动消息
- 请回答你的职能与描述。
## 输出要求
- 确认你的职能，单段紧凑自述（禁用换行/空行）"""


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

        # 获取所有的舞台实体
        entities = self._game.get_group(
            Matcher(
                all_of=[KickOffMessageComponent],
                none_of=[KickOffDoneComponent],
            )
        ).entities.copy()

        if len(entities) == 0:
            return

        # 处理请求
        await self._process_request(entities)

    ###############################################################################################################################################
    async def _process_request(self, entities: Set[Entity]) -> None:

        # 添加请求处理器
        request_handlers: List[ChatRequestHandler] = []

        for entity1 in entities:
            # 不同实体生成不同的提示
            gen_prompt = self._generate_prompt(entity1)
            if gen_prompt == "":
                logger.warning(
                    f"KickOffSystem: {entity1._name} kick off message is empty. dungeon or monster?"
                )
                continue

            agent_short_term_memory = self._game.get_agent_short_term_memory(entity1)
            request_handlers.append(
                ChatRequestHandler(
                    agent_name=entity1._name,
                    prompt=gen_prompt,
                    chat_history=agent_short_term_memory.chat_history,
                )
            )

        # 并发
        await self._game.chat_system.gather(request_handlers=request_handlers)

        # 添加上下文。
        for request_handler in request_handlers:

            entity2 = self._game.get_entity_by_name(request_handler._name)
            assert entity2 is not None

            if request_handler.last_message_content == "":
                continue

            self._game.append_human_message(entity2, request_handler._prompt)
            self._game.append_ai_message(entity2, request_handler.ai_message)

            # 必须执行
            entity2.replace(KickOffDoneComponent, entity2._name)

            # 若是场景，用response替换narrate
            if (
                entity2.has(StageComponent)
                and request_handler.last_message_content != ""
            ):
                entity2.replace(
                    EnvironmentComponent,
                    entity2._name,
                    request_handler.last_message_content,
                )
            elif entity2.has(ActorComponent):
                pass

    ###############################################################################################################################################
    def _generate_prompt(self, entity: Entity) -> str:

        kick_off_message_comp = entity.get(KickOffMessageComponent)
        assert kick_off_message_comp is not None
        if kick_off_message_comp.content == "":
            # kick off消息为空，直接返回
            return ""

        # 不同实体生成不同的提示
        gen_prompt = ""
        if entity.has(ActorComponent):
            # 角色的
            gen_prompt = _generate_actor_kick_off_prompt(kick_off_message_comp.content)
        elif entity.has(StageComponent):
            # 舞台的
            gen_prompt = _generate_stage_kick_off_prompt(
                kick_off_message_comp.content,
            )
        elif entity.has(WorldSystemComponent):
            # 世界系统的
            gen_prompt = _generate_world_system_kick_off_prompt()

        return gen_prompt

    ###############################################################################################################################################
