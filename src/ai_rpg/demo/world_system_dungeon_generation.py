from ..models import (
    WorldSystem,
    DungeonGenerationComponent,
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


def create_dungeon_generation() -> WorldSystem:
    """
    创建地下城图片生成系统。

    该系统负责在进入地下城时，通过文生图 AI 为地下城及其房间生成场景图片。

    Returns:
        WorldSystem: 配置完成的地下城图片生成系统实例
    """

    world_system = create_world_system(
        name="世界系统.地下城生成系统",
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
    )

    # 配置组件
    world_system.component = DungeonGenerationComponent.__name__

    # 返回配置完成的世界系统
    return world_system
