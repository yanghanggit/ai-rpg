from ..models import (
    Boot,
)
from .actor_warrior import create_actor_warrior
from .actor_wizard import create_actor_wizard
from .campaign_setting import FANTASY_WORLD_RPG_CAMPAIGN_SETTING
from .stage_heros_camp import (
    create_demo_heros_camp,
    create_demo_heros_restaurant,
)


#######################################################################################################################
def create_demo_game_world_boot1(game_name: str) -> Boot:
    # 创建世界
    world_boot = Boot(
        name=game_name, campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING
    )

    # 创建英雄营地场景和角色
    actor_warrior = create_actor_warrior()
    actor_wizard = create_actor_wizard()

    # 创建场景
    stage_heros_camp = create_demo_heros_camp()
    stage_heros_restaurant = create_demo_heros_restaurant()

    # 设置关系和消息
    stage_heros_camp.actors = [actor_warrior, actor_wizard]

    # 设置角色的初始状态
    assert actor_warrior.kick_off_message == "", "战士角色的kick_off_message应为空"
    actor_warrior.kick_off_message = f"""# 游戏启动！告诉我你是谁？请说出你的全名。并说出你的目标(回答简短)。注意:{actor_wizard.name} 是你的同伴。你的目标是: 以自由卫士身份磨砺武技，追寻圣剑"晨曦之刃"以斩除灾厄。"""

    assert actor_wizard.kick_off_message == "", "法师角色的kick_off_message应为空"
    actor_wizard.kick_off_message = f"""# 游戏启动！告诉我你是谁？请说出你的全名。并说出你的目标(回答简短)。注意:{actor_warrior.name} 是你的同伴。你的目标是: 通过破解古代遗迹中的符文机械秘密,找到平息魔网紊乱危机的方法,证明你的道路才是拯救新奥拉西斯的关键。"""

    # 设置英雄营地场景的初始状态
    world_boot.stages = [stage_heros_camp, stage_heros_restaurant]

    # 添加世界系统
    world_boot.world_systems = []

    # 返回
    return world_boot


#######################################################################################################################


#######################################################################################################################
def create_demo_game_world_boot2(game_name: str) -> Boot:
    # 创建世界
    world_boot = Boot(
        name=game_name, campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING
    )

    # 创建英雄营地场景和角色
    actor_warrior = create_actor_warrior()
    assert actor_warrior.kick_off_message == "", "战士角色的kick_off_message应为空"
    actor_warrior.kick_off_message = f"""# 游戏启动！告诉我你是谁？请说出你的全名。并说出你的目标(回答简短)。你的目标是: 以自由卫士身份磨砺武技，追寻圣剑"晨曦之刃"以斩除灾厄。"""

    # 创建场景
    stage_heros_camp = create_demo_heros_camp()

    # 设置关系和消息
    stage_heros_camp.actors = [actor_warrior]

    # 设置英雄营地场景的初始状态
    world_boot.stages = [stage_heros_camp]

    # 添加世界系统
    world_boot.world_systems = []

    # 返回
    return world_boot
