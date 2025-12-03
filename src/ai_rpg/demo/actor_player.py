from ..models import (
    Actor,
    ActorType,
    CharacterStats,
)
from .campaign_setting import (
    FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
    FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
)
from .utils import (
    create_actor,
)


def create_actor_player() -> Actor:
    """
    创建一个玩家角色实例

    Returns:
        Actor: 玩家角色实例
    """
    return create_actor(
        name="角色.玩家.XYZ",
        character_sheet_name="player",
        kick_off_message="",
        character_stats=CharacterStats(base_dexterity=1),
        type=ActorType.ALLY.value,
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        actor_profile="你是无意间从现实世界的电脑游戏中穿越到这个世界的玩家XYZ，知道这里不是真实的世界，而是一个由AI生成的奇幻冒险环境。",
        appearance="""看不出真实年龄，穿着似乎随时都在变化，但又完美融入这个世界，毫无违和感。 """,
        global_game_mechanics=FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
    )
