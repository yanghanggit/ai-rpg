"""外观合成公共层：单点维护「管道起点补合成」与「穿装即时合成」共用的部分。

两条调用路径（`AppearanceSynthesisSystem` / `WearCostumeActionSystem`）共用同一个世界实体
（`AppearanceSynthesisComponent`）、同一套请求 label 与同一份隔离式客户端构造方式；
这些必须一致，差异只在触发时机与结果告知方式，那些留在各自 system 文件中。
本模块只放必须同构的部分，避免 label 格式与记忆隔离口径漂移。
"""

from typing import Final, Tuple

from ..deepseek import DeepSeekClient
from ..entitas import Entity, Matcher
from ..game.dbg_game import DBGGame
from ..models import (
    AppearanceComponent,
    AppearanceSynthesisComponent,
    SystemMessage,
    WornCostumeComponent,
)
from .appearance_prompt_builders import build_appearance_synthesis_prompt

#######################################################################################################################################
# 请求 label：`世界.外观合成|角色.名`（主体是世界实体，服务对象是角色）
#######################################################################################################################################
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
# 世界实体定位与客户端构造
#######################################################################################################################################
def resolve_appearance_synthesis_entity(game: DBGGame) -> Entity:
    """定位唯一的「外观合成」世界实体（蓝图必须提供，缺失即数据错误）。"""
    entities = game.get_group(
        Matcher(all_of=[AppearanceSynthesisComponent])
    ).entities.copy()
    assert (
        len(entities) == 1
    ), f"外观合成世界实体数量异常: {len(entities)}（应为 1 个 AppearanceSynthesisComponent 世界实体）。蓝图缺少该实体时请刷新：python -m scripts.setup_demo"
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
