from typing import Dict, Final, List, Set, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..chat_client.client import ChatClient
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from ..models import (
    StageDescriptionComponent,
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

{"\n\n".join(actor_appearances_on_stage_info)}

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
@final
class StageDescriptionSystem(ExecuteProcessor):
    """场景描述生成系统。

    为 StageComponent 实体生成环境描述文本，结果写入 StageDescriptionComponent。
    跳过已有描述的场景，对待处理场景并行发起 AI 请求。

    Attributes:
        _game: TCG游戏上下文
    """

    def __init__(self, game: TCGGame) -> None:
        self._game: Final[TCGGame] = game

    #######################################################################################################################################
    @override
    async def execute(self) -> None:

        # 获取所有可以进行场景规划的场景实体
        stage_entities = self._game.get_group(
            Matcher(all_of=[StageComponent])
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
            assert stage_entity is not None, f"未找到名称为 {chat_client.name} 的实体"

            self._process_stage_description_response(stage_entity, chat_client)

    #######################################################################################################################################
    def _prepare_stage_description_requests(
        self, stage_entities: Set[Entity]
    ) -> List[ChatClient]:
        """为 StageDescriptionComponent.narrative 为空的场景构建 ChatClient 请求列表。"""
        chat_clients: List[ChatClient] = []

        for stage_entity in stage_entities:

            environment_comp = stage_entity.get(StageDescriptionComponent)
            if environment_comp.narrative != "":
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
        """解析 AI 响应，更新场景实体的 StageDescriptionComponent 并存入对话历史。"""
        try:

            format_response = StageDescriptionResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            self._game.add_human_message(stage_entity, chat_client.prompt)
            self._game.add_ai_message(stage_entity, chat_client.response_ai_messages)

            # 更新环境描写
            if format_response.description != "":
                stage_entity.replace(
                    StageDescriptionComponent,
                    stage_entity.name,
                    format_response.description,
                )

        except Exception as e:
            logger.error(f"Exception: {e}")


#######################################################################################################################################
