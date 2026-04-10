"""演示世界创建模块

提供工厂函数创建预配置的游戏世界，包括双角色和单角色版本。
"""

from ..models import (
    Blueprint,
)
from .actor_wanderer import create_wanderer
from .actor_scholar import create_scholar
from .global_settings import RPG_CAMPAIGN_SETTING
from .stage_ruins import (
    create_broken_wall_enclosure,
    create_stone_platform,
)
from .world_system_player_action_audit import create_player_action_audit
from .world_system_dungeon_generation import create_dungeon_generation


#######################################################################################################################
def create_ruins_blueprint(game_name: str) -> Blueprint:
    """
    创建演示游戏世界Blueprint实例 - 旅行者与学者双角色版本。

    包含断壁石室和石台广场两个场景，两名失忆者在沙漠残垣遗迹中醒来。

    Args:
        game_name: 游戏世界的名称

    Returns:
        Blueprint: 初始化完成的游戏世界实例
    """

    # 创建英雄营地场景和角色
    actor_wanderer = create_wanderer()

    # 直接使用外观描述，这样就减少一次推理生成。
    actor_wanderer.character_sheet.appearance = actor_wanderer.character_sheet.base_body

    # 调整旅行者的速度属性，增加其在 SPEED_ORDER 策略下的出手优先级
    actor_wanderer.character_stats.speed = 20

    # 创建学者角色
    actor_mystic = create_scholar()

    # 创建场景
    stage_broken_wall_enclosure = create_broken_wall_enclosure()
    stage_stone_platform = create_stone_platform()

    # 设置关系和消息，先都在这里设置好，后续如果需要调整也方便。
    stage_stone_platform.actors = [actor_wanderer, actor_mystic]

    # 创建世界
    return Blueprint(
        name=game_name,
        player_actor=actor_wanderer.name,  # 玩家角色为战士
        player_only_stage=stage_broken_wall_enclosure.name,
        campaign_setting=RPG_CAMPAIGN_SETTING,
        stages=[
            stage_broken_wall_enclosure,
            stage_stone_platform,
        ],
        world_systems=[create_player_action_audit(), create_dungeon_generation()],
    )


###############################################################################################################################
