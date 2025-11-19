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
        mind_voice_actions="内心独白(仅自己可见)",
        query_actions="回答事实性问题前必填(地点/人物/物品/事件等具体信息)。填写后下轮必答,禁止再检索。",
        speak_actions={
            "角色全名": "说话内容。检索时必须填'让我想想',不得有其他内容。",
        },
        whisper_actions={
            "角色全名": "耳语内容(其他人听不到)",
        },
        announce_actions="公开宣布内容(所有人听到)。",
        trans_stage_name="移动目标场景全名(不移动则留空)",
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
- 严格遵守沉浸叙事原则。
- 严格遵守全名精确匹配机制。
- 第一人称视角。

## 输出格式

### 标准示例

```json
{response_sample.model_dump_json()}
```

### 核心规则
1. 交流方式三选一:说话/耳语/宣布,不可并用。
2. 遇到事实性提问(询问具体的地点/人物/物品/历史等)必须检索:
   ① 填query_actions(用问题关键词)→仅说'让我想想'→等待结果
   ② 收到结果→立即基于结果回答→禁止再填query_actions
   ③ 结果不足→说'我不知道'→禁止编造或二次检索
3. 禁止编造上下文不存在的实体。不在上下文且未检索的信息一律不得使用。
4. 严格JSON格式,字段名不可改。"""


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
