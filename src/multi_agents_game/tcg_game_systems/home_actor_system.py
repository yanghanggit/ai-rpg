from pydantic import BaseModel
from ..entitas import ExecuteProcessor, Matcher, Entity
from ..chat_services.chat_request_handler import ChatRequestHandler
from ..format_string import json_format
from ..models import (
    ActorComponent,
    EnvironmentComponent,
    CanStartPlanningComponent,
    SpeakAction,
    MindVoiceAction,
    WhisperAction,
    AnnounceAction,
)
from overrides import override
from typing import Dict, List, final
from ..game.tcg_game import TCGGame
from loguru import logger


#######################################################################################################################################
@final
class ActorPlanningResponse(BaseModel):
    speak_actions: Dict[str, str] = {}
    whisper_actions: Dict[str, str] = {}
    announce_actions: str = ""
    mind_voice_actions: str = ""


#######################################################################################################################################
def _generate_prompt(
    current_stage: str,
    current_stage_narration: str,
    actors_appearance_mapping: Dict[str, str],
) -> str:

    actors_appearances_info = []
    for actor_name, appearance in actors_appearance_mapping.items():
        actors_appearances_info.append(f"{actor_name}: {appearance}")
    if len(actors_appearances_info) == 0:
        actors_appearances_info.append("无")

    # 格式示例
    actor_response_example = ActorPlanningResponse(
        speak_actions={
            "场景内角色全名": "你要说的内容（场景内其他角色会听见）",
        },
        whisper_actions={
            "场景内角色全名": "你要说的内容（只有你和目标角色能听见）",
        },
        announce_actions="你要说的内容（所有的角色都能听见）",
        mind_voice_actions="你要说的内容（内心独白，只有你自己能听见）",
    )

    return f"""# 请制定你的行动计划！决定你将要做什么，并以 JSON 格式输出。
## 当前场景
{current_stage} | {current_stage_narration}
## 场景内角色
{"\n".join(actors_appearances_info)}
## 输出内容
- 请根据当前场景，角色信息与你的历史，制定你的行动计划。
- 请严格遵守全名机制。
- 第一人称视角。
## 输出格式
### 标准示例
{actor_response_example.model_dump_json()}
### 注意事项
- speak_actions/whisper_actions/announce_actions 这三种行动只能选其一
- mind_voice_actions可选。
- 根据‘标准示例’，直接输出合规JSON。"""


#######################################################################################################################################
def _compress_prompt(
    prompt: str,
) -> str:
    return "# 请做出你的计划，决定你将要做什么，并以 JSON 格式输出。"


#######################################################################################################################################
@final
class HomeActorSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    #######################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    #######################################################################################################################################
    @override
    async def a_execute1(self) -> None:
        await self._process_actor_planning_request()

    #######################################################################################################################################
    async def _process_actor_planning_request(self) -> None:

        # 获取所有需要进行角色规划的角色
        actor_entities = self._game.get_group(
            Matcher(
                all_of=[CanStartPlanningComponent, ActorComponent],
            )
        ).entities.copy()

        if len(actor_entities) == 0:
            return

        # 处理角色规划请求
        request_handlers: List[ChatRequestHandler] = self._generate_requests(
            actor_entities
        )

        # 语言服务
        await self._game.chat_system.gather(request_handlers=request_handlers)

        # 处理角色规划请求
        self._handle_responses(request_handlers)

    #######################################################################################################################################
    def _handle_responses(self, request_handlers: List[ChatRequestHandler]) -> None:

        for request_handler in request_handlers:

            if request_handler.last_message_content == "":
                continue

            entity2 = self._game.get_entity_by_name(request_handler._name)
            assert entity2 is not None
            self._handle_response(entity2, request_handler)

    #######################################################################################################################################
    def _handle_response(
        self, entity2: Entity, request_handler: ChatRequestHandler
    ) -> None:

        # 核心处理
        try:

            format_response = ActorPlanningResponse.model_validate_json(
                json_format.strip_json_code_block(request_handler.last_message_content)
            )

            self._game.append_human_message(
                entity2, _compress_prompt(request_handler._prompt)
            )
            self._game.append_ai_message(entity2, request_handler.ai_message)

            # 添加说话动作
            if len(format_response.speak_actions) > 0:
                entity2.replace(
                    SpeakAction, entity2._name, format_response.speak_actions
                )

            # 添加耳语动作
            if len(format_response.whisper_actions) > 0:
                entity2.replace(
                    WhisperAction, entity2._name, format_response.whisper_actions
                )

            # 添加宣布动作
            if format_response.announce_actions != "":
                entity2.replace(
                    AnnounceAction, entity2._name, format_response.announce_actions
                )

            # 添加内心独白
            if format_response.mind_voice_actions != "":
                entity2.replace(
                    MindVoiceAction, entity2._name, format_response.mind_voice_actions
                )

        except Exception as e:
            logger.error(f"Exception: {e}")

    #######################################################################################################################################
    def _generate_requests(
        self, actor_entities: set[Entity]
    ) -> List[ChatRequestHandler]:

        request_handlers: List[ChatRequestHandler] = []

        for entity in actor_entities:

            current_stage = self._game.safe_get_stage_entity(entity)
            assert current_stage is not None

            # 找到当前场景内所有角色
            actors_apperances_mapping = (
                self._game.retrieve_actor_appearance_on_stage_mapping(current_stage)
            )
            actors_apperances_mapping.pop(entity._name, None)

            # 生成消息
            message = _generate_prompt(
                current_stage._name,
                current_stage.get(EnvironmentComponent).narrate,
                actors_apperances_mapping,
            )

            # 生成请求处理器
            request_handlers.append(
                ChatRequestHandler(
                    agent_name=entity._name,
                    prompt=message,
                    chat_history=self._game.get_agent_short_term_memory(
                        entity
                    ).chat_history,
                )
            )

        return request_handlers

    #######################################################################################################################################
