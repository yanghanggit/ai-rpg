from ..models import (
    WorldSystem,
)
from .campaign_setting import FANTASY_WORLD_RPG_CAMPAIGN_SETTING
from .utils import (
    create_world_system,
)


def create_world_system_test() -> WorldSystem:
    """
    创建一个测试的世界系统实例

    Returns:
        WorldSystem: 测试的世界系统实例
    """
    return create_world_system(
        name="系统.世界系统",
        kick_off_message=f"""你已苏醒，准备开始冒险。请告诉我你的职能和目标。""",
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        world_system_profile="你是一个测试的系统。用于生成魔法",
    )
