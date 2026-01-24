from typing import Final, final, override, List
from loguru import logger
from pydantic import BaseModel
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    PlayerComponent,
    SpeakAction,
    WhisperAction,
    AnnounceAction,
    WorldComponent,
    PlayerActionAuditComponent,
)
from ..game.tcg_game import TCGGame
from ..chat_service.client import ChatClient
from ..utils import extract_json_from_code_block
from langchain_core.messages import SystemMessage


####################################################################################################################################
@final
class ContentAuditResponse(BaseModel):
    """内容审核响应数据模型。

    封装 AI 返回的内容审核结果，用于判断玩家动作是否符合规则。

    Attributes:
        is_approved: 审核是否通过（True 表示批准，False 表示拒绝）
        reason: 拒绝理由（审核不通过时必填）
    """

    is_approved: bool
    reason: str = ""


####################################################################################################################################
def _build_audit_prompt(content: str) -> str:
    """构建内容审核提示词。

    生成用于 AI 审核玩家动作内容的提示词，要求 AI 判断内容是否合适。

    Args:
        content: 待审核的玩家动作内容

    Returns:
        格式化的审核提示词
    """
    return f"""# 指令！内容审核，以JSON格式返回结果

{content}

## 输出格式(JSON)

```json
{{
  "is_approved": true或false,
  "reason": "拒绝理由（不通过时必填）"
}}
```

**约束规则**：

- 严格按上述JSON格式输出审核结果
- 所有字段名不可更改"""


####################################################################################################################################


