from typing import Dict, Final, List, Set, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..chat_client.client import ChatClient
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from ..models import (
    EnvironmentComponent,
    HomeComponent,
    StageComponent,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class StageDescriptionResponse(BaseModel):
    description: str = ""


#######################################################################################################################################
def _build_stage_description_prompt(
    actor_appearances_on_stage: Dict[str, str],
) -> str:
    """构建场景描述的提示词。

    根据场景内角色的外貌信息，生成用于请求AI生成场景环境描述的提示词。
    该提示词要求AI仅描述场景环境，不包含角色信息。

    Args:
        actor_appearances_on_stage: 角色名称到外貌描述的映射字典

    Returns:
        格式化的提示词字符串，包含角色列表和输出格式说明
    """
    actor_appearances_on_stage_info = []
    for actor_name, appearance in actor_appearances_on_stage.items():
        actor_appearances_on_stage_info.append(f"{actor_name}: {appearance}")
    if len(actor_appearances_on_stage_info) == 0:
        actor_appearances_on_stage_info.append("无")

    return f"""# 指令！请你输出你的场景描述。并以 JSON 格式输出。

## 场景内角色

{"\n".join(actor_appearances_on_stage_info)}

## 输出格式(JSON)

```json
{{
  "description": "场景内的环境描述"
}}
```

**约束规则**：

- 场景内的环境描述，不要包含任何角色信息
- 所有输出必须为第三人称视角
- 严格按上述JSON格式输出"""


#######################################################################################################################################
def _compress_prompt_for_history(prompt: str) -> str:
    """压缩提示词以便保存到对话历史。

    将完整的场景描述提示词压缩成简短版本，减少存储在消息历史中的token消耗。
    原始提示词可能包含数百字符，压缩后仅保留核心指令。

    Args:
        prompt: 原始完整提示词

    Returns:
        压缩后的简短提示词字符串
    """
    logger.debug(f"准备压缩原始提示词 {prompt[:100]}...")
    return "# 指令！请你输出你的场景描述。并以 JSON 格式输出。"


#######################################################################################################################################
@final
class HomeStageDescriptionSystem(ExecuteProcessor):
    """家园场景描述生成系统。

    负责为家园场景实体生成环境描述文本。系统会自动筛选出尚未生成环境描述的场景，
    通过AI并行生成描述内容，并将结果保存到场景实体的环境描述组件中。

    工作流程：
        1. 查询所有家园场景实体（包含 StageComponent 和 HomeComponent）
        2. 筛选出环境描述为空的场景
        3. 为每个场景构建包含场景内角色信息的提示词
        4. 并行发送请求到AI服务生成场景描述
        5. 解析响应并更新场景实体的 EnvironmentComponent
        6. 将压缩后的提示词和AI响应保存到对话历史

    特性：
        - 智能跳过已有描述的场景，避免重复生成
        - 并行请求提升效率
        - 提示词压缩节省对话历史存储空间
        - 场景描述仅包含环境信息，不包含角色行为

    Attributes:
        _game: TCG游戏上下文，用于访问实体和游戏状态
    """

    def __init__(self, game_context: TCGGame) -> None:
        self._game: Final[TCGGame] = game_context

    #######################################################################################################################################
    @override
    async def execute(self) -> None:

        # 获取所有可以进行场景规划的场景实体
        stage_entities = self._game.get_group(
            Matcher(all_of=[StageComponent, HomeComponent])
        ).entities.copy()

        # 准备场景描述请求
        chat_clients: List[ChatClient] = self._prepare_stage_description_requests(
            stage_entities
        )

        # 并行发送请求
        await ChatClient.batch_chat(clients=chat_clients)

        # 处理响应
        for chat_client in chat_clients:

            stage_entity = self._game.get_entity_by_name(chat_client.name)
            assert stage_entity is not None

            self._process_stage_description_response(stage_entity, chat_client)

    #######################################################################################################################################
    def _prepare_stage_description_requests(
        self, stage_entities: Set[Entity]
    ) -> List[ChatClient]:
        """为需要生成环境描述的场景准备请求。

        遍历所有家园场景实体，筛选出尚未生成环境描述的场景，
        为每个场景构建ChatClient请求处理器。已有环境描述的场景会被跳过。

        Args:
            stage_entities: 所有家园场景实体的集合

        Returns:
            ChatClient请求处理器列表，每个处理器对应一个待生成描述的场景
        """
        chat_clients: List[ChatClient] = []

        for stage_entity in stage_entities:

            environment_comp = stage_entity.get(EnvironmentComponent)
            if environment_comp.description != "":
                # 如果环境描述不为空，跳过
                logger.debug(
                    f"跳过场景 {stage_entity.name} 的规划请求，因其环境描述不为空"
                )
                continue

            # 获取场景内角色的外貌信息
            actor_appearances_on_stage: Dict[str, str] = (
                self._game.get_actor_appearances_on_stage(stage_entity)
            )

            # 生成请求处理器
            chat_clients.append(
                ChatClient(
                    name=stage_entity.name,
                    prompt=_build_stage_description_prompt(actor_appearances_on_stage),
                    context=self._game.get_agent_context(stage_entity).context,
                )
            )
        return chat_clients

    #######################################################################################################################################
    def _process_stage_description_response(
        self, stage_entity: Entity, chat_client: ChatClient
    ) -> None:
        """处理场景描述生成的响应结果。

        解析AI返回的场景描述JSON，将压缩后的提示词和AI响应保存到对话历史，
        并更新场景实体的环境描述组件。

        Args:
            stage_entity: 场景实体
            chat_client: 包含请求和响应内容的ChatClient处理器

        Raises:
            Exception: 当响应解析失败时记录错误日志
        """
        try:

            format_response = StageDescriptionResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            self._game.add_human_message(
                stage_entity, _compress_prompt_for_history(chat_client.prompt)
            )
            self._game.add_ai_message(stage_entity, chat_client.response_ai_messages)

            # 更新环境描写
            if format_response.description != "":
                stage_entity.replace(
                    EnvironmentComponent,
                    stage_entity.name,
                    format_response.description,
                )

        except Exception as e:
            logger.error(f"Exception: {e}")


#######################################################################################################################################
