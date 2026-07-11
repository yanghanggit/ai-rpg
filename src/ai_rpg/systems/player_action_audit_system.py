from typing import Final, final, override, List, Dict
from loguru import logger
from pydantic import BaseModel, field_validator
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    PlayerComponent,
    SpeakAction,
    WhisperAction,
    AnnounceAction,
    WorldComponent,
    PlayerActionAuditComponent,
)
from ..game.dbg_game import DBGGame
from ..deepseek import DeepSeekClient
from ..utils import extract_json_from_code_block
from ..models.messages import SystemMessage


####################################################################################################################################
@final
class ContentAuditResponse(BaseModel):
    """内容审核响应数据模型。"""

    is_approved: bool
    reason: str = ""

    @field_validator("reason", mode="before")
    @classmethod
    def _coerce_none(cls, v: object) -> str:
        return str(v) if v is not None else ""


####################################################################################################################################
def _build_audit_prompt(content: str) -> str:
    """构建内容审核提示词。"""
    return f"""# 内容审核，以JSON格式返回结果

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
    """玩家动作内容审核系统。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
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
    async def react(self, entities: List[Entity]) -> None:

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
        await self._filter_player_actions(entities[0], world_system_entity)

    ####################################################################################################################################
    def _extract_all_action_contents(self, player_entity: Entity) -> str:
        """从实体中提取所有需要审核的动作内容。"""
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
        """移除实体上所有待审核的动作组件"""
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
        """审核玩家动作内容。"""
        # 提取所有需要审核的内容
        content = self._extract_all_action_contents(entity)

        if not content:
            logger.warning(f"实体 {entity.name} 没有需要审核的内容")
            return

        # 构建审核提示词
        prompt = _build_audit_prompt(content)

        # 获取审计世界系统的AI上下文
        agent_context = self._game.get_agent_context(world_system_entity)
        assert isinstance(
            agent_context.context[0], SystemMessage
        ), "审计世界系统AI上下文的第一条消息必须是SystemMessage类型"

        # 创建AI审核请求（使用审计世界系统的system prompt）
        chat_client = DeepSeekClient(
            name=world_system_entity.name,
            prompt=prompt,
            context=[agent_context.context[0]],
        )

        # 发送审核请求；出错时默认拒绝，保证安全性
        try:
            await chat_client.chat()
        except Exception as e:
            logger.error(f"AI审核过程出错: {e}")
            logger.warning("玩家输入未通过AI审核: 审核系统异常,请稍后重试")
            self._remove_all_actions(entity)
            return

        # 解析AI响应；解析失败时默认拒绝，保证安全性
        response_content = chat_client.response_content
        logger.debug(f"AI审核响应: {response_content}")

        try:
            audit_response = ContentAuditResponse.model_validate_json(
                extract_json_from_code_block(response_content)
            )
        except Exception as e:
            logger.error(f"解析AI审核响应失败: {e}")
            logger.error(f"原始响应: {response_content}")
            logger.warning("玩家输入未通过AI审核: AI审核响应格式错误,请重试")
            self._remove_all_actions(entity)
            return

        # 处理审核结果
        if not audit_response.is_approved:
            logger.warning(f"玩家输入未通过AI审核: {audit_response.reason}")
            self._remove_all_actions(entity)
        else:
            logger.info(f"玩家输入通过AI审核")

    ####################################################################################################################################
