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
        name="角色.我.耀心",
        character_sheet_name="player",
        kick_off_message="",
        character_stats=CharacterStats(base_dexterity=1),
        type=ActorType.ALLY.value,
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        actor_profile="",
        appearance=""" """,
        global_game_mechanics=FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
    )