@final
class PlayerActionAuditSystem(ReactiveProcessor):
    """玩家动作审核系统。

    反应式处理器，监听玩家的消息动作组件（SpeakAction、WhisperAction、AnnounceAction），
    通过审计世界系统的 AI 进行内容审核。审核不通过时移除所有动作组件，阻止消息发送。

    工作流程：
        1. 监听玩家实体上的消息动作组件添加事件
        2. 获取玩家行动审计世界系统实体（包含 PlayerActionAuditComponent）
        3. 提取所有待审核的动作内容
        4. 使用审计世界系统的 AI 上下文进行内容审核
        5. 根据审核结果决定是否保留动作组件

    安全策略：
        - 任何异常情况（AI 连接失败、响应解析错误等）都默认拒绝
        - 审核不通过时移除所有动作，等同于取消本回合的所有发言
        - 审核通过的动作继续保留，由后续系统处理

    Attributes:
        _game: 游戏实例引用

    Note:
        - 当前为单机游戏模式，仅支持一个玩家实体
        - 审核标准来自玩家行动审计世界系统，而非玩家自身的 AI 上下文
    """

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: Final[TCGGame] = game_context

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        # 监听玩家实体上SpeakAction、WhisperAction和AnnounceAction组件的添加事件
        return {
            Matcher(SpeakAction): GroupEvent.ADDED,
            Matcher(WhisperAction): GroupEvent.ADDED,
            Matcher(AnnounceAction): GroupEvent.ADDED,
        }

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:

        # 只处理包含PlayerComponent且具有SpeakAction、WhisperAction或AnnounceAction组件的实体
        return entity.has(PlayerComponent) and (
            entity.has(SpeakAction)
            or entity.has(WhisperAction)
            or entity.has(AnnounceAction)
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:

        # 获取玩家行动审计系统实体
        world_system_entities = self._game.get_group(
            Matcher(all_of=[WorldComponent, PlayerActionAuditComponent])
        ).entities.copy()

        # 确保存在玩家行动审计系统实体
        if not world_system_entities:
            logger.error("未找到玩家行动审计系统实体，无法进行内容审核")
            return

        # 应该只有一个玩家行动审计系统实体
        assert len(world_system_entities) == 1, "存在多个玩家行动审计系统实体，数据异常"
        world_system_entity = next(iter(world_system_entities))

        # 单机游戏，应该只有一个玩家实体
        assert len(entities) == 1, "单机游戏，玩家实体不应该超过1个"
        player_entity = entities[0]
        await self._filter_player_actions(player_entity, world_system_entity)

    ####################################################################################################################################
    def _extract_all_action_contents(self, player_entity: Entity) -> str:
        """从实体中提取所有需要审核的动作内容。

        同时检查 SpeakAction、WhisperAction、AnnounceAction，
        将所有存在的动作内容拼接成一个完整的审核文本。

        Args:
            player_entity: 玩家实体

        Returns:
            拼接后的完整审核内容文本，如果没有任何动作则返回空字符串
        """
        content_parts: List[str] = []

        # 提取 SpeakAction
        if player_entity.has(SpeakAction):
            speak_action = player_entity.get(SpeakAction)
            messages = "\n".join(
                [
                    f"  对 {target}: {msg}"
                    for target, msg in speak_action.target_messages.items()
                ]
            )
            content_parts.append(f"【说话】\n{messages}")

        # 提取 WhisperAction
        if player_entity.has(WhisperAction):
            whisper_action = player_entity.get(WhisperAction)
            messages = "\n".join(
                [
                    f"  对 {target}: {msg}"
                    for target, msg in whisper_action.target_messages.items()
                ]
            )
            content_parts.append(f"【私聊】\n{messages}")

        # 提取 AnnounceAction
        if player_entity.has(AnnounceAction):
            announce_action = player_entity.get(AnnounceAction)
            content_parts.append(f"【公告】\n  {announce_action.message}")

        return "\n\n".join(content_parts)

    ####################################################################################################################################
    def _remove_all_actions(self, entity: Entity) -> None:
        """移除实体上所有待审核的动作组件。

        用于在内容审核不通过时，阻止所有形式的消息发送。

        Args:
            entity: 玩家实体
        """
        if entity.has(SpeakAction):
            entity.remove(SpeakAction)
        if entity.has(WhisperAction):
            entity.remove(WhisperAction)
        if entity.has(AnnounceAction):
            entity.remove(AnnounceAction)

    ####################################################################################################################################
    async def _filter_player_actions(
        self, entity: Entity, world_system_entity: Entity
    ) -> None:
        """审核玩家动作内容。

        提取玩家实体上的所有待审核动作（SpeakAction、WhisperAction、AnnounceAction），
        通过审计世界系统的 AI 进行内容审核。审核不通过时移除所有动作组件，阻止消息发送。

        Args:
            entity: 玩家实体
            world_system_entity: 玩家行动审计系统实体

        Note:
            - 任何异常情况（AI 连接失败、响应解析错误等）都默认拒绝，确保安全性
            - 审核通过的动作继续保留在实体上，由后续系统处理
            - 审核不通过时移除所有动作，等同于取消本回合的所有发言
        """
        # 提取所有需要审核的内容
        content = self._extract_all_action_contents(entity)

        if not content:
            logger.warning(f"实体 {entity.name} 没有需要审核的内容")
            return

        # 执行AI审核检查
        try:
            # 构建审核提示词
            prompt = _build_audit_prompt(content)

            # 获取审计世界系统的AI上下文
            agent_context = self._game.get_agent_context(world_system_entity)
            assert isinstance(
                agent_context.context[0], SystemMessage
            ), "审计世界系统AI上下文的第一条消息必须是SystemMessage类型"

            # 创建AI审核请求（使用审计世界系统的system prompt）
            chat_client = ChatClient(
                name=world_system_entity.name,
                prompt=prompt,
                context=[agent_context.context[0]],
            )

            # 发送审核请求
            await ChatClient.batch_chat(clients=[chat_client])

            # 解析AI响应
            response_content = chat_client.response_content
            logger.debug(f"AI审核响应: {response_content}")

            try:
                audit_response = ContentAuditResponse.model_validate_json(
                    extract_json_from_code_block(response_content)
                )
                is_approved = audit_response.is_approved
                reason = audit_response.reason

            except Exception as e:
                logger.error(f"解析AI审核响应失败: {e}")
                logger.error(f"原始响应: {response_content}")
                # 解析失败时默认拒绝,保证安全性
                is_approved = False
                reason = "AI审核响应格式错误,请重试"

        except Exception as e:
            logger.error(f"AI审核过程出错: {e}")
            # 出错时默认拒绝,保证安全性
            is_approved = False
            reason = "审核系统异常,请稍后重试"

        # 处理审核结果
        if not is_approved:
            logger.warning(f"玩家输入未通过AI审核: {reason}")
            self._remove_all_actions(entity)
        else:
            logger.info(f"玩家输入通过AI审核")

    ####################################################################################################################################
