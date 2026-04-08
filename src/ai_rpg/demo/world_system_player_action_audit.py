from ..models import (
    WorldSystem,
    PlayerActionAuditComponent,
    ComponentSerialization,
)
from .global_settings import (
    RPG_CAMPAIGN_SETTING,
    # RPG_SYSTEM_RULES,
)
from .rpg_system_rules import (
    RPG_SYSTEM_RULES,
)
from .entity_factory import (
    create_world_system,
)


def create_player_action_audit() -> WorldSystem:
    """
    创建玩家行动审计系统。

    该系统负责审阅玩家输入的语言类指令，确保指令内容合规：
    1. 不包含法律与道德禁止的内容
    2. 不包含跳出游戏世界观的内容

    Returns:
        WorldSystem: 配置完成的玩家行动审计系统实例
    """

    world_system = create_world_system(
        name="世界系统.玩家行动审计系统",
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
    )

    # 配置组件
    world_system.components = [
        ComponentSerialization(
            name=PlayerActionAuditComponent.__name__,
            data=PlayerActionAuditComponent(name=world_system.name).model_dump(),
        )
    ]

    # 返回配置完成的世界系统
    return world_system
