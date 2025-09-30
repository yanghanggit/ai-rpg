from typing import Dict, List, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..chat_services.client import ChatClient
from ..entitas import Entity, Matcher, GroupEvent
from ..models import (
    AnnounceAction,
    EnvironmentComponent,
    MindVoiceAction,
    SpeakAction,
    WhisperAction,
    PlanAction,
    TransStageAction,
    HomeComponent,
)
from ..utils import json_format
from ..game_systems.base_action_reactive_system import BaseActionReactiveSystem


#######################################################################################################################################
@final
class ActorResponse(BaseModel):
    speak_actions: Dict[str, str] = {}
    whisper_actions: Dict[str, str] = {}
    announce_actions: str = ""
    mind_voice_actions: str = ""
    trans_stage_name: str = ""


#######################################################################################################################################
def _generate_prompt(
    current_stage: str,
    current_stage_narration: str,
    actors_appearance_mapping: Dict[str, str],
    available_home_stages: List[str],
) -> str:

    actors_appearances_info = []
    for actor_name, appearance in actors_appearance_mapping.items():
        actors_appearances_info.append(f"{actor_name}: {appearance}")
    if len(actors_appearances_info) == 0:
        actors_appearances_info.append("无")

    # 格式示例
    response_sample = ActorResponse(
        speak_actions={
            "场景内角色全名": "你要说的内容。1）如果是回答问题，根据自己的上下文中已有的信息来进行答复。2）如果上下文中的信息没有关于这个问题的准确答案，就回答“让我想想”。3）如果上一次的speak_actions里已经出现了“让我想想”，那么这次speak_actions必须是直接回答问题，不能再出现“让我想想”。并且这次回答问题时，如果上下文中有问题的准确答案就直接回答，如果上下文中还是没有相关信息或准确答案就回答“我不知道”。4）但如果上一次的speak_actions里有“我不知道”，那么这次的speak_actions不能再出现“我不知道”，而是一定会根据这次的问题重新思考。注意：只关注本次的提问，对于之前的提问，不需要再次回答。（场景内其他角色会听见）",
        },
        whisper_actions={
            "场景内角色全名": "你要说的内容（只有你和目标角色能听见）",
        },
        announce_actions="你要说的内容（所有的角色都能听见）",
        mind_voice_actions="你要说的内容。判断逻辑：1) 如果在本次对话中有人向你提问，且你在本次的speak_actions中回复了“让我想想”，则这次的mind_voice_actions只能生成这个最新的问题；2) 如果没有最新的提问，则生成你的内心独白。注意：只关注本次的提问，对于之前的提问，严禁再次回答。（只有你自己能听见）",
    )

    return f"""# 请制定你的行动计划！决定你将要做什么，并以 JSON 格式输出。

## 当前场景

{current_stage} | {current_stage_narration}

## 场景内角色

{"\n".join(actors_appearances_info)}

## 由当前场景可去往的场景

{"\n- ".join(available_home_stages) if len(available_home_stages) > 0 else "无场景可去往"}

## 输出内容

- 请根据当前场景，角色信息与你的历史，制定你的行动计划。
- 请严格遵守全名机制。
- 请严格遵守对话机制。
- 第一人称视角。

## 输出格式

### 标准示例

```json
{response_sample.model_dump_json()}
```

### 注意事项
- speak_actions/whisper_actions/announce_actions 这三种行动只能选其一
- mind_voice_actions可选。
- 严格按照‘标准示例’进行输出。"""


#######################################################################################################################################
def _compress_prompt(
    prompt: str,
) -> str:
    logger.debug(f"原始 Prompt =>\n{prompt}")
    return "# 请做出你的计划，决定你将要做什么，并以 JSON 格式输出。"


#######################################################################################################################################
@final
class HomeActorSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(PlanAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(PlanAction)

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:

        if len(entities) == 0:
            return

        # 处理角色规划请求
        request_handlers: List[ChatClient] = self._generate_request_handlers(entities)

        # 语言服务
        await ChatClient.gather_request_post(clients=request_handlers)

        # 处理角色规划请求
        for request_handler in request_handlers:
            entity2 = self._game.get_entity_by_name(request_handler.name)
            assert entity2 is not None
            self._handle_response(entity2, request_handler)

    #######################################################################################################################################
    def _handle_response(self, entity2: Entity, request_handler: ChatClient) -> None:

        try:

            response = ActorResponse.model_validate_json(
                json_format.strip_json_code_block(request_handler.response_content)
            )

            self._game.append_human_message(
                entity2, _compress_prompt(request_handler.prompt)
            )
            self._game.append_ai_message(entity2, request_handler.response_ai_messages)

            # 添加说话动作
            if len(response.speak_actions) > 0:
                entity2.replace(SpeakAction, entity2.name, response.speak_actions)

            # 添加耳语动作
            if len(response.whisper_actions) > 0:
                entity2.replace(WhisperAction, entity2.name, response.whisper_actions)

            # 添加宣布动作
            if response.announce_actions != "":
                entity2.replace(AnnounceAction, entity2.name, response.announce_actions)

            # 添加内心独白
            if response.mind_voice_actions != "":
                entity2.replace(
                    MindVoiceAction, entity2.name, response.mind_voice_actions
                )

            # 最后：如果需要可以添加传送场景。
            if response.trans_stage_name != "":
                entity2.replace(
                    TransStageAction, entity2.name, response.trans_stage_name
                )

        except Exception as e:
            logger.error(f"Exception: {e}")

    #######################################################################################################################################
    def _generate_request_handlers(
        self, actor_entities: List[Entity]
    ) -> List[ChatClient]:

        all_home_entities = self._game.get_group(
            Matcher(
                all_of=[HomeComponent],
            )
        ).entities.copy()

        request_handlers: List[ChatClient] = []

        for entity in actor_entities:

            current_stage = self._game.safe_get_stage_entity(entity)
            assert current_stage is not None

            # 找到当前场景内所有角色 & 他们的外观描述
            actors_apperances_mapping = self._game.get_stage_actor_appearances(
                current_stage
            )
            # 移除自己
            actors_apperances_mapping.pop(entity.name, None)

            # 找到当前场景可去往的家园场景
            available_home_stages = all_home_entities.copy()  # 注意这里必须 copy
            available_home_stages.discard(current_stage)

            # 生成消息
            message = _generate_prompt(
                current_stage=current_stage.name,
                current_stage_narration=current_stage.get(
                    EnvironmentComponent
                ).description,
                actors_appearance_mapping=actors_apperances_mapping,
                available_home_stages=[e.name for e in available_home_stages],
            )

            # 生成请求处理器
            request_handlers.append(
                ChatClient(
                    name=entity.name,
                    prompt=message,
                    chat_history=self._game.get_agent_chat_history(entity).chat_history,
                )
            )

        return request_handlers

    #######################################################################################################################################
