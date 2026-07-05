from typing import Final, List, final
from loguru import logger
from overrides import override
from ..deepseek import DeepSeekClient
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.dbg_game import DBGGame
from ..models import ActorComponent, AppearanceComponent, CostumeComponent, HumanMessage
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
        targets = self._get_targets()
        if not targets:
            logger.debug("AppearanceInitializationSystem: 无需初始化外观，跳过")
            return

        # 批量构建 DeepSeekClient 并发送请求
        clients = self._build_clients(targets)

        # 批量请求 DeepSeek 生成外观描述
        await DeepSeekClient.batch_chat(clients)

        # 将 LLM 响应应用回对应角色的外观组件
        for client in clients:
            self._apply_result(client)

    #######################################################################################################################################
    def _get_targets(self) -> List[Entity]:
        """筛选出外观未初始化（appearance == base_body）且穿戴时装的角色实体。"""
        entities = self._game.get_group(
            Matcher(all_of=[ActorComponent, AppearanceComponent, CostumeComponent])
        ).entities
        return [
            entity
            for entity in entities
            if entity.get(AppearanceComponent).appearance
            == entity.get(AppearanceComponent).base_body
        ]

    #######################################################################################################################################
    def _build_clients(self, targets: List[Entity]) -> List[DeepSeekClient]:
        """为目标实体批量构建外观合成所需的 DeepSeekClient 实例。"""
        clients: List[DeepSeekClient] = []
        for entity in targets:
            appearance_comp = entity.get(AppearanceComponent)
            costume: CostumeItem = entity.get(CostumeComponent).item
            prompt = build_appearance_synthesis_prompt(
                base_body=appearance_comp.base_body,
                costume_name=costume.name,
                costume_description=costume.description,
            )
            clients.append(
                DeepSeekClient(
                    name=entity.name,
                    prompt=prompt,
                    context=self._game.get_agent_context(entity).context,
                )
            )
        return clients

    #######################################################################################################################################
    def _apply_result(self, client: DeepSeekClient) -> None:
        """将单个 LLM 响应应用回对应角色的外观组件。"""
        entity = self._game.get_entity_by_name(client.name)
        assert (
            entity is not None
        ), f"ActorAppearanceInitSystem: 找不到实体 {client.name}"

        appearance_comp = entity.get(AppearanceComponent)
        costume: CostumeItem = entity.get(CostumeComponent).item
        new_appearance = client.response_content.strip()

        if not new_appearance:
            logger.warning(
                f"AppearanceInitializationSystem: LLM 返回空，角色 {entity.name} 退回简单拼接"
            )
            new_appearance = f"{appearance_comp.base_body}，{costume.description}"

        entity.replace(
            AppearanceComponent,
            appearance_comp.name,
            appearance_comp.base_body,
            new_appearance,
        )
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
