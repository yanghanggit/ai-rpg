"""外观合成系统：把「基础体型 + 时装」合成为角色当前外观描述。

推理由世界实体（`AppearanceSynthesisComponent`）承担，只用它的 system prompt；
结果写回 `AppearanceComponent`，并给本人补一条自我状态说明（不广播）。
"""

from typing import Final, List, Optional, Tuple, final, override

from loguru import logger

from ..deepseek import DeepSeekClient, batch_chat
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.dbg_game import DBGGame
from ..models import (
    ActorComponent,
    AppearanceComponent,
    AppearanceSynthesisComponent,
    HumanMessage,
    SystemMessage,
    WornCostumeComponent,
)
from .appearance_prompt_builders import (
    build_appearance_synthesis_prompt,
    build_self_appearance_message,
)

#######################################################################################################################################
# 外观合成请求的 label：`世界.外观合成|角色.名`
_LABEL_SEPARATOR: Final[str] = "|"


def make_appearance_label(world_name: str, actor_name: str) -> str:
    """拼装请求 label：`世界.外观合成|角色.名`。"""
    for part in (world_name, actor_name):
        assert (
            _LABEL_SEPARATOR not in part
        ), f"实体名不能包含 label 分隔符 {_LABEL_SEPARATOR!r}（会破坏回写解析）: {part!r}"
    return f"{world_name}{_LABEL_SEPARATOR}{actor_name}"


def parse_appearance_label(label: str) -> Tuple[str, str]:
    """拆回 `(世界实体名, 角色名)`。"""
    world_name, sep, actor_name = label.partition(_LABEL_SEPARATOR)
    assert sep and world_name and actor_name, f"外观合成 label 格式非法: {label!r}"
    return world_name, actor_name


#######################################################################################################################################
def resolve_appearance_synthesis_entity(game: DBGGame) -> Optional[Entity]:
    """定位唯一的「外观合成」世界实体；缺失或重复时返回 None（调用方自行降级）。"""
    entities = game.get_group(
        Matcher(all_of=[AppearanceSynthesisComponent])
    ).entities.copy()
    if len(entities) != 1:
        logger.warning(
            f"外观合成世界实体数量异常: {len(entities)}"
            f"（应为 1 个 AppearanceSynthesisComponent 世界实体），跳过外观合成。"
            "若为旧存档，请刷新蓝图：python -m scripts.setup_demo"
        )
        return None
    return next(iter(entities))


#######################################################################################################################################
def build_appearance_synthesis_client(
    game: DBGGame,
    world_entity: Entity,
    entity: Entity,
) -> DeepSeekClient:
    """为单个角色构建外观合成客户端（messages 只有世界实体的 system prompt）。"""
    appearance_comp: AppearanceComponent = entity.get(AppearanceComponent)
    costume = entity.get(WornCostumeComponent).item

    memory = game.get_agent_memory(world_entity).messages
    assert memory and isinstance(
        memory[0], SystemMessage
    ), f"{world_entity.name} 缺少 system message"

    return DeepSeekClient(
        label=make_appearance_label(world_entity.name, entity.name),
        input_message=build_appearance_synthesis_prompt(
            base_body=appearance_comp.base_body,
            costume_name=costume.name,
            costume_description=costume.description,
        ),
        # 隔离记忆：角色记忆不参与，也不回写。
        messages=[SystemMessage(content=memory[0].content)],
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
        if world_entity is None:
            return

        chat_clients: List[DeepSeekClient] = [
            build_appearance_synthesis_client(self._game, world_entity, entity)
            for entity in targets
        ]

        await batch_chat(chat_clients)

        for client in chat_clients:
            self._apply_result(client)

    #######################################################################################################################################
    def _apply_result(self, client: DeepSeekClient) -> None:
        """写回外观，并给本人补一条自我状态说明（不广播）。"""
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
