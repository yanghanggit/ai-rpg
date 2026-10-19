"""外观合成系统：把「基础体型 + 时装」合成为角色当前外观描述。

推理由世界实体（`AppearanceSynthesisComponent`）承担，只用它的 system prompt；
结果写回 `AppearanceComponent`，并给本人补一条自我状态说明（不广播）。
与穿装共用 label / 世界实体 / 客户端构造，那些在 `appearance_synthesis_common.py`。
"""

from typing import Final, List, final, override

from loguru import logger

from ..deepseek import batch_chat
from ..entitas import ExecuteProcessor, Matcher
from ..game.dbg_game import DBGGame
from ..llm import ChatClientProtocol
from ..models import (
    ActorComponent,
    AppearanceComponent,
    HumanMessage,
    WornCostumeComponent,
)
from .appearance_prompt_builders import build_self_appearance_message
from .appearance_synthesis_common import (
    build_appearance_synthesis_client,
    parse_appearance_label,
    resolve_appearance_synthesis_entity,
)


#######################################################################################################################################
@final
class AppearanceSynthesisSystem(ExecuteProcessor):
    """为「外观尚未合成」的角色补齐外观描述。"""

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    #######################################################################################################################################
    @override
    async def execute(self) -> None:
        """找出 appearance == base_body 且穿戴时装的角色，批量重新合成外观描述。"""

        entities = self._game.get_group(
            Matcher(all_of=[ActorComponent, AppearanceComponent, WornCostumeComponent])
        ).entities

        # 外观未初始化：appearance 仍等于 base_body（即尚未与时装合成过）。
        targets = [
            entity
            for entity in entities
            if entity.get(AppearanceComponent).appearance
            == entity.get(AppearanceComponent).base_body
        ]
        if not targets:
            return

        world_entity = resolve_appearance_synthesis_entity(self._game)

        chat_clients: List[ChatClientProtocol] = [
            build_appearance_synthesis_client(self._game, world_entity, entity)
            for entity in targets
        ]

        await batch_chat(chat_clients)

        for client in chat_clients:
            self._apply_result(client)

    #######################################################################################################################################
    def _apply_result(self, client: ChatClientProtocol) -> None:
        """写回外观，并给本人补一条自我状态说明（不广播）。

        入参按协议标注：只需 label / response_ai_message / response_content。
        """
        if client.response_ai_message is None:
            logger.warning(f"AppearanceSynthesisSystem: {client.label} 未返回消息")
            return

        new_appearance = client.response_content.strip()
        if new_appearance == "":
            logger.warning(f"AppearanceSynthesisSystem: {client.label} 返回空外观")
            return

        # label 是「世界.外观合成|角色.名」：回写落在服务对象（actor）身上。
        _, actor_name = parse_appearance_label(client.label)
        entity = self._game.get_entity_by_name(actor_name)
        assert entity is not None, f"AppearanceSynthesisSystem: 找不到实体 {actor_name}"

        appearance_comp: AppearanceComponent = entity.get(AppearanceComponent)
        entity.replace(
            AppearanceComponent,
            appearance_comp.name,
            appearance_comp.base_body,
            new_appearance,
        )
        # 只写给本人：这是自我状态，不是世界内的外观变化事件。
        costume = entity.get(WornCostumeComponent).item
        self._game.add_human_message(
            entity=entity,
            human_message=HumanMessage(
                content=build_self_appearance_message(
                    costume_name=costume.name,
                    new_appearance=new_appearance,
                ),
                appearance_update="self",
            ),
        )
        logger.debug(
            f"AppearanceSynthesisSystem: 角色 {entity.name} 外观已合成（仅本人收到说明）"
        )
