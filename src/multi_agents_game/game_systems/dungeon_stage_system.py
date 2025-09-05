from typing import Dict, final

from loguru import logger
from overrides import override
from pydantic import BaseModel

from ..chat_services.client import ChatClient
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from ..models import (
    DrawCardsAction,
    EnvironmentComponent,
    TurnAction,
)
from ..utils import json_format


#######################################################################################################################################
@final
class StagePlanningResponse(BaseModel):
    environment: str = ""


#######################################################################################################################################
def _generate_prompt(
    actors_appearances_mapping: Dict[str, str],
) -> str:

    actors_appearances_info = []
    for actor_name, appearance in actors_appearances_mapping.items():
        actors_appearances_info.append(f"{actor_name}: {appearance}")
    if len(actors_appearances_info) == 0:
        actors_appearances_info.append("无")

    response_example = StagePlanningResponse(environment="场景内的环境描述")

    return f"""# 请你输出你的场景描述
## 场景内角色
{"\n".join(actors_appearances_info)}
## 输出内容-场景描述
- 场景内的环境描述，不要包含任何角色信息。
## 输出要求
- 所有输出必须为第三人称视角。
- 不要使用```json```来封装内容。
### 输出格式(JSON)
{response_example.model_dump_json()}"""


#######################################################################################################################################
@final
class DungeonStageSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    #######################################################################################################################################
    @override
    async def execute(self) -> None:
        if not self._is_phase_valid():
            logger.debug("StagePlanningSystem: 状态无效，跳过执行。")
            return
        self._process_stage_planning()

    #######################################################################################################################################
    def _is_phase_valid(self) -> bool:

        if (
            self._game.current_engagement.is_post_wait_phase
            or self._game.current_engagement.is_complete_phase
        ):
            return False

        if self._game.current_engagement.is_on_going_phase:
            entities = self._game.get_group(
                Matcher(any_of=[TurnAction, DrawCardsAction])
            ).entities
            if len(entities) > 0:
                logger.debug(
                    "StagePlanningSystem: 当前阶段有any_of=[TurnAction, DrawCardsAction]行动，跳过执行。"
                )
                return False

        return True

    #######################################################################################################################################
    def _process_stage_planning(self) -> None:

        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        current_stage = self._game.safe_get_stage_entity(player_entity)
        assert current_stage is not None

        request_handler = self._generate_requests(current_stage)
        self._game.chat_system.request(request_handlers=[request_handler])

        # if request_handler.last_message_content == "":
        #     logger.error(f"Agent: {request_handler._name}, Response is empty.")
        #     return

        self._handle_response(current_stage, request_handler)

    #######################################################################################################################################
    def _generate_requests(self, stage_entity: Entity) -> ChatClient:

        # 获取场景内角色的外貌信息
        actors_appearances_mapping: Dict[str, str] = (
            self._game.retrieve_actor_appearance_on_stage_mapping(stage_entity)
        )

        # 生成提示信息
        message = _generate_prompt(actors_appearances_mapping)

        # 生成请求处理器
        return ChatClient(
            agent_name=stage_entity._name,
            prompt=message,
            chat_history=self._game.get_agent_short_term_memory(
                stage_entity
            ).chat_history,
        )

    #######################################################################################################################################
    def _handle_response(
        self, stage_entity: Entity, request_handler: ChatClient
    ) -> None:

        # 核心处理
        try:

            format_response = StagePlanningResponse.model_validate_json(
                json_format.strip_json_code_block(request_handler.response_content)
            )

            self._game.append_human_message(stage_entity, request_handler._prompt)
            self._game.append_ai_message(stage_entity, request_handler.ai_messages)

            # 更新环境描写
            if format_response.environment != "":
                stage_entity.replace(
                    EnvironmentComponent,
                    stage_entity._name,
                    format_response.environment,
                )

        except Exception as e:
            logger.error(f"Exception: {e}")


#######################################################################################################################################
