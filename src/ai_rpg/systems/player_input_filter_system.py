"""玩家输入过滤系统模块。

该模块实现了玩家输入的内容审核过滤功能,在玩家执行对话动作前进行内容检查,
通过玩家角色的AI进行自我审核,阻止不合规的输入,并向玩家返回友好的提示信息。

主要功能:
- 检查玩家的对话输入内容
- 通过玩家AI自我判断内容是否合规
- 阻止不合规的对话动作
- 向玩家提供明确的错误提示

工作流程:
1. 拦截玩家的SpeakAction
2. 将玩家的输入内容发送给玩家AI进行审核
3. 玩家AI根据其actor_profile中的规则判断内容是否合规
4. 如果不合规,移除SpeakAction并返回提示
5. 如果合规,允许SpeakAction继续执行
"""

from typing import final, override
from loguru import logger
from pydantic import BaseModel
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import SpeakAction, PlayerComponent
from ..game.tcg_game import TCGGame
from ..chat_services.client import ChatClient
from ..utils import extract_json_from_code_block


####################################################################################################################################
@final
class InputFilterResponse(BaseModel):
    """输入过滤响应数据模型。
    
    封装AI返回的输入审核结果。
    
    Attributes:
        is_approved: 输入是否通过审核(True表示通过,False表示拒绝)
        reason: 拒绝原因(如果is_approved为False,需要填写拒绝理由)
    """
    
    is_approved: bool
    reason: str = ""


####################################################################################################################################
def _build_filter_prompt(target_messages: dict[str, str]) -> str:
    """构建输入过滤提示词。
    
    生成用于AI审核玩家输入内容的提示词。
    
    Args:
        target_messages: 玩家要发送的消息字典,键为目标角色名,值为消息内容
        
    Returns:
        格式化的提示词字符串
    """
    messages_text = "\n".join([f"对 {target}: {content}" for target, content in target_messages.items()])
    
    return f"""# 内容审核指令！请审核以下即将发送的消息内容

## 待审核的消息

{messages_text}

## 审核任务

请根据你的角色设定中的"输入内容审核规则",判断这些消息内容是否合适。

## 输出格式

请严格按照以下JSON格式输出审核结果:

```json
{{
  "is_approved": true或false,
  "reason": "如果拒绝则必须填写拒绝理由"
}}
```"""


####################################################################################################################################
def _format_filter_rejection_message(player_name: str, reason: str) -> str:
    """格式化过滤拒绝消息。
    
    Args:
        player_name: 玩家名称
        reason: 拒绝原因
        
    Returns:
        格式化后的拒绝消息字符串
    """
    return f"""# 系统提示！{player_name} 的输入未通过审核

**原因**: {reason}

**提示**: 请调整您的输入内容后重试。"""


####################################################################################################################################


@final
class PlayerInputFilterSystem(ReactiveProcessor):
    """玩家输入过滤系统。
    
    该系统在玩家执行对话动作前通过玩家AI进行内容审核,确保输入内容符合规范。
    当检测到不合规内容时,会阻止动作执行并向玩家返回提示信息。
    
    审核机制:
    - 将玩家输入发送给玩家自己的AI进行审核
    - AI根据actor_profile中定义的规则进行判断
    - 只有通过AI审核的内容才会继续执行
    
    Attributes:
        _game: 游戏上下文实例
    """

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: TCGGame = game_context

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        """获取系统触发器。
        
        监听SpeakAction组件的添加事件,但只处理玩家实体的动作。
        
        Returns:
            触发器配置字典
        """
        return {Matcher(SpeakAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        """过滤需要处理的实体。
        
        只处理包含SpeakAction和PlayerComponent的实体(即玩家实体)。
        NPC的对话不需要经过此过滤系统。
        
        Args:
            entity: 待检查的实体
            
        Returns:
            如果是玩家实体且包含SpeakAction则返回True,否则返回False
        """
        return entity.has(SpeakAction) and entity.has(PlayerComponent)

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        """响应实体变化。
        
        对每个玩家的SpeakAction执行AI审核检查。
        
        Args:
            entities: 触发事件的实体列表
        """
        for entity in entities:
            await self._process_input_filter(entity)

    ####################################################################################################################################
    async def _process_input_filter(self, entity: Entity) -> None:
        """处理实体的输入过滤。

        该方法通过调用玩家AI来审核对话内容是否合规,如果AI判断不合规,
        会移除SpeakAction组件以阻止后续的对话处理,并向玩家发送AI给出的拒绝理由。

        处理流程:
        1. 获取实体的 SpeakAction 组件
        2. 构建审核提示词
        3. 调用玩家AI进行审核
        4. 解析AI的审核结果
        5. 如果不通过,移除 SpeakAction 组件并添加提示消息

        Args:
            entity: 包含 SpeakAction 组件的玩家实体

        Returns:
            None

        Note:
            - 当前为测试版本,AI会拒绝所有输入
            - 移除 SpeakAction 后,后续的 SpeakActionSystem 不会处理此实体
            - AI的审核规则在actor_profile或kick_off中定义
        """
        speak_action = entity.get(SpeakAction)
        
        # 执行AI审核检查
        is_approved, reason = await self._check_content_with_ai(entity, speak_action)
        
        if not is_approved:
            # 审核不通过,移除SpeakAction组件以阻止后续处理
            logger.warning(f"玩家输入未通过AI审核: {reason}")
            entity.remove(SpeakAction)
            
            # 向玩家发送AI给出的拒绝理由
            self._game.add_human_message(
                entity=entity,
                message_content=_format_filter_rejection_message(
                    speak_action.name, reason
                ),
            )
        else:
            logger.info(f"玩家输入通过AI审核")

    ####################################################################################################################################
    async def _check_content_with_ai(
        self, entity: Entity, speak_action: SpeakAction
    ) -> tuple[bool, str]:
        """通过AI检查对话内容是否通过过滤。
        
        调用玩家的AI进行内容审核,AI会根据其角色设定判断内容是否合规。
        
        Args:
            entity: 玩家实体
            speak_action: 要检查的对话动作
            
        Returns:
            元组 (是否通过审核, 拒绝理由)
            
        Note:
            当前测试版本中,AI会拒绝所有输入以测试系统是否正常工作
        """
        try:
            # 构建审核提示词
            prompt = _build_filter_prompt(speak_action.target_messages)
            
            # 获取玩家的AI上下文
            agent_context = self._game.get_agent_context(entity)
            
            # 创建AI审核请求
            chat_client = ChatClient(
                name=entity.name,
                prompt=prompt,
                context=agent_context.context,
            )
            
            # 发送审核请求
            await ChatClient.gather_request_post(clients=[chat_client])
            
            # 解析AI响应
            response_content = chat_client.response_content
            logger.debug(f"AI审核响应: {response_content}")
            
            try:
                filter_response = InputFilterResponse.model_validate_json(
                    extract_json_from_code_block(response_content)
                )
                
                return filter_response.is_approved, filter_response.reason
                
            except Exception as e:
                logger.error(f"解析AI审核响应失败: {e}")
                logger.error(f"原始响应: {response_content}")
                # 解析失败时默认拒绝,保证安全性
                return False, "AI审核响应格式错误,请重试"
                
        except Exception as e:
            logger.error(f"AI审核过程出错: {e}")
            # 出错时默认拒绝,保证安全性
            return False, "审核系统异常,请稍后重试"

    ####################################################################################################################################
