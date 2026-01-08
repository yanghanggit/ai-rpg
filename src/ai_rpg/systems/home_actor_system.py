"""家园角色行动系统模块。

该模块负责处理家园场景中角色的行动规划与执行：
1. 监听角色的 PlanAction 组件触发
2. 为角色生成包含场景、角色、可用行动的完整提示词
3. 调用 AI 服务获取角色的行动决策
4. 将 AI 响应解析并转化为具体的游戏行动组件

核心流程：
- 创建聊天客户端 -> 发送 AI 请求 -> 处理响应 -> 执行行动

主要组件：
- ActorPlanResponse: AI 返回的行动规划响应数据模型
- HomeActorSystem: 响应式处理器，处理角色行动规划的完整生命周期
- _build_full_action_prompt: 构建完整的行动规划提示词
- _build_compressed_action_prompt: 构建压缩版提示词用于历史记录
"""

from typing import Dict, Final, List, final
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
    ActorComponent,
    PlayerComponent,
    PlayerOnlyStageComponent,
)
from ..utils import extract_json_from_code_block
from ..game.tcg_game import TCGGame


#######################################################################################################################################
@final
class ActionPlanResponse(BaseModel):
    """角色行动规划响应数据模型。

    封装 AI 返回的角色行动决策，包含多种行动类型。

    Attributes:
        mind_voice_actions: 内心独白内容（仅角色自己可见）
        query_actions: 查询请求内容（用于事实性信息检索）
        speak_actions: 说话行动，键为目标角色名，值为说话内容
        whisper_actions: 耳语行动，键为目标角色名，值为耳语内容（其他人听不到）
        announce_actions: 公开宣布内容（所有人都能听到）
        trans_stage_name: 要传送到的目标场景名称（留空则不移动）
    """

    mind_voice_actions: str = ""
    query_actions: str = ""
    speak_actions: Dict[str, str] = {}
    whisper_actions: Dict[str, str] = {}
    announce_actions: str = ""
    trans_stage_name: str = ""


#######################################################################################################################################
def _build_full_action_prompt(
    current_stage: str,
    current_stage_narration: str,
    actors_appearance_mapping: Dict[str, str],
    available_home_stages: List[str],
) -> str:
    """构建完整的角色行动规划提示词。

    生成包含当前场景信息、其他角色信息、可用场景列表和行动规则的完整提示词，
    用于指导 AI 生成符合游戏规则的角色行动决策。

    Args:
        current_stage: 当前场景名称
        current_stage_narration: 当前场景的环境描述
        actors_appearance_mapping: 场景内其他角色的外观描述字典，键为角色名，值为外观描述
        available_home_stages: 可以前往的家园场景名称列表

    Returns:
        格式化的完整提示词字符串，包含场景信息、角色信息、行动规则和 JSON 输出格式要求
    """
    # 场景内角色外观描述
    actors_appearances_info = []
    for actor_name, appearance in actors_appearance_mapping.items():
        actors_appearances_info.append(f"{actor_name}: {appearance}")
    if len(actors_appearances_info) == 0:
        actors_appearances_info.append("无")

    return f"""# 指令！请根据当前场景，角色信息与你的历史制定你的行动计划！决定你将要做什么，并以 JSON 格式输出。

## 当前场景

{current_stage} | {current_stage_narration}

## 场景内角色

{"\n".join(actors_appearances_info)}

## 由当前场景可去往的场景

{"\n- ".join(available_home_stages) if len(available_home_stages) > 0 else "无场景可去往"}

## 核心规则

1. **第一人称视角**  
   所有行动和思考必须以第一人称进行。

2. **交流方式三选一**  
   说话/耳语/宣布,不可并用。

3. **事实性提问必须检索**  
   - 当有人向你提问事实性信息(地点/人物/物品/事件等)时:
     * 第一步: 填写检索词语(提取问题中的关键词)
     * 第二步: 在交流方式字段中只能填写表达正在思考的简短话语(根据角色性格和说话风格填写,不超过10字)
     * 第三步: 本回合结束,等待检索结果
   - 收到检索结果后:
     * 基于检索结果回答问题或者自行决定后续行动
     * 若检索无结果则说"我不知道"或类似表达
   
4. **检索时严格禁止**  
   - 禁止在填写检索词语的同时在交流方式里给出任何实质性答案
   - 禁止编造、推测、猜测任何未经检索的信息
   - 只能说"正在思考"类的过渡话语,不得包含对问题的回答内容

5. **信息来源限制**  
   只能使用: ①当前上下文中明确提到的信息 ②检索返回的结果。其他一律视为编造。

## 输出格式

### 标准示例

```json
{{
  "mind_voice_actions": "内心独白(仅自己可见)",
  "query_actions": "回答事实性问题前必填(地点/人物/物品/事件等具体信息)",
  "speak_actions": {{
    "角色全名": "说话内容"
  }},
  "whisper_actions": {{
    "角色全名": "耳语内容(其他人听不到)"
  }},
  "announce_actions": "公开宣布内容(所有人听到)",
  "trans_stage_name": "移动目标场景全名(不移动则留空)"
}}
```

严格遵循"标准示例"的JSON格式,字段名不可改。"""


