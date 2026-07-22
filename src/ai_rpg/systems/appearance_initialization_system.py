from typing import Final, List, final
from loguru import logger
from overrides import override
from ..deepseek import DeepSeekClient
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.dbg_game import DBGGame
from ..models import (
    ActorComponent,
    AppearanceComponent,
    EquippedCostumeComponent,
    HumanMessage,
)
from ..models.items import CostumeItem
from .appearance_prompt_builders import (
    build_appearance_synthesis_prompt,
    build_wear_costume_message,
)


#######################################################################################################################################
@final
class AppearanceInitializationSystem(ExecuteProcessor):
    """角色外观初始化系统"""

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    #######################################################################################################################################
    @override
    async def execute(self) -> None:
        """找出 appearance == base_body 且穿戴时装的角色，批量重新合成外观描述。"""

        # 获取所有包含 ActorComponent、AppearanceComponent 和 CostumeComponent 的实体
        entities = self._game.get_group(
            Matcher(
                all_of=[ActorComponent, AppearanceComponent, EquippedCostumeComponent]
            )
        ).entities

        # 筛选出外观未初始化（appearance == base_body）的实体
        targets = [
            entity
            for entity in entities
            if entity.get(AppearanceComponent).appearance
            == entity.get(AppearanceComponent).base_body
        ]

        # 为每个目标实体构建对应的 DeepSeekClient 实例
        chat_clients: List[DeepSeekClient] = [
            self._build_client(entity) for entity in targets
        ]

        # 批量构建 DeepSeekClient 并发送请求
        # 批量请求 DeepSeek 生成外观描述
        await DeepSeekClient.batch_chat(chat_clients)

        # 将 LLM 响应应用回对应角色的外观组件
        for client in chat_clients:
            self._apply_result(client)

    #######################################################################################################################################
    def _build_client(self, entity: Entity) -> DeepSeekClient:
        """为单个目标实体构建外观合成所需的 DeepSeekClient 实例。"""

        appearance_comp = entity.get(AppearanceComponent)
        costume: CostumeItem = entity.get(EquippedCostumeComponent).item

        prompt = build_appearance_synthesis_prompt(
            base_body=appearance_comp.base_body,
            costume_name=costume.name,
            costume_description=costume.description,
        )

        return DeepSeekClient(
            name=entity.name,
            prompt=prompt,
            context=self._game.get_agent_context(entity).context,
        )

    #######################################################################################################################################
    def _apply_result(self, client: DeepSeekClient) -> None:
        """将单个 LLM 响应应用回对应角色的外观组件。"""

        if client.response_ai_message is None:
            logger.warning(f"AppearanceInitializationSystem: LLM 未返回消息")
            return

        entity = self._game.get_entity_by_name(client.name)
        assert (
            entity is not None
        ), f"ActorAppearanceInitSystem: 找不到实体 {client.name}"

        appearance_comp = entity.get(AppearanceComponent)
        costume: CostumeItem = entity.get(EquippedCostumeComponent).item
        new_appearance = client.response_content.strip()

        # 更新外观。
        entity.replace(
            AppearanceComponent,
            appearance_comp.name,
            appearance_comp.base_body,
            new_appearance,
        )

        # 添加事件上下文。
        self._game.add_human_message(
            entity,
            HumanMessage(
                content=build_wear_costume_message(
                    entity.name, costume.name, new_appearance
                )
            ),
        )
        logger.debug(
            f"AppearanceInitializationSystem: 角色 {entity.name} 外观已恢复合成，时装 {costume.name!r}"
        )

    #######################################################################################################################################
