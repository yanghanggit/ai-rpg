"""
Demo world creation module for AI RPG game.

This module provides factory functions for creating complete game world instances
with pre-configured actors, stages, and world systems. It supports multiple game
scenarios with different character and stage configurations.

主要功能:
- 创建包含双角色(战士+法师)的演示世界
- 创建包含单角色(战士)的演示世界
- 初始化游戏场景、角色关系和开场消息
- 配置战役设定和世界系统
"""

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
    """
    创建演示游戏世界Boot实例 - 双角色版本。

    该函数创建一个包含战士和法师两个角色的完整游戏世界，
    包含英雄营地和英雄餐厅两个场景。两个角色为同伴关系，
    各自有不同的游戏目标。

    Args:
        game_name: 游戏世界的名称

    Returns:
        Boot: 初始化完成的游戏世界实例，包含:
            - 2个角色(战士和法师)
            - 2个场景(英雄营地和英雄餐厅)
            - 角色的初始kick_off_message
            - 预设的战役设定

    角色目标:
        - 战士: 以自由卫士身份磨砺武技，探索遗迹寻找压制遗迹变异的方法并为死去的战友复仇
        - 法师: 通过破解古代遗迹中的符文机械秘密,找到平息魔网紊乱危机的方法
    """
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
    actor_warrior.kick_off_message = f"""# 游戏启动！告诉我你是谁？请说出你的全名。并说出你的目标(回答简短)。注意:{actor_wizard.name} 是你的同伴。你的目标是: 以自由卫士身份磨砺武技，探索遗迹寻找压制遗迹变异的方法并为死去的战友复仇。"""

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
    """
    创建演示游戏世界Boot实例 - 单角色版本。

    该函数创建一个只包含战士角色的简化游戏世界，
    只有英雄营地一个场景。适合单人游戏或测试场景。

    Args:
        game_name: 游戏世界的名称

    Returns:
        Boot: 初始化完成的游戏世界实例，包含:
            - 1个角色(战士)
            - 1个场景(英雄营地)
            - 角色的初始kick_off_message
            - 预设的战役设定

    角色目标:
        - 战士: 以自由卫士身份磨砺武技，追寻圣剑"晨曦之刃"以斩除灾厄
    """
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
