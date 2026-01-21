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
    PlayerComponent,
    Item,
    ItemType,
    InventoryComponent,
)
from ..utils import extract_json_from_code_block
from langchain_core.messages import SystemMessage


#######################################################################################################################################
@final
class AppearanceResponse(BaseModel):
    appearance: str = ""


#######################################################################################################################################
def _build_appearance_prompt(base_body: str, equipped_items: str) -> str:
    """构建角色外观生成的提示词。

    Args:
        base_body: 基础身体形态（天生特征）
        equipped_items: 装备物品描述，如果为空字符串则显示"无"

    Returns:
        格式化的提示词字符串
    """
    equipped_items_display = equipped_items if equipped_items else "无"

    return f"""# 指令！请根据你的基础身体形态和装备信息，生成你的完整外观描述，以JSON返回。

## 基础身体形态

{base_body}

## 装备信息

{equipped_items_display}

## 输出格式

```json
{{
  "appearance": "外观描述"
}}
```

## 约束

- 严格按JSON格式输出
- 客观视觉描述可见特征，第三人称，严禁主观词汇和角色名字
- 严禁提及任何装备或物品的名称
- 严格遵守物理遮挡逻辑，只描述未被装备覆盖的可见部位，自然融入装备视觉特征
- 连贯流畅，100-150字"""


#######################################################################################################################################
def _format_appearance_update_notification(appearance: str) -> str:
    """格式化外观更新通知消息。

    Args:
        appearance: 完整的外观描述

    Returns:
        格式化后的通知消息字符串
    """
    return f"""# 通知！你的外观信息已经更新: 

{appearance}"""


#######################################################################################################################################
@final
class ActorAppearanceUpdateSystem(ExecuteProcessor):
    """角色外观更新系统。

    根据角色的基础身体形态（base_body）和装备信息通过 LLM 生成完整的外观描述（appearance）。
    系统自动筛选需要生成外观的角色，并行生成后更新到角色实体组件中。

    工作流程：
        1. 查询所有角色实体（包含 ActorComponent 和 AppearanceComponent）
        2. 筛选出 base_body 不为空且 appearance 为空的角色
        3. 从 InventoryComponent 读取角色的装备类型物品（武器、防具、饰品）
        4. 为每个角色构建包含基础形态和装备信息的提示词（使用 System Prompt 作为上下文）
        5. 并行发送请求到 AI 服务生成外观描述
        6. 解析响应并更新 AppearanceComponent.appearance
        7. 向角色 Agent 上下文添加外观更新通知

    触发条件：
        - base_body 不为空（已定义基础形态）
        - appearance 为空（需要生成）

    Note:
        LLM 具备物理遮挡推理能力，会自动处理装备遮挡关系（如全覆盖面罩不会描述被遮挡的面部特征）。
        如果角色没有装备，装备信息将显示为"无"。

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
            Matcher(all_of=[ActorComponent, PlayerComponent, AppearanceComponent])
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
        从 InventoryComponent 读取装备信息，为每个角色构建 ChatClient 请求处理器。

        Args:
            actor_entities: 所有角色实体的集合

        Returns:
            ChatClient请求处理器列表，每个处理器对应一个待生成外观的角色
        """
        chat_clients: List[ChatClient] = []

        for actor_entity in actor_entities:

            appearance_comp = actor_entity.get(AppearanceComponent)

            # 筛选条件：base_body 不为空 且 appearance 为空
            if appearance_comp.base_body == "":
                # logger.debug(f"跳过角色 {actor_entity.name}，base_body 为空")
                continue

            if appearance_comp.appearance != "":
                # logger.debug(f"跳过角色 {actor_entity.name}，外观已存在")
                continue

            # 获取 Agent 上下文
            agent_context = self._game.get_agent_context(actor_entity)
            assert isinstance(
                agent_context.context[0], SystemMessage
            ), "角色AI上下文的第一条消息必须是SystemMessage类型"

            # 获取角色装备类型物品
            equipped_items = self._get_equipment_type_items(actor_entity)
            equipped_items_text = "\n".join(
                [
                    f"- {item.name}: {item.description}, 数量: {item.count}"
                    for item in equipped_items
                ]
            )
            logger.debug(
                f"角色 {actor_entity.name} 拥有装备类型物品 {len(equipped_items)} 件"
            )

            # 构建请求处理器
            chat_clients.append(
                ChatClient(
                    name=actor_entity.name,
                    prompt=_build_appearance_prompt(
                        base_body=appearance_comp.base_body,
                        equipped_items=equipped_items_text,
                    ),
                    context=[agent_context.context[0]],
                )
            )

        # logger.debug(f"准备为 {len(chat_clients)} 个角色生成外观描述")
        return chat_clients

    #######################################################################################################################################
    def _process_appearance_response(
        self, actor_entity: Entity, chat_client: ChatClient
    ) -> None:
        """处理外观生成的响应结果。

        解析 AI 返回的外观描述 JSON，更新 AppearanceComponent.appearance，
        并向 Agent 上下文添加外观更新通知。

        Args:
            actor_entity: 角色实体
            chat_client: 包含请求和响应内容的 ChatClient 处理器

        Raises:
            Exception: 当响应解析失败时记录错误日志
        """
        try:

            format_response = AppearanceResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )
            # 更新 AppearanceComponent
            if format_response.appearance != "":
                appearance_comp = actor_entity.get(AppearanceComponent)
                actor_entity.replace(
                    AppearanceComponent,
                    appearance_comp.name,
                    appearance_comp.base_body,  # 保持 base_body 不变
                    format_response.appearance,  # 更新 appearance
                )

                # 通知 Agent 外观已更新
                self._game.add_human_message(
                    actor_entity,
                    _format_appearance_update_notification(format_response.appearance),
                )

                logger.info(f"✅ 成功更新角色 {actor_entity.name} 的外观描述")
            else:
                logger.warning(f"⚠️  角色 {actor_entity.name} 的外观描述为空，跳过更新")

        except Exception as e:
            logger.error(f"❌ 处理角色 {actor_entity.name} 的外观响应失败: {e}")

    #######################################################################################################################################
    def _get_equipment_type_items(self, actor_entity: Entity) -> List[Item]:
        """从角色背包中筛选出所有装备类型的物品。

        遍历角色的 InventoryComponent，返回所有类型为武器、防具、饰品的物品。
        注意：该函数筛选的是装备**类型**的物品，并非判断物品是否已装备（equipped状态）。

        Args:
            actor_entity: 角色实体，必须包含 InventoryComponent 组件

        Returns:
            装备类型物品列表（WEAPON、ARMOR、ACCESSORY）

        Raises:
            AssertionError: 当实体缺少 InventoryComponent 时抛出
        """
        inventory_comp = actor_entity.get(InventoryComponent)
        assert inventory_comp is not None, "Entity must have InventoryComponent"

        equipment_type_items: List[Item] = []
        for item in inventory_comp.items:
            if item.type in {ItemType.WEAPON_ITEM, ItemType.EQUIPMENT_ITEM}:
                equipment_type_items.append(item)

        return equipment_type_items

    #######################################################################################################################################
