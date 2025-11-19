from typing import Dict, List, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..chat_services.client import ChatClient
from ..entitas import Entity, Matcher, GroupEvent, ReactiveProcessor
from ..models import (
    AnnounceAction,
    EnvironmentComponent,
    QueryAction,
    SpeakAction,
    WhisperAction,
    PlanAction,
    TransStageAction,
    HomeComponent,
    MindEvent,
)
from ..utils import extract_json_from_code_block
from ..game.tcg_game import TCGGame


#######################################################################################################################################
@final
class ActorResponse(BaseModel):
    mind_voice_actions: str = ""
    query_actions: str = ""
    speak_actions: Dict[str, str] = {}
    whisper_actions: Dict[str, str] = {}
    announce_actions: str = ""
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
        mind_voice_actions="你要说的内容。内心独白（只有你自己能听见）",
        query_actions="用于深度记忆检索的关键问题。使用判断：1) 对方提出的问题在当前上下文中找不到足够信息来回答，且你认为自己的记忆中可能存储了相关信息 2) 需要回忆具体细节、数据或过往经历来提供准确答复 3) 对方明确寻求建议，需要检索相关经验。注意：如果当前上下文已有答案，或问题过于宽泛模糊，则不使用。查询应精准简短，只包含核心关键词。（只有你自己能听见，会触发记忆检索）",
        speak_actions={
            "场景内角色全名": "对单个或多个角色说话。使用场景：日常对话、回答问题、讨论事项。回答策略：1) 优先检查当前上下文（角色设定、场景信息、对话历史）是否有相关信息 2) 如果有就直接基于已知信息回答 3) 如果信息不足但应该知道，必须说'让我想想'，同时使用记忆检索，禁止在不确定的情况下直接给出答案 4) 如果确实不在知识范围内就说'我不知道'。严禁编造上下文中不存在的角色名、地点名、道具名等游戏实体。如果使用了记忆检索，本次回复只能是'让我想想'。避免对同一问题重复相同回复。禁止复述其他角色的话。（场景内其他角色会听见）",
        },
        whisper_actions={
            "场景内角色全名": "对特定角色私密交流。使用场景：1) 分享不想让其他人知道的私密信息 2) 提醒队友注意某事但不想公开 3) 商讨需要保密的计划或策略 4) 表达只想让特定对象知道的个人情感。与说话的区别：耳语是一对一的隐私对话，其他角色听不到。遵守相同的回答策略和禁止编造规则。（只有你和目标角色能听见）",
        },
        announce_actions="向所有人宣布。使用场景：1) 发布重要通知或警告 2) 分享需要所有人都知道的关键信息 3) 宣告决定或计划 4) 紧急情况下的呼救或警报。与说话的区别：宣布是向场景内所有角色广播，用于需要公开传达的重要事项。遵守相同的禁止编造规则。（所有角色都能听见）",
        trans_stage_name="你要前往的场景全名。如果不想转换场景就留空。",
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
- 请严格遵守沉浸叙事原则：禁止编造上下文中不存在的游戏实体（角色、地点、道具等）。
- 请严格遵守全名精确匹配机制。
- 第一人称视角。

## 输出格式

### 标准示例

```json
{response_sample.model_dump_json()}
```

### 注意事项
- 说话/耳语/宣布 这三种交流行动只能选其一。根据沟通意图选择：日常对话用说话，私密交流用耳语，重要通知用宣布。
- 记忆检索机制：当你需要查询记忆时，本轮的说话内容必须是'让我想想'，不能同时给出具体答案。下一轮才会基于检索结果回答。
- 内心独白可选。用于表达角色的内心想法、分析、计划等只有自己知道的信息。
- 场景转换可选。如果你想前往其他场景，填写可去往场景列表中的场景全名。留空表示不转换场景。
- 严格按照'标准示例'中的JSON格式进行输出。"""


#######################################################################################################################################
def _compress_prompt(
    prompt: str,
) -> str:
    logger.debug(f"原始 Prompt =>\n{prompt}")
    return "# 请做出你的计划，决定你将要做什么，并以 JSON 格式输出。"


#######################################################################################################################################
@final
class HomeActorSystem(ReactiveProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: TCGGame = game_context

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
                extract_json_from_code_block(request_handler.response_content)
            )

            self._game.append_human_message(
                entity2, _compress_prompt(request_handler.prompt)
            )
            self._game.append_ai_message(entity2, request_handler.response_ai_messages)

            # 添加内心独白: 上下文！
            if response.mind_voice_actions != "":

                self._game.notify_entities(
                    set({entity2}),
                    MindEvent(
                        message=f"{entity2.name} : {response.mind_voice_actions}",
                        actor=entity2.name,
                        content=response.mind_voice_actions,
                    ),
                )

            # 添加说话动作
            if len(response.speak_actions) > 0:
                entity2.replace(SpeakAction, entity2.name, response.speak_actions)

            # 添加耳语动作
            if len(response.whisper_actions) > 0:
                entity2.replace(WhisperAction, entity2.name, response.whisper_actions)

            # 添加宣布动作
            if response.announce_actions != "":
                entity2.replace(AnnounceAction, entity2.name, response.announce_actions)

            # 添加查询动作
            if response.query_actions != "":
                entity2.replace(QueryAction, entity2.name, response.query_actions)

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
                    context=self._game.get_agent_context(entity).context,
                )
            )

        return request_handlers

    #######################################################################################################################################
