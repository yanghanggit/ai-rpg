from ..models import (
    Boot,
)

# from .actor_warrior import create_actor_warrior
# from .actor_wizard import create_actor_wizard
# from .campaign_setting import FANTASY_WORLD_RPG_CAMPAIGN_SETTING
from .sd_stage import (
    create_demo_werewolf_stage,
)

from .sd_actors import (
    create_actor_moderator,
    create_actor_werewolf,
    create_actor_seer,
    create_actor_witch,
    create_actor_villager,
)

WEREWOLF_CAMPAIGN_SETTING = """在一个名为月影村的偏远小镇上，夜幕降临时邪恶的狼人开始觅食。
村民们必须在白天通过讨论和投票找出隐藏在他们中间的狼人，而狼人则要在夜晚悄悄消灭村民。
神秘的预言家能够洞察他人的真实身份，智慧的女巫掌握着生死的药剂。
这是一场善恶之间的较量，只有一方能够获得最终的胜利。"""


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
