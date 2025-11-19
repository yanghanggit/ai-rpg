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
from ..utils import json_format
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
        mind_voice_actions="你的内心想法。只有你自己能听见的独白。禁止在内心独白中编造不存在的游戏实体。",
        query_actions="记忆检索关键词,留空表示不检索。当对方询问你应该知道但上下文中没有的具体信息时使用(如专有名词、历史事件、过往经历、技术细节等)。特别注意:遇到'最...的'、'哪里有'、'谁有'等需要确切信息的问题时,如果上下文没有明确答案,必须使用检索而非猜测。",
        speak_actions={
            "场景内角色全名": "对话内容。回答策略:1)如果上下文有答案就直接回答 2)如果问题需要你回忆过去的具体信息,说'让我想想'并填写query_actions,不能继续回答 3)如果确实不知道就说'我不知道'。禁止编造不存在的游戏实体。禁止猜测答案。",
        },
        whisper_actions={
            "场景内角色全名": "私密对话内容。一对一交流,其他角色听不到。遵守相同的回答策略。",
        },
        announce_actions="向所有人宣布的内容。重要通知或公开声明。",
        trans_stage_name="要前往的场景全名,留空表示不移动。",
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
- 说话/耳语/宣布 这三种交流行动只能选其一。根据沟通意图选择:日常对话用说话,私密交流用耳语,重要通知用宣布。
- 【记忆检索机制】当需要回答对方的具体问题,但当前上下文中没有答案时,应使用query_actions检索记忆。
- 【关键规则】如果填写了query_actions(不为空),你的对话内容(说话/耳语/宣布)必须是且只能是'让我想想'四个字,不能有任何额外内容。下一轮会基于检索结果回答。
- 【禁止行为】严禁在使用query_actions的同时继续回答问题。不能说"让我想想...啊!我想起来了..."或类似表述。
- 【检索后处理】如果上一轮使用了query_actions并收到了检索结果,本轮必须基于检索结果回答,严禁再次检索相同问题,严禁编造检索结果中没有的实体。
- 【何时检索】对方询问:专有名词、历史事件、过往经历、技术数据、角色关系等你应该知道但上下文没有的信息。特别是"最...的是哪里/是谁"、"哪里有..."、"在哪能找到..."等需要确切信息的问题,如果上下文没有明确答案,必须检索而非猜测。
- 【何时不检索】日常问候、情感表达、基于当前场景的简单对话、上下文已有答案的问题、已经检索过的问题。
- 【严禁猜测】遇到需要确切信息的问题时,如果上下文中没有答案且你不确定,应该检索或说'我不知道',绝对不能凭感觉猜测或编造答案。
- 场景转换可选,根据实际情况填写或留空。
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
                json_format.strip_json_code_block(request_handler.response_content)
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
