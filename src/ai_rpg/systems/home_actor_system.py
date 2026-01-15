from typing import Dict, Final, List, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..chat_services import ChatClient
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
    ActorComponent,
    PlayerComponent,
    PlayerOnlyStageComponent,
)
from ..utils import extract_json_from_code_block
from ..game import TCGGame


#######################################################################################################################################
def _format_mind_notification(actor_name: str, mind_content: str) -> str:
    """格式化内心活动通知消息。

    Args:
        actor_name: 角色名称
        mind_content: 内心活动内容

    Returns:
        格式化后的通知消息
    """
    return f"# 通知！{actor_name} 内心活动: {mind_content}"


#######################################################################################################################################
@final
class ActionPlanResponse(BaseModel):
    """角色行动规划响应数据模型。

    用于解析和验证 AI 返回的角色行动决策 JSON 数据，
    确保响应结构符合预期格式并包含所有必要的行动信息。

    Attributes:
        mind: 内心独白
        query: 数据库检索关键词
        speak: 说话行动（目标角色名 -> 内容）
        whisper: 耳语行动（目标角色名 -> 内容）
        announce: 公开宣布
        trans_stage: 移动目标场景名
    """

    mind: str = ""
    query: str = ""
    speak: Dict[str, str] = {}
    whisper: Dict[str, str] = {}
    announce: str = ""
    trans_stage: str = ""


#######################################################################################################################################
def _build_action_planning_prompt(
    current_stage: str,
    current_stage_narration: str,
    other_actors_appearances: Dict[str, str],
    available_home_stages: List[str],
) -> str:
    """构建角色行动规划提示词。

    Args:
        current_stage: 场景名称
        current_stage_narration: 场景环境描述
        other_actors_appearances: 其他角色的外观（角色名 -> 外观）
        available_home_stages: 可前往的场景列表

    Returns:
        完整的行动规划提示词
    """
    # 场景内角色外观描述
    other_actors_appearance_info = []
    for actor_name, appearance in other_actors_appearances.items():
        other_actors_appearance_info.append(f"{actor_name}: {appearance}")
    if len(other_actors_appearance_info) == 0:
        other_actors_appearance_info.append("无")

    return f"""# 指令! 决定你要做什么，以JSON格式输出。

## 场景信息

{current_stage} | {current_stage_narration}

可移动至: {", ".join(available_home_stages) if len(available_home_stages) > 0 else "无"}

## 其他角色

{"\n".join(other_actors_appearance_info)}

## 核心规则

1. **每回合行动结构**

```
每回合结构：
├─ mind [必填] - 内心独白/思考
└─ 主要行动 [三选一，严格互斥]
   ├─ A. query - 检索思考（向内）
   ├─ B. 交流行动 - 向外发送信息（三选一）
   │   ├─ speak
   │   ├─ whisper
   │   └─ announce
   └─ C. trans_stage - 移动场景
```

2. **第一人称视角**  
   所有行动和思考必须以第一人称进行。

3. **对内检索** (`query`)
   - System prompt是信息目录，需要详细信息时用query向数据库检索，结果会添加到context

4. **对外交流** - 三种方式的区别
   - `speak`：对当前场景内指定角色说话（公开，场景内所有人都能听到）
   - `whisper`：对指定角色耳语（私密，只有你和对方知道）
   - `announce`：向所有家园场景发布公告（广播，所有家园场景的角色都能听到）
   
   **约束**：只能使用context中已有的信息

5. **场景移动** (`trans_stage`)
   - 填写目标场景全名（从"可移动至"列表选择）

## 输出格式(JSON)

```json
{{
  "mind": "内心独白",
  "query": "检索关键词",
  "speak": {{
    "角色全名": "说话内容"
  }},
  "whisper": {{
    "角色全名": "耳语内容"
  }},
  "announce": "公开宣布内容",
  "trans_stage": "移动目标场景全名"
}}
```

**约束规则**：

- 严格按上述JSON格式输出你的行动决策
- 所有字段名不可更改"""


#######################################################################################################################################
def _build_action_planning_prompt_test(
    current_stage: str,
    current_stage_narration: str,
    other_actors_appearances: Dict[str, str],
    available_home_stages: List[str],  # 这个暂时不用，因为关闭了移动！
) -> str:
    """构建角色行动规划提示词（测试版本，不含announce和trans_stage）。

    Args:
        current_stage: 场景名称
        current_stage_narration: 场景环境描述
        other_actors_appearances: 其他角色的外观（角色名 -> 外观）

    Returns:
        完整的行动规划提示词
    """
    # 场景内角色外观描述
    other_actors_appearance_info = []
    for actor_name, appearance in other_actors_appearances.items():
        other_actors_appearance_info.append(f"{actor_name}: {appearance}")
    if len(other_actors_appearance_info) == 0:
        other_actors_appearance_info.append("无")

    return f"""# 指令! 决定你要做什么，以JSON格式输出。

## 场景信息

{current_stage} | {current_stage_narration}

## 其他角色

{"\n".join(other_actors_appearance_info)}

## 核心规则

1. **每回合行动结构**

```
每回合结构：
├─ mind [必填] - 内心独白/思考
└─ 主要行动 [二选一，严格互斥]
   ├─ A. query - 检索思考（向内）
   └─ B. 交流行动 - 向外发送信息（二选一）
       ├─ speak
       └─ whisper
```

2. **第一人称视角**  
   所有行动和思考必须以第一人称进行。

3. **对内检索** (`query`)
   - System prompt是信息目录，需要详细信息时用query向数据库检索，结果会添加到context

4. **对外交流** - 两种方式的区别
   - `speak`：对当前场景内指定角色说话（公开，场景内所有人都能听到）
   - `whisper`：对指定角色耳语（私密，只有你和对方知道）
   
   **约束**：只能使用context中已有的信息

## 输出格式(JSON)

```json
{{
  "mind": "内心独白",
  "query": "检索关键词",
  "speak": {{
    "角色全名": "说话内容"
  }},
  "whisper": {{
    "角色全名": "耳语内容"
  }}
}}
```

**约束规则**：

- 严格按上述JSON格式输出你的行动决策
- 所有字段名不可更改"""


