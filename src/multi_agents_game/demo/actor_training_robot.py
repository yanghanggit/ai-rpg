from ..models import (
    Actor,
    ActorType,
    RPGCharacterProfile,
)
from .campaign_setting import FANTASY_WORLD_RPG_CAMPAIGN_SETTING
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
        actor_profile="""你是一个训练机器人，你不会动，不会使用和生成任何技能，但你是死不掉的，你有无限的血量，""",
        appearance="""你其实长的和稻草人一模一样，但是比稻草人身上多了一些金属盔甲，你被绑在一根柱子上。""",
    )
