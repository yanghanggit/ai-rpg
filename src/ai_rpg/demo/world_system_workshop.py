from ..models import (
    WorkshopComponent,
    ComponentSerialization,
)
from .global_settings import RPG_CAMPAIGN_SETTING
from .rpg_system_rules import RPG_SYSTEM_RULES
from .entity_factory import create_world_system
from ..models import WorldSystem


def create_workshop() -> WorldSystem:
    """创建制造工坊世界系统，为 CraftItemActionSystem 提供 LLM context。

    输出格式规范嵌入在每次请求的 user 提示词中，不放入 system_message。

    Returns:
        WorldSystem: 配置完成的制造工坊世界系统实例
    """
    world_system = create_world_system(
        name="世界系统.制造工坊",
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
    )

    world_system.components = [
        ComponentSerialization(
            name=WorkshopComponent.__name__,
            data=WorkshopComponent(name=world_system.name).model_dump(),
        )
    ]

    return world_system
