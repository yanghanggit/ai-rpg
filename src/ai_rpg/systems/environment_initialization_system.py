from typing import Dict, Final, List, final

from loguru import logger
from overrides import override

from ..deepseek import DeepSeekClient, batch_chat
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.dbg_game import DBGGame
from ..game.rpg_actor_appearances import get_actor_appearances_in_stage
from ..models import (
    EnvironmentComponent,
    StageComponent,
)
from ..models.messages import HumanMessage
from ..utils import (
    prompt_builder,
)


#######################################################################################################################################
@prompt_builder
def _build_environment_prompt(
    actor_appearances_in_stage: Dict[str, str],
) -> str:
    """为环境叙事请求构建 prompt。"""

    # 构建角色外观信息列表，若无角色则注明“无”以避免 AI 误以为输入遗漏导致解析错误
    actor_appearances_in_stage_info = []
    for actor_name, appearance in actor_appearances_in_stage.items():
        actor_appearances_in_stage_info.append(f"{actor_name}: {appearance}")

    # 若场景内无角色，则明确告知 AI 以避免其误以为是输入遗漏导致的解析错误
    if len(actor_appearances_in_stage_info) == 0:
        actor_appearances_in_stage_info.append("无")

    return f"""# 请你输出你的环境描述。

## 场景内角色外观（用于推断环境影响）

以下角色的外观可能对场景环境产生间接影响，请据此推断当前环境状态。

{"\n\n".join(actor_appearances_in_stage_info)}

**约束规则**：

- 若角色外观会对环境产生直接影响（例如：持火把者照亮黑暗空间、发光生物映亮洞壁），须将该**环境影响效果**纳入环境描述
- 无论角色是否对环境产生影响，最终描述中均**不得提及**任何角色本身（不得出现角色名称、角色形态或角色行为）
- 所有输出必须为第三人称视角
- 直接输出一段纯文本的环境描述，不要使用 JSON 或 Markdown 标记"""


#######################################################################################################################################
@final
class EnvironmentInitializationSystem(ExecuteProcessor):
    """为场景实体生成环境描述，写入 EnvironmentComponent.narrative。"""

    def __init__(
        self,
        game: DBGGame,
    ) -> None:
        self._game: Final[DBGGame] = game

    #######################################################################################################################################
    @override
    async def execute(self) -> None:

        # 获取所有场景实体（StageComponent）且尚未生成环境描述（EnvironmentComponent）的实体
        stage_entities = self._game.get_group(
            Matcher(all_of=[StageComponent], none_of=[EnvironmentComponent])
        ).entities.copy()

        # 若没有需要生成环境描述的场景实体，则直接返回
        chat_clients: List[DeepSeekClient] = [
            self._build_client(stage_entity) for stage_entity in stage_entities
        ]

        # 批量发送请求给 AI，等待所有响应完成
        await batch_chat(clients=chat_clients)

        # 处理每个场景实体的 AI 响应，更新 EnvironmentComponent 并存入对话历史
        for chat_client in chat_clients:
            self._process_environment_response(
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
            prompt=_build_environment_prompt(actor_appearances),
            messages=self._game.get_agent_memory(stage_entity).messages,
        )

    #######################################################################################################################################
    def _process_environment_response(
        self,
        chat_client: DeepSeekClient,
    ) -> bool:
        """解析 AI 响应，更新 EnvironmentComponent 并存入对话历史。"""

        # 如果 AI 响应为空，则记录警告并返回 False。
        if chat_client.response_ai_message is None:
            logger.warning(
                f"EnvironmentInitializationSystem: AI 响应为空，name={chat_client.name}"
            )
            return False

        stage_entity = self._game.get_entity_by_name(chat_client.name)
        assert (
            stage_entity is not None
        ), f"stage_entity is None, name={chat_client.name}"

        # 直接取 LLM 返回的纯文本作为环境描述（去除首尾空白）。
        description = chat_client.response_content.strip()
        if not description:
            logger.warning(
                f"EnvironmentInitializationSystem: AI 返回空文本，name={chat_client.name}"
            )
            return False

        # 添加消息（写入与请求一致的完整 prompt，保证记忆与实际请求不错位）。
        self._game.add_human_message(
            stage_entity, HumanMessage(content=chat_client.prompt)
        )

        # 添加消息。
        self._game.add_ai_message(stage_entity, chat_client.response_ai_message)

        # 更新环境叙事
        stage_entity.replace(
            EnvironmentComponent,
            stage_entity.name,
            description,
        )

        return True


#######################################################################################################################################
