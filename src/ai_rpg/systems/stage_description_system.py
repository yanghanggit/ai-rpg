from typing import Dict, Final, List, final
from ..models.messages import HumanMessage
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.dbg_game import DBGGame
from ..game.rpg_actor_appearances import get_actor_appearances_in_stage
from ..models import (
    StageDescriptionComponent,
    StageComponent,
)
from ..utils import (
    extract_json_from_code_block,
)


#######################################################################################################################################
@final
class StageDescriptionResponse(BaseModel):
    """场景描述系统的 AI 响应格式。"""

    description: str = ""


#######################################################################################################################################
def _build_compressed_stage_description_prompt(
    actor_appearances_in_stage: Dict[str, str],
) -> str:
    """生成压缩版场景描述提示词（仅角色外观动态感知，省略静态输出格式与约束规则）"""

    actor_appearances_in_stage_info = []
    for actor_name, appearance in actor_appearances_in_stage.items():
        actor_appearances_in_stage_info.append(f"{actor_name}: {appearance}")

    if len(actor_appearances_in_stage_info) == 0:
        actor_appearances_in_stage_info.append("无")

    return f"""# 请你输出你的场景描述。并以 JSON 格式输出。

## 场景内角色外观（用于推断环境影响）

以下角色的外观可能对场景环境产生间接影响，请据此推断当前环境状态。

{"\n\n".join(actor_appearances_in_stage_info)}"""


#######################################################################################################################################
def _build_stage_description_prompt(
    actor_appearances_in_stage: Dict[str, str],
) -> str:
    """为场景描述请求构建 prompt。"""

    # 构建角色外观信息列表，若无角色则注明“无”以避免 AI 误以为输入遗漏导致解析错误
    actor_appearances_in_stage_info = []
    for actor_name, appearance in actor_appearances_in_stage.items():
        actor_appearances_in_stage_info.append(f"{actor_name}: {appearance}")

    # 若场景内无角色，则明确告知 AI 以避免其误以为是输入遗漏导致的解析错误
    if len(actor_appearances_in_stage_info) == 0:
        actor_appearances_in_stage_info.append("无")

    return f"""# 请你输出你的场景描述。并以 JSON 格式输出。

## 场景内角色外观（用于推断环境影响）

以下角色的外观可能对场景环境产生间接影响，请据此推断当前环境状态。

{"\n\n".join(actor_appearances_in_stage_info)}

## 输出格式(JSON)

```json
{{
  "description": "场景内的环境描述"
}}
```

**约束规则**：

- 若角色外观会对环境产生直接影响（例如：持火把者照亮黑暗空间、发光生物映亮洞壁），须将该**环境影响效果**纳入场景描述
- 无论角色是否对环境产生影响，最终描述中均**不得提及**任何角色本身（不得出现角色名称、角色形态或角色行为）
- 所有输出必须为第三人称视角
- 严格按上述JSON格式输出"""


#######################################################################################################################################
@final
class StageDescriptionSystem(ExecuteProcessor):
    """为场景实体生成环境描述，写入 StageDescriptionComponent.narrative。"""

    def __init__(
        self,
        game: DBGGame,
        use_compressed_prompt: bool = True,
    ) -> None:
        self._game: Final[DBGGame] = game
        self._use_compressed_prompt: Final[bool] = use_compressed_prompt

    #######################################################################################################################################
    @override
    async def execute(self) -> None:

        # 获取所有场景实体（StageComponent）且尚未生成环境描述（StageDescriptionComponent）的实体
        stage_entities = self._game.get_group(
            Matcher(all_of=[StageComponent], none_of=[StageDescriptionComponent])
        ).entities.copy()

        # 若没有需要生成环境描述的场景实体，则直接返回
        chat_clients: List[DeepSeekClient] = [
            self._build_client(stage_entity) for stage_entity in stage_entities
        ]

        # 批量发送请求给 AI，等待所有响应完成
        await DeepSeekClient.batch_chat(clients=chat_clients)

        # 处理每个场景实体的 AI 响应，更新 StageDescriptionComponent 并存入对话历史
        for chat_client in chat_clients:
            self._process_stage_description_response(
                chat_client,
            )

    #######################################################################################################################################
    def _build_client(self, stage_entity: Entity) -> DeepSeekClient:
        """为场景实体构建 DeepSeekClient。"""

        actor_appearances: Dict[str, str] = get_actor_appearances_in_stage(
            self._game, stage_entity
        )

        return DeepSeekClient(
            name=stage_entity.name,
            prompt=_build_stage_description_prompt(actor_appearances),
            compressed_prompt=(
                _build_compressed_stage_description_prompt(actor_appearances)
                if self._use_compressed_prompt
                else None
            ),
            context=self._game.get_agent_context(stage_entity).context,
        )

    #######################################################################################################################################
    def _process_stage_description_response(
        self,
        chat_client: DeepSeekClient,
    ) -> bool:
        """解析 AI 响应，更新 StageDescriptionComponent 并存入对话历史。"""

        # 如果 AI 响应为空，则记录警告并返回 False。
        if chat_client.response_ai_message is None:
            logger.warning(
                f"StageDescriptionSystem: AI 响应为空，name={chat_client.name}"
            )
            return False

        stage_entity = self._game.get_entity_by_name(chat_client.name)
        assert (
            stage_entity is not None
        ), f"stage_entity is None, name={chat_client.name}"

        # 尝试解析 AI 响应的 JSON 内容，构建 StageDescriptionResponse 对象。
        try:
            format_response = StageDescriptionResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )
        except Exception as e:
            logger.error(f"Exception: {e}")
            return False

        # 添加上下文。
        if self._use_compressed_prompt:

            # 使用压缩 prompt 加入上下文。
            self._game.add_human_message(
                stage_entity,
                HumanMessage(
                    content=chat_client.compressed_prompt,
                    stage_description_full_prompt=chat_client.prompt,
                ),
            )
        else:

            # 直接使用完整 prompt 加入上下文。
            self._game.add_human_message(
                stage_entity, HumanMessage(content=chat_client.prompt)
            )

        # 添加上下文。
        self._game.add_ai_message(stage_entity, chat_client.response_ai_message)

        # 更新环境描写
        stage_entity.replace(
            StageDescriptionComponent,
            stage_entity.name,
            format_response.description,
        )

        return True


#######################################################################################################################################
