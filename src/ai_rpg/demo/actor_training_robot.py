from ..models import (
    Actor,
    ActorType,
    RPGCharacterProfile,
)
from .campaign_setting import (
    FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
    FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
)
from .utils import (
    create_actor,
)


def create_actor_training_robot() -> Actor:
    """
    创建一个训练机器人角色实例

    Returns:
        Actor: 训练机器人角色实例
    """
    return create_actor(
        name="角色.怪物.训练机器人",
        character_sheet_name="training_robot",
        kick_off_message="",
        rpg_character_profile=RPGCharacterProfile(base_dexterity=1),
        type=ActorType.MONSTER,
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        actor_profile="""你是一个训练机器人，只会最基本的防御和攻击，你不会生成观察和利用环境的技能。
         【战斗循环】  
        1. 防御（格挡或减伤，等待敌人出手）。  
        2. 攻击（基础轻攻击或者重击）。
        3. 控场（击晕或限制敌人行动，创造输出机会）。
        4. 攻击（基础轻攻击或者重击）。  
        → 然后再次回到 1. 防御，循环往复。""",
        appearance="""长的和稻草人一模一样，但是身上多了一些金属盔甲，你被绑在一根柱子上,手上只握着一根木棍。""",
        global_game_mechanics=FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
    )