#######################################################################################################################################
def _build_compressed_action_prompt(
    prompt: str,
) -> str:
    """构建压缩版的行动规划提示词。

    将完整提示词压缩为简短版本，用于保存到对话历史记录中以节省 token 消耗。
    压缩版本仅保留核心指令，省略详细的场景信息和规则说明。

    Args:
        prompt: 原始的完整提示词（用于日志记录）

    Returns:
        压缩后的简短提示词字符串
    """
    # logger.debug(f"原始 Prompt =>\n{prompt}")
    return "# 指令！请根据当前场景，角色信息与你的历史制定你的行动计划！决定你将要做什么，并以 JSON 格式输出。"


#######################################################################################################################################
@final
class HomeActorSystem(ReactiveProcessor):
    """家园角色行动系统。

    响应式处理器，监听并处理家园场景中角色的行动规划请求。
    当角色实体添加 PlanAction 组件时触发，为角色生成行动规划提示词，
    调用 AI 服务获取决策，并将决策转化为具体的游戏行动组件。

    工作流程：
    1. 监听 PlanAction 组件的添加事件
    2. 为每个角色创建聊天客户端，生成包含场景上下文的提示词
    3. 批量调用 AI 服务获取行动决策
    4. 解析 AI 响应并添加对应的行动组件（说话、耳语、查询、移动等）

    Attributes:
        _game: TCG 游戏实例的引用
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

        解析 AI 返回的行动规划响应，将其转化为具体的游戏行动组件并添加到角色实体上。
        同时将对话内容保存到历史记录中。

        处理的行动类型包括：
        - 内心独白（MindEvent）
        - 说话（SpeakAction）
        - 耳语（WhisperAction）
        - 宣布（AnnounceAction）
        - 查询（QueryAction）
        - 场景传送（TransStageAction）

        Args:
            actor_entity: 执行行动的角色实体
            chat_client: 包含 AI 响应的聊天客户端

        Note:
            如果解析响应失败，会记录错误日志但不会中断流程
        """
        try:

            # 验证响应
            validated_response = ActionPlanResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            # 添加上下文！
            self._game.add_human_message(
                actor_entity,
                _build_compressed_action_prompt(chat_client.prompt),
                compressed_prompt=chat_client.prompt,
            )
            self._game.add_ai_message(actor_entity, chat_client.response_ai_messages)

            # 添加内心独白: 上下文！，这里做直接添加与通知处理
            if validated_response.mind_voice_actions != "":

                self._game.notify_entities(
                    set({actor_entity}),
                    MindEvent(
                        message=f"# 通知！{actor_entity.name} 内心活动: {validated_response.mind_voice_actions}",
                        actor=actor_entity.name,
                        content=validated_response.mind_voice_actions,
                    ),
                )

            # 添加说话动作
            if len(validated_response.speak_actions) > 0:
                actor_entity.replace(
                    SpeakAction, actor_entity.name, validated_response.speak_actions
                )

            # 添加耳语动作
            if len(validated_response.whisper_actions) > 0:
                actor_entity.replace(
                    WhisperAction, actor_entity.name, validated_response.whisper_actions
                )

            # 添加宣布动作
            if validated_response.announce_actions != "":
                actor_entity.replace(
                    AnnounceAction,
                    actor_entity.name,
                    validated_response.announce_actions,
                )

            # 添加查询动作
            if validated_response.query_actions != "":
                actor_entity.replace(
                    QueryAction, actor_entity.name, validated_response.query_actions
                )

            # 最后：如果需要可以添加传送场景。
            if validated_response.trans_stage_name != "":
                actor_entity.replace(
                    TransStageAction,
                    actor_entity.name,
                    validated_response.trans_stage_name,
                )

        except Exception as e:
            logger.error(f"Exception: {e}")

    #######################################################################################################################################
    def _create_actor_chat_clients(
        self, actor_entities: List[Entity]
    ) -> List[ChatClient]:
        """为角色实体创建聊天客户端。

        为每个角色生成包含场景上下文的完整提示词，并创建对应的聊天客户端用于 AI 请求。

        为每个角色收集以下信息：
        - 当前所在场景及其描述
        - 场景内其他角色的外观信息
        - 可以前往的家园场景列表
        - 角色的对话历史上下文

        Args:
            actor_entities: 需要生成行动规划的角色实体列表

        Returns:
            聊天客户端列表，每个客户端对应一个角色的 AI 请求
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
            current_stage = self._game.safe_get_stage_entity(actor_entity)
            assert current_stage is not None

            # 找到当前场景内所有角色 & 他们的外观描述
            actors_apperances_mapping = self._game.get_stage_actor_appearances(
                current_stage
            )
            # 移除自己
            actors_apperances_mapping.pop(actor_entity.name, None)

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
                    prompt=_build_full_action_prompt(
                        current_stage=current_stage.name,
                        current_stage_narration=current_stage.get(
                            EnvironmentComponent
                        ).description,
                        actors_appearance_mapping=actors_apperances_mapping,
                        available_home_stages=[e.name for e in available_home_stages],
                    ),
                    context=self._game.get_agent_context(actor_entity).context,
                )
            )

        return chat_clients

    #######################################################################################################################################
