from ..models import (
    Boot,
)
from .social_deduction_game_stage import (
    create_demo_werewolf_stage,
)
from .social_deduction_game_actors import (
    create_actor_moderator,
    create_actor_werewolf,
    create_actor_seer,
    create_actor_witch,
    create_actor_villager,
)

from .campaign_setting import (
    WEREWOLF_CAMPAIGN_SETTING,
)


#######################################################################################################################
def create_demo_sd_game_boot(game_name: str) -> Boot:
    # 创建世界
    world_boot = Boot(name=game_name, campaign_setting=WEREWOLF_CAMPAIGN_SETTING)

    # 创建参与角色
    # 主持人
    moderator = create_actor_moderator()

    # 狼人阵营 (2人)
    werewolf1 = create_actor_werewolf("1号玩家")
    werewolf2 = create_actor_werewolf("2号玩家")

    # 好人阵营 (3人)
    seer = create_actor_seer("3号玩家")
    witch = create_actor_witch("4号玩家")
    villager1 = create_actor_villager("5号玩家")
    villager2 = create_actor_villager("6号玩家")

    # 创建游戏场地
    stage_werewolf_stage = create_demo_werewolf_stage()

    # 设置关系和消息
    stage_werewolf_stage.actors = [
        moderator,
        werewolf1,
        werewolf2,
        seer,
        witch,
        villager1,
        villager2,
    ]

    # 设置英雄营地场景的初始状态
    world_boot.stages = [stage_werewolf_stage]

    # 添加世界系统
    world_boot.world_systems = []

    # 返回
    return world_boot


#######################################################################################################################
