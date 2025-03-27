from entitas import Matcher, Entity, Matcher, ExecuteProcessor  # type: ignore
from pydantic import BaseModel
from extended_systems.chat_request_handler import ChatRequestHandler
from components.components_v_0_0_1 import (
    StageEnvironmentComponent,
    HandComponent,
)
from overrides import override
from typing import Dict, final
from game.tcg_game import TCGGame
from loguru import logger
import format_string.json_format


#######################################################################################################################################
@final
class StagePlanningResponse(BaseModel):
    environment_narration: str = ""


#######################################################################################################################################
def _generate_prompt(
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
class DungeonStagePlanningSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    #######################################################################################################################################
    @override
    def execute(self) -> None:
        if not self._is_phase_valid():
            logger.debug("StagePlanningSystem: 状态无效，跳过执行。")
            return
        self._process_stage_planning()

    #######################################################################################################################################
    def _is_phase_valid(self) -> bool:

        if (
            self._game.combat_system.is_post_wait_phase
            or self._game.combat_system.is_complete_phase
        ):
            return False

        if self._game.combat_system.is_on_going_phase:
            actor_entities = self._game.get_group(
                Matcher(
                    all_of=[
                        HandComponent,
                    ],
                )
            ).entities

            if len(actor_entities) == 0:
                return False

        return True

    #######################################################################################################################################
    def _process_stage_planning(self) -> None:

        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        current_stage = self._game.safe_get_stage_entity(player_entity)
        assert current_stage is not None

        request_handler = self._generate_requests(current_stage)
        self._game.langserve_system.handle(request_handlers=[request_handler])

        if request_handler.response_content == "":
            logger.error(f"Agent: {request_handler._name}, Response is empty.")
            return

        self._handle_response(current_stage, request_handler)

    #######################################################################################################################################
    def _generate_requests(self, stage_entity: Entity) -> ChatRequestHandler:

        # 获取场景内角色的外貌信息
        actors_appearances_mapping: Dict[str, str] = (
            self._game.retrieve_actor_appearance_on_stage_mapping(stage_entity)
        )

        # 生成提示信息
        message = _generate_prompt(actors_appearances_mapping)

        # 生成请求处理器
        return ChatRequestHandler(
            name=stage_entity._name,
            prompt=message,
            chat_history=self._game.get_agent_short_term_memory(
                stage_entity
            ).chat_history,
        )

    #######################################################################################################################################
    def _handle_response(
        self, stage_entity: Entity, request_handler: ChatRequestHandler
    ) -> None:

        assert stage_entity.has(StageEnvironmentComponent)

        # 核心处理
        try:

            format_response = StagePlanningResponse.model_validate_json(
                format_string.json_format.strip_json_code_block(
                    request_handler.response_content
                )
            )

            logger.warning(
                f"Stage: {stage_entity._name}, Response:\n{format_response.model_dump_json()}"
            )

            self._game.append_human_message(
                stage_entity, _compress_stage_plan_prompt(request_handler._prompt)
            )
            self._game.append_ai_message(stage_entity, request_handler.response_content)

            # 更新环境描写
            if format_response.environment_narration != "":
                stage_entity.replace(
                    StageEnvironmentComponent,
                    stage_entity._name,
                    format_response.environment_narration,
                )

        except:
            logger.error(
                f"""返回格式错误: {stage_entity._name}, Response = \n{request_handler.response_content}"""
            )


#######################################################################################################################################
