from typing import Dict, List, Set, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..chat_services.client import ChatClient
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
class StageEnvironmentResponse(BaseModel):
    description: str = ""


#######################################################################################################################################
def _generate_prompt(
    stage_actor_appearances: Dict[str, str],
) -> str:

    stage_actor_appearances_info = []
    for actor_name, appearance in stage_actor_appearances.items():
        stage_actor_appearances_info.append(f"{actor_name}: {appearance}")
    if len(stage_actor_appearances_info) == 0:
        stage_actor_appearances_info.append("无")

    response_example = StageEnvironmentResponse(description="场景内的环境描述")

    return f"""# 请你输出你的场景描述

## 场景内角色

{"\n".join(stage_actor_appearances_info)}

## 输出内容-场景描述

- 场景内的环境描述，不要包含任何角色信息。
- 所有输出必须为第三人称视角。

### 输出格式(JSON)

```json
{response_example.model_dump_json()}
```
"""


#######################################################################################################################################
def _compress_prompt(prompt: str) -> str:
    logger.debug(f"准备压缩原始提示词 {prompt}")
    return "# 请你输出你的场景描述。并以 JSON 格式输出。"


#######################################################################################################################################
@final
class HomeStageSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    #######################################################################################################################################
    @override
    async def execute(self) -> None:

        # 获取所有可以进行场景规划的场景实体
        stage_entities = self._game.get_group(
            Matcher(all_of=[StageComponent, HomeComponent])
        ).entities.copy()

        # 生成请求处理器
        request_handlers: List[ChatClient] = self._generate_request_handlers(
            stage_entities
        )

        # 并行发送请求
        await ChatClient.gather_request_post(clients=request_handlers)

        # 处理响应
        for request_handler in request_handlers:

            entity2 = self._game.get_entity_by_name(request_handler.name)
            assert entity2 is not None

            self._handle_response(entity2, request_handler)

    #######################################################################################################################################
    def _generate_request_handlers(
        self, stage_entities: Set[Entity]
    ) -> List[ChatClient]:

        request_handlers: List[ChatClient] = []

        for stage_entity in stage_entities:

            environment_component = stage_entity.get(EnvironmentComponent)
            if environment_component.description != "":
                # 如果环境描述不为空，跳过
                logger.debug(
                    f"跳过场景 {stage_entity.name} 的规划请求，因其环境描述不为空"
                )
                continue

            # 获取场景内角色的外貌信息
            stage_actor_appearances: Dict[str, str] = (
                self._game.get_stage_actor_appearances(stage_entity)
            )

            # 生成提示信息
            message = _generate_prompt(stage_actor_appearances)

            # 生成请求处理器
            request_handlers.append(
                ChatClient(
                    name=stage_entity.name,
                    prompt=message,
                    context=self._game.get_agent_context(stage_entity).context,
                )
            )
        return request_handlers

    #######################################################################################################################################
    def _handle_response(self, entity2: Entity, request_handler: ChatClient) -> None:

        try:

            format_response = StageEnvironmentResponse.model_validate_json(
                extract_json_from_code_block(request_handler.response_content)
            )

            self._game.append_human_message(
                entity2, _compress_prompt(request_handler.prompt)
            )
            self._game.append_ai_message(entity2, request_handler.response_ai_messages)

            # 更新环境描写
            if format_response.description != "":
                entity2.replace(
                    EnvironmentComponent,
                    entity2.name,
                    format_response.description,
                )

        except Exception as e:
            logger.error(f"Exception: {e}")


#######################################################################################################################################
