from typing import Final, List, Set, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..chat_services.client import ChatClient
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from ..models import (
    ActorComponent,
    AppearanceComponent,
)
from ..utils import extract_json_from_code_block
from ..demo import create_actor_warrior


#######################################################################################################################################
@final
class AppearanceResponse(BaseModel):
    appearance: str = ""


#######################################################################################################################################
def _build_appearance_prompt(
    base_body: str,
    actor_name: str,
) -> str:
    """构建角色外观生成的提示词（简化版）。

    根据角色的基础身体形态生成完整的外观描述提示词。
    该提示词要求AI基于base_body生成详细的外观描述。

    Args:
        base_body: 基础身体形态（天生特征）
        actor_name: 角色名称

    Returns:
        格式化的提示词字符串，包含角色信息和输出格式说明
    """

    return f"""# 指令！请根据角色的基础身体形态，生成完整的外观描述。

## 角色名称

{actor_name}

## 基础身体形态

{base_body}

## 输出格式(JSON)
```json
{{
  "appearance": "完整的外观描述"
}}
```

**生成规则**：
1. 必须包含基础身体形态的所有特征
2. 可以适当补充穿着的基础服饰（如内衣、简单衣物）
3. 描述应连贯、具有画面感
4. 使用第三人称视角
5. 字数控制在 80-150 字之间
6. 严格按上述 JSON 格式输出"""


#######################################################################################################################################
def _compress_prompt_for_history(prompt: str) -> str:
    """压缩提示词以便保存到对话历史。

    将完整的外观生成提示词压缩成简短版本，减少存储在消息历史中的token消耗。

    Args:
        prompt: 原始完整提示词

    Returns:
        压缩后的简短提示词字符串
    """
    logger.debug(f"准备压缩原始提示词 {prompt[:100]}...")
    return "# 指令！请根据基础身体形态生成完整的外观描述。"


#######################################################################################################################################
@final
class ActorAppearanceUpdateSystem(ExecuteProcessor):
    """角色外观更新系统（简化版）。

    根据角色的基础身体形态（base_body），通过 LLM 动态生成角色的完整外观描述（appearance）。
    系统会自动筛选出需要生成外观的角色，通过AI并行生成描述内容，并将结果保存到角色实体的外观组件中。

    工作流程：
        1. 查询所有角色实体（包含 ActorComponent 和 AppearanceComponent）
        2. 筛选出 base_body 不为空且 appearance 为空的角色
        3. 为每个角色构建包含 base_body 的提示词
        4. 并行发送请求到AI服务生成外观描述
        5. 解析响应并更新角色实体的 AppearanceComponent.appearance
        6. 将压缩后的提示词和AI响应保存到对话历史

    特性：
        - 智能跳过已有外观或缺少base_body的角色，避免重复生成
        - 并行请求提升效率
        - 提示词压缩节省对话历史存储空间
        - 外观描述基于角色的基础身体形态生成

    触发条件：
        - base_body 不为空（已定义基础形态）
        - appearance 为空（需要生成）

    Note:
        - 本版本不考虑装备和技能信息
        - 仅基于 base_body 生成基础外观
        - 可以在后续版本中扩展支持装备系统

    Attributes:
        _game: TCG游戏上下文，用于访问实体和游戏状态
    """

    def __init__(self, game_context: TCGGame) -> None:
        self._game: Final[TCGGame] = game_context

    #######################################################################################################################################
    @override
    async def execute(self) -> None:

        # 获取所有角色实体
        actor_entities = self._game.get_group(
            Matcher(all_of=[ActorComponent, AppearanceComponent])
        ).entities.copy()

        # 准备外观更新请求
        chat_clients: List[ChatClient] = self._prepare_appearance_requests(
            actor_entities
        )

        # 并行发送请求
        await ChatClient.gather_request_post(clients=chat_clients)

        # 处理响应
        for chat_client in chat_clients:

            actor_entity = self._game.get_entity_by_name(chat_client.name)
            assert actor_entity is not None

            self._process_appearance_response(actor_entity, chat_client)

    #######################################################################################################################################
    def _prepare_appearance_requests(
        self, actor_entities: Set[Entity]
    ) -> List[ChatClient]:
        """准备需要更新外观的角色请求。

        遍历所有角色实体，筛选出需要生成外观的角色（base_body不为空且appearance为空），
        为每个角色构建ChatClient请求处理器。

        Args:
            actor_entities: 所有角色实体的集合

        Returns:
            ChatClient请求处理器列表，每个处理器对应一个待生成外观的角色
        """
        chat_clients: List[ChatClient] = []

        for actor_entity in actor_entities:

            if actor_entity.name != "角色.战士.卡恩":
                continue

            appearance_comp = actor_entity.get(AppearanceComponent)

            # 筛选条件：base_body 不为空 且 appearance 为空
            if appearance_comp.base_body == "":
                logger.debug(f"跳过角色 {actor_entity.name}，base_body 为空")
                continue

            if appearance_comp.appearance != "":
                logger.debug(f"跳过角色 {actor_entity.name}，外观已存在")
                continue

            # 构建请求处理器
            chat_clients.append(
                ChatClient(
                    name=actor_entity.name,
                    prompt=_build_appearance_prompt(
                        base_body=appearance_comp.base_body,
                        actor_name=actor_entity.name,
                    ),
                    context=self._game.get_agent_context(actor_entity).context,
                )
            )

        logger.info(f"准备为 {len(chat_clients)} 个角色生成外观描述")
        return chat_clients

    #######################################################################################################################################
    def _process_appearance_response(
        self, actor_entity: Entity, chat_client: ChatClient
    ) -> None:
        """处理外观生成的响应结果。

        解析AI返回的外观描述JSON，将压缩后的提示词和AI响应保存到对话历史，
        并更新角色实体的 AppearanceComponent.appearance 字段。

        Args:
            actor_entity: 角色实体
            chat_client: 包含请求和响应内容的ChatClient处理器

        Raises:
            Exception: 当响应解析失败时记录错误日志
        """
        try:

            format_response = AppearanceResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            self._game.add_human_message(
                actor_entity, _compress_prompt_for_history(chat_client.prompt)
            )
            self._game.add_ai_message(actor_entity, chat_client.response_ai_messages)

            # 更新 AppearanceComponent
            if format_response.appearance != "":
                appearance_comp = actor_entity.get(AppearanceComponent)
                actor_entity.replace(
                    AppearanceComponent,
                    appearance_comp.name,
                    appearance_comp.base_body,  # 保持 base_body 不变
                    format_response.appearance,  # 更新 appearance
                )

                logger.info(f"✅ 成功更新角色 {actor_entity.name} 的外观描述")
            else:
                logger.warning(f"⚠️  角色 {actor_entity.name} 的外观描述为空，跳过更新")

        except Exception as e:
            logger.error(f"❌ 处理角色 {actor_entity.name} 的外观响应失败: {e}")


#######################################################################################################################################
