"""场景环境初始化系统：由场景自身生成环境叙事，写入 `EnvironmentComponent` 与场景记忆。"""

from typing import Dict, Final, List, final

from loguru import logger
from overrides import override

from ..deepseek import DeepSeekClient
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.dbg_combat_processor import get_alive_actors_in_stage
from ..game.dbg_game import DBGGame
from ..game.rpg_actor_appearances import get_actor_appearances_in_stage
from ..llm import ChatClientProtocol, batch_chat
from ..models import (
    EnvironmentComponent,
    HomeComponent,
    HumanMessage,
    PlayerComponent,
    StageComponent,
)
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
- 直接输出一段纯文本的环境描述，不要使用 JSON 或 Markdown 标记
- **字数限制**：整体控制在 120 字以内，用简洁笔触勾勒空间轮廓、光影、声音与气味的大致氛围即可，不要逐件罗列陈设与细节"""


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

        # 「无观察 = 无推理」：游戏状态只能从 Actor 视角被观测，因此仅对满足观察者门槛的场景
        # 生成环境叙事；不满足的场景保持惰性（继续缺组件），待条件满足后再自然补生成。
        # 这既省去无效推理，也避免把无关场景卷入批量请求。
        observed_stage_entities = [
            stage_entity
            for stage_entity in stage_entities
            if self._is_observed_stage(stage_entity)
        ]

        # 若没有「有观察者且缺环境」的场景，则无事可做
        if not observed_stage_entities:
            return

        # 构建每个待生成场景的请求客户端
        chat_clients: List[ChatClientProtocol] = [
            self._build_client(stage_entity) for stage_entity in observed_stage_entities
        ]

        # 批量发送请求给 AI，等待所有响应完成。返回与 clients 对齐的失败列表（成功为 None）。
        errors = await batch_chat(clients=chat_clients)

        # 消费 batch 失败列表与逐条处理结果，统一记账：
        # 1) 传输/HTTP 层失败：error 已带原因，直接记账，不再走 response 解析（避免重复告警）；
        # 2) 请求成功但响应为空（空 choices / 空文本）：由 handler 返回 False。
        # 本项为 best-effort：环境叙事是可选补充，失败场景仍缺组件，会在后续「有观察者」的
        # 管线轮次里被再次纳入（惰性重试），因此此处不做同调用内重试。
        failed_names: List[str] = []
        for chat_client, error in zip(chat_clients, errors):
            if error is not None:
                logger.warning(
                    f"EnvironmentInitializationSystem: 环境叙事请求失败 name={chat_client.label} kind={error.kind} status={error.status_code} retryable={error.retryable}"
                )
                failed_names.append(chat_client.label)
                continue

            if not self._process_environment_response(chat_client):
                failed_names.append(chat_client.label)

        # 一次汇总，交代哪些场景未生成及其后续处置
        if failed_names:
            logger.warning(
                f"EnvironmentInitializationSystem: {len(failed_names)}/{len(chat_clients)} 个场景环境叙事未生成（{'、'.join(failed_names)}）；它们将继续缺少 EnvironmentComponent，待后续有观察者的管线轮次自动补齐"
            )

    #######################################################################################################################################
    def _is_observed_stage(self, stage_entity: Entity) -> bool:
        """判断场景是否达到生成环境叙事的观察者门槛。

        - Home 场景：场景内存在存活 Actor（有人）即可；
        - Dungeon 场景：场景内存在存活 Actor，且玩家本人也在场（存活 Actor 中含 PlayerComponent）。
        """
        alive_actors = get_alive_actors_in_stage(self._game, stage_entity)

        # 无人：无观察者，保持惰性
        if not alive_actors:
            return False

        # Home：有人即执行
        if stage_entity.has(HomeComponent):
            return True

        # Dungeon：除有人外，玩家本人必须在场
        return any(actor.has(PlayerComponent) for actor in alive_actors)

    #######################################################################################################################################
    def _build_client(self, stage_entity: Entity) -> DeepSeekClient:
        """为场景实体构建 DeepSeekClient。"""

        actor_appearances: Dict[str, str] = get_actor_appearances_in_stage(
            self._game, stage_entity
        )

        return DeepSeekClient(
            label=stage_entity.name,
            input_message=_build_environment_prompt(actor_appearances),
            messages=self._game.get_agent_memory(stage_entity).messages,
        )

    #######################################################################################################################################
    def _process_environment_response(
        self,
        chat_client: ChatClientProtocol,
    ) -> bool:
        """解析 AI 响应，更新 EnvironmentComponent 并存入对话历史。

        入参按协议标注：只需 label / response_ai_message / response_content，
        与具体 provider 无关。
        """

        # 如果 AI 响应为空，则记录警告并返回 False。
        if chat_client.response_ai_message is None:
            logger.warning(
                f"EnvironmentInitializationSystem: AI 响应为空，name={chat_client.label}"
            )
            return False

        stage_entity = self._game.get_entity_by_name(chat_client.label)
        assert (
            stage_entity is not None
        ), f"stage_entity is None, name={chat_client.label}"

        # 直接取 LLM 返回的纯文本作为环境描述（去除首尾空白）。
        description = chat_client.response_content.strip()
        if not description:
            logger.warning(
                f"EnvironmentInitializationSystem: AI 返回空文本，name={chat_client.label}"
            )
            return False

        # 添加消息（写入与请求一致的完整 prompt，保证记忆与实际请求不错位）。
        self._game.add_human_message(
            stage_entity,
            HumanMessage(
                content=chat_client.input_message,
                environment_initialization=stage_entity.name,
            ),
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
