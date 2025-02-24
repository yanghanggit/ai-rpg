from agent.chat_request_handler import ChatRequestHandler
from components.components import (
    StageComponent,
    KickOffDoneFlagComponent,
    PlayerActorFlagComponent,
    StageEnvironmentComponent,
    StageNarratePlanningPermitFlagComponent,
)
from components.actions import (
    STAGE_AVAILABLE_ACTIONS_REGISTER,
)
from entitas import ExecuteProcessor, Matcher  # type: ignore
from overrides import override
from typing import List, final, cast
from game.tcg_game_context import TCGGameContext
from game.tcg_game import TCGGame
from loguru import logger


#######################################################################################################################################
@final
class StageNarratePlanningSystem(ExecuteProcessor):

    def __init__(self, context: TCGGameContext) -> None:
        self._context: TCGGameContext = context
        self._game: TCGGame = cast(TCGGame, context._game)
        assert self._game is not None

    #######################################################################################################################################
    @override
    def execute(self) -> None:
        logger.debug("StagePlanningExecutionSystem.execute()")

    #######################################################################################################################################
    @override
    async def a_execute1(self) -> None:
        # logger.debug("StagePlanningExecutionSystem.a_execute1()")
        await self._process_stage_planning_request()

    #######################################################################################################################################
    @override
    async def a_execute2(self) -> None:
        logger.debug("StagePlanningExecutionSystem.a_execute2()")

    #######################################################################################################################################
    async def _process_stage_planning_request(self) -> None:

        stage_entities = self._context.get_group(
            Matcher(
                all_of=[
                    StageNarratePlanningPermitFlagComponent,
                ]
            )
        ).entities.copy()

        if len(stage_entities) == 0:
            return

        request_handlers: List[ChatRequestHandler] = []
        for entity in stage_entities:
            message = _generate_stage_plan_prompt()
            assert message is not None
            agent_short_term_memory = self._game.get_agent_short_term_memory(entity)
            request_handlers.append(
                ChatRequestHandler(
                    name=entity._name,
                    prompt=message,
                    chat_history=agent_short_term_memory.chat_history,
                )
            )

        await self._game.langserve_system.gather(request_handlers=request_handlers)

        for request_handler in request_handlers:
            logger.warning(
                f"Agent: {request_handler._name}, Response:\n{request_handler.response_content}"
            )

            if request_handler.response_content == "":
                continue

            entity2 = self._context.get_entity_by_name(request_handler._name)
            assert entity2 is not None
            self._game.append_human_message(
                entity2, _compress_stage_plan_prompt(request_handler._prompt)
            )
            self._game.append_ai_message(entity2, request_handler.response_content)
            # 更新环境描写
            entity2.replace(
                StageEnvironmentComponent,
                entity2._name,
                request_handler.response_content,
            )

    #######################################################################################################################################


#######################################################################################################################################


def _generate_stage_plan_prompt() -> str:
    return f"""# 请推理你的环境是否会发生变化并输出变化后的场景描述，请确保你的描述符合游戏设定，不会偏离时代背景。
## 场景内角色进行的动作
{'无,TODO'}
## 输出要求
- 尽量简短。
- 若场景内不会发生变化，请输出对原环境的类似描述，或原环境其他方面的描述。"""


def _compress_stage_plan_prompt(prompt: str) -> str:
    # logger.debug(f"原来的提示词为:\n{prompt}")
    return "# 请推理你的环境可能发生哪些变化。尽量简短输出。"