#######################################################################################################################################
def _build_action_prompt_summary(
    prompt: str,
) -> str:
    """构建压缩版提示词用于历史记录。

    Args:
        prompt: 原始完整提示词

    Returns:
        压缩后的简短提示词
    """
    logger.debug(f"原始 Prompt =>\n{prompt[:100]}")
    return "# 指令! 决定你要做什么，以JSON格式输出。"


#######################################################################################################################################
@final
class HomeActorSystem(ReactiveProcessor):
    """家园角色行动系统。

    响应式处理器，监听 PlanAction 组件触发，生成行动规划提示词，
    调用 AI 服务获取决策，并转化为游戏行动组件。

    Attributes:
        _game: 游戏实例引用
    """

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: Final[TCGGame] = game_context

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(PlanAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(PlanAction) and entity.has(ActorComponent)

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:

        # 处理角色规划请求
        chat_clients: List[ChatClient] = self._create_actor_chat_clients(entities)

        # 语言服务
        await ChatClient.gather_request_post(clients=chat_clients)

        # 处理角色规划请求
        for chat_client in chat_clients:
            response_entity = self._game.get_entity_by_name(chat_client.name)
            assert (
                response_entity is not None
            ), f"Cannot find entity by name: {chat_client.name}"
            self._execute_actor_actions(response_entity, chat_client)

    #######################################################################################################################################
    def _execute_actor_actions(
        self, actor_entity: Entity, chat_client: ChatClient
    ) -> None:
        """执行角色的行动决策。

        解析 AI 响应并转化为游戏行动组件，保存对话历史。

        Args:
            actor_entity: 角色实体
            chat_client: 聊天客户端（包含 AI 响应）
        """
        try:

            # 验证响应
            validated_response = ActionPlanResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            # 添加上下文！
            self._game.add_human_message(
                actor_entity,
                _build_action_prompt_summary(chat_client.prompt),
                compressed_prompt=chat_client.prompt,
            )
            self._game.add_ai_message(actor_entity, chat_client.response_ai_messages)

            # 添加内心独白: 上下文！，这里做直接添加与通知处理
            if validated_response.mind != "":

                self._game.notify_entities(
                    set({actor_entity}),
                    MindEvent(
                        message=_format_mind_notification(
                            actor_entity.name, validated_response.mind
                        ),
                        actor=actor_entity.name,
                        content=validated_response.mind,
                    ),
                )

            # 添加说话动作
            if len(validated_response.speak) > 0:
                actor_entity.replace(
                    SpeakAction, actor_entity.name, validated_response.speak
                )

            # 添加耳语动作
            if len(validated_response.whisper) > 0:
                actor_entity.replace(
                    WhisperAction, actor_entity.name, validated_response.whisper
                )

            # 添加宣布动作
            if validated_response.announce != "":
                actor_entity.replace(
                    AnnounceAction,
                    actor_entity.name,
                    validated_response.announce,
                )

            # 添加查询动作
            if validated_response.query != "":
                actor_entity.replace(
                    QueryAction, actor_entity.name, validated_response.query
                )

            # 最后：如果需要可以添加传送场景。
            if validated_response.trans_stage != "":
                actor_entity.replace(
                    TransStageAction,
                    actor_entity.name,
                    validated_response.trans_stage,
                )

        except Exception as e:
            logger.error(f"Exception: {e}")

    #######################################################################################################################################
    def _create_actor_chat_clients(
        self, actor_entities: List[Entity]
    ) -> List[ChatClient]:
        """为角色创建聊天客户端。

        收集场景上下文并生成提示词，创建聊天客户端。

        Args:
            actor_entities: 角色实体列表

        Returns:
            聊天客户端列表
        """
        # 找到所有家园场景实体
        home_stage_entities = self._game.get_group(
            Matcher(
                all_of=[HomeComponent],
            )
        ).entities.copy()

        chat_clients: List[ChatClient] = []

        for actor_entity in actor_entities:

            # 找到当前场景
            current_stage = self._game.resolve_stage_entity(actor_entity)
            assert current_stage is not None

            # 找到当前场景内所有角色 & 他们的外观描述
            other_actors_appearances = self._game.get_actor_appearances_on_stage(
                current_stage
            )
            # 移除自己
            other_actors_appearances.pop(actor_entity.name, None)

            # 找到当前场景可去往的家园场景,这样能节省计算量。
            available_home_stages = home_stage_entities.copy()  # 注意这里必须 copy
            available_home_stages.discard(current_stage)

            # 如果当前角色不是玩家，过滤掉仅玩家可进入的场景
            if not actor_entity.has(PlayerComponent):
                available_home_stages = {
                    stage
                    for stage in available_home_stages
                    if not stage.has(PlayerOnlyStageComponent)
                }

            # 生成请求处理器
            chat_clients.append(
                ChatClient(
                    name=actor_entity.name,
                    prompt=_build_action_planning_prompt_test(
                        current_stage=current_stage.name,
                        current_stage_narration=current_stage.get(
                            EnvironmentComponent
                        ).description,
                        other_actors_appearances=other_actors_appearances,
                        available_home_stages=[e.name for e in available_home_stages],
                    ),
                    context=self._game.get_agent_context(actor_entity).context,
                )
            )

        return chat_clients

    #######################################################################################################################################
