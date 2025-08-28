from typing import Dict, List, Set, final

from loguru import logger
from overrides import override
from pydantic import BaseModel

from ..chat_services.chat_request_handler import ChatRequestHandler
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from ..models import (
    CanStartPlanningComponent,
    EnvironmentComponent,
    HomeComponent,
    StageComponent,
)
from ..utils import json_format


#######################################################################################################################################
@final
class StagePlanningResponse(BaseModel):
    environment_narration: str = ""


#######################################################################################################################################
def _generate_stage_plan_prompt(
    actors_appearances_mapping: Dict[str, str],
) -> str:

    actors_appearances_info = []
    for actor_name, appearance in actors_appearances_mapping.items():
        actors_appearances_info.append(f"{actor_name}: {appearance}")
    if len(actors_appearances_info) == 0:
        actors_appearances_info.append("无")

    stage_response_example = StagePlanningResponse(
        environment_narration="场景内的环境描述"
    )

    return f"""# 请你输出你的场景描述
## 场景内角色
{"\n".join(actors_appearances_info)}
## 输出内容-场景描述
- 场景内的环境描述，不要包含任何角色信息。
## 输出要求
- 所有输出必须为第三人称视角。
- 不要使用```json```来封装内容。
### 输出格式(JSON)
{stage_response_example.model_dump_json()}"""


#######################################################################################################################################
def _compress_stage_plan_prompt(prompt: str) -> str:
    return "# 请你输出你的场景描述。并以 JSON 格式输出。"


#######################################################################################################################################
@final
class HomeStageSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    #######################################################################################################################################
    @override
    async def execute(self) -> None:
        await self._process_stage_planning_request()

    #######################################################################################################################################
    async def _process_stage_planning_request(self) -> None:

        stage_entities = self._game.get_group(
            Matcher(all_of=[CanStartPlanningComponent, StageComponent, HomeComponent])
        ).entities.copy()

        request_handlers: List[ChatRequestHandler] = (
            self._generate_chat_request_handlers(stage_entities)
        )

        await self._game.chat_system.gather(request_handlers=request_handlers)

        self._handle_chat_responses(request_handlers)

    #######################################################################################################################################
    def _generate_chat_request_handlers(
        self, stage_entities: Set[Entity]
    ) -> List[ChatRequestHandler]:

        request_handlers: List[ChatRequestHandler] = []

        for stage_entity in stage_entities:

            environment_component = stage_entity.get(EnvironmentComponent)
            if environment_component.narrate != "":
                # 如果环境描述不为空，跳过
                continue

            # 获取场景内角色的外貌信息
            actors_appearances_mapping: Dict[str, str] = (
                self._game.retrieve_actor_appearance_on_stage_mapping(stage_entity)
            )

            # 生成提示信息
            message = _generate_stage_plan_prompt(actors_appearances_mapping)

            # 生成请求处理器
            request_handlers.append(
                ChatRequestHandler(
                    agent_name=stage_entity._name,
                    prompt=message,
                    chat_history=self._game.get_agent_short_term_memory(
                        stage_entity
                    ).chat_history,
                )
            )
        return request_handlers

    #######################################################################################################################################
    def _handle_chat_responses(
        self, request_handlers: List[ChatRequestHandler]
    ) -> None:
        for request_handler in request_handlers:

            if request_handler.last_message_content == "":
                continue

            entity2 = self._game.get_entity_by_name(request_handler._name)
            assert entity2 is not None

            self._handle_stage_response(entity2, request_handler)

    #######################################################################################################################################
    def _handle_stage_response(
        self, entity2: Entity, request_handler: ChatRequestHandler
    ) -> None:

        try:

            format_response = StagePlanningResponse.model_validate_json(
                json_format.strip_json_code_block(request_handler.last_message_content)
            )

            self._game.append_human_message(
                entity2, _compress_stage_plan_prompt(request_handler._prompt)
            )
            self._game.append_ai_message(entity2, request_handler.ai_message)

            # 更新环境描写
            if format_response.environment_narration != "":
                entity2.replace(
                    EnvironmentComponent,
                    entity2._name,
                    format_response.environment_narration,
                )

        except Exception as e:
            logger.error(f"Exception: {e}")


#######################################################################################################################################
