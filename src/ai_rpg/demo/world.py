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
    Blueprint,
    WeaponItem,
    EquipmentItem,
)
from .actor_warrior import create_actor_warrior
from .actor_wizard import create_actor_wizard
from .actor_player import create_actor_player
from .global_settings import FANTASY_WORLD_RPG_CAMPAIGN_SETTING
from .stage_ally_manor import (
    create_demo_ally_safe_room,
    create_demo_ally_dining_room,
    create_stage_monitoring_house,
)


#######################################################################################################################
def create_demo_game_world_blueprint1(game_name: str) -> Blueprint:
    """
    创建演示游戏世界Blueprint实例 - 双角色版本。

    该函数创建一个包含战士和法师两个角色的完整游戏世界，
    包含英雄营地和英雄餐厅两个场景。两个角色为同伴关系,
    各自有不同的游戏目标。

    Args:
        game_name: 游戏世界的名称

    Returns:
        Blueprint: 初始化完成的游戏世界实例，包含:
            - 2个角色(战士和法师)
            - 2个场景(英雄营地和英雄餐厅)
            - 角色的初始kick_off_message
            - 预设的战役设定

    角色目标:
        - 战士: 以自由卫士身份磨砺武技，探索遗迹寻找压制时间裂隙的方法并为死去的战友复仇
        - 法师: 通过破解裂隙遗迹中的符文机械秘密,找到平息魔网紊乱危机的方法
    """

    # 创建英雄营地场景和角色
    actor_warrior = create_actor_warrior()
    actor_wizard = create_actor_wizard()

    # 创建场景
    stage_ally_safe_room = create_demo_ally_safe_room()
    stage_ally_dining_room = create_demo_ally_dining_room()
    stage_monitoring_room = create_stage_monitoring_house()

    # 设置关系和消息
    stage_ally_safe_room.actors = [actor_warrior, actor_wizard]
    # 设置角色的初始状态
    assert actor_warrior.kick_off_message == "", "战士角色的kick_off_message应为空"
    actor_warrior.kick_off_message = f"""# 游戏启动！告诉我你是谁？请说出你的全名。并说出你的目标(回答简短)。你的目标是: 以自由卫士身份磨砺武技，探索裂隙遗迹寻找压制时空裂隙出现的方法并为死去的战友复仇。"""

    assert actor_wizard.kick_off_message == "", "法师角色的kick_off_message应为空"
    actor_wizard.kick_off_message = f"""# 游戏启动！告诉我你是谁？请说出你的全名。并说出你的目标(回答简短)。你的目标是: 通过破解裂隙遗迹中的符文机械秘密,找到平息魔网紊乱危机和压制时空裂隙出现的方法。"""

    # 设置英雄营地场景的初始状态
    stage_ally_safe_room.kick_off_message = f"""# # 游戏启动! 以第三人称视角，直接描写场景内部的可见环境。
        
使用纯粹的感官描写：视觉、听觉、嗅觉、触觉等具体细节。
输出为单段紧凑文本，不使用换行或空行。"""

    # 设置英雄餐厅场景的初始状态
    stage_ally_dining_room.kick_off_message = f"""# 游戏启动! 以第三人称视角，直接描写场景内部的可见环境。
        
使用纯粹的感官描写：视觉、听觉、嗅觉、触觉等具体细节。
输出为单段紧凑文本，不使用换行或空行。

## 环境叙事基调
餐馆里弥漫着美食的香气，模糊的人影在木桌间交错，嘈杂的交谈声混成低沉的背景音。
这些人影是环境氛围的一部分，作为整体存在感呈现，不应被描述为具体的个体或互动行为。"""

    # 创建世界
    world_blueprint = Blueprint(
        name=game_name,
        player_actor=actor_warrior.name,  # 玩家角色为战士
        player_only_stage=stage_monitoring_room.name,
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        stages=[],
        world_systems=[],
    )

    # 设置世界场景
    world_blueprint.stages = [
        stage_ally_safe_room,
        stage_ally_dining_room,
        stage_monitoring_room,
    ]

    # 添加世界系统
    world_blueprint.world_systems = []

    # 返回
    return world_blueprint


#######################################################################################################################


#######################################################################################################################
def create_demo_game_world_blueprint2(game_name: str) -> Blueprint:
    """
    创建演示游戏世界Blueprint实例 - 单角色版本。

    该函数创建一个只包含战士角色的简化游戏世界，
    只有英雄营地一个场景。适合单人游戏或测试场景。

    Args:
        game_name: 游戏世界的名称

    Returns:
        Blueprint: 初始化完成的游戏世界实例，包含:
            - 1个角色(战士)
            - 1个场景(英雄营地)
            - 角色的初始kick_off_message
            - 预设的战役设定

    角色目标:
        - 战士: 以自由卫士身份磨砺武技，探索裂隙遗迹寻找压制时空裂隙出现的方法并为死去的战友复仇。
    """

    # 测试战士角色
    actor_warrior = create_actor_warrior()
    assert actor_warrior.kick_off_message == "", "战士角色的kick_off_message应为空"
    actor_warrior.kick_off_message = f"""# 游戏启动！告诉我你是谁？请说出你的全名。并说出你的目标(回答简短)。你的目标是: 以自由卫士身份磨砺武技，探索裂隙遗迹寻找压制时空裂隙出现的方法并为死去的战友复仇。"""
    # actor_warrior.character_stats.attack = 100000
    # 测试法师角色
    # actor_wizard = create_actor_wizard()
    # assert actor_wizard.kick_off_message == "", "法师角色的kick_off_message应为空"
    # actor_wizard.kick_off_message = f"""# 游戏启动！告诉我你是谁？请说出你的全名。并说出你的目标(回答简短)。你的目标是: 通过破解裂隙遗迹中的符文机械秘密,找到平息魔网紊乱危机和压制时空裂隙出现的方法。"""

    # 添加战士测试装备
    actor_warrior.items.extend(
        [
            WeaponItem(
                name="武器.长剑.晨曦之刃",
                uuid="",
                description="传说中的圣剑，剑身泛着淡金色的曙光，剑柄镶嵌着太阳纹章宝石",
                count=1,
            ),
            # 战士测试防具
            EquipmentItem(
                name="防具.战甲.裂隙守护者之铠",
                uuid="",
                description="厚重的深灰色板甲，肩甲和胸甲上刻有抗魔法符文，散发微弱的蓝色光芒。配有全覆盖的金属面罩（完全封闭整个头部，不露出任何头发、面容、下巴），面罩表面刻有狮首浮雕，额头处镶嵌一颗小型红宝石",
                count=1,
            ),
            # 战士测试饰品
            # Item(
            #     name="饰品.护符.战神之证",
            #     uuid="",
            #     type=ItemType.ACCESSORY,
            #     description="黑铁打造的护符，挂在腰间的皮革腰带上，护符中央镶嵌着红色晶石",
            #     count=1,
            # ),
        ]
    )

    # 创建场景
    stage_monitoring_house = create_stage_monitoring_house()

    # 设置关系和消息
    stage_monitoring_house.actors = [actor_warrior]

    # 创建世界
    world_blueprint = Blueprint(
        name=game_name,
        player_actor=actor_warrior.name,  # 玩家角色为战士
        # player_actor=actor_wizard.name,  # 玩家角色为法师
        player_only_stage=stage_monitoring_house.name,
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        stages=[],
        world_systems=[],
    )

    # 设置英雄营地场景的初始状态
    world_blueprint.stages = [stage_monitoring_house]

    # 添加世界系统
    world_blueprint.world_systems = []

    # 返回
    return world_blueprint


###############################################################################################################################
def create_demo_game_world_blueprint3(game_name: str) -> Blueprint:
    """
    创建演示游戏世界Blueprint实例 - 玩家角色版本。

    该函数创建一个包含玩家角色的完整游戏世界，
    包含英雄营地和英雄餐厅两个场景。玩家角色具备特殊技能。

    Args:
        game_name: 游戏世界的名称
    Returns:
        Blueprint: 初始化完成的游戏世界实例，包含:
            - 1个玩家角色
            - 1个战士角色
            - 1个法师角色
            - 3个场景(英雄营地、英雄餐厅和监控室)
            - 角色的初始kick_off_message
            - 预设的战役设定
    角色目标:
        - 玩家角色: 利用穿越者身份和特殊技能,探索裂隙遗迹,寻找压制时空裂隙出现的方法,并揭开这个世界的秘密。
        - 战士: 以自由卫士身份磨砺武技，探索裂隙遗迹寻找压制时空裂隙出现的方法并为死去的战友复仇。
    """

    # 创建角色
    actor_warrior = create_actor_warrior()
    actor_player = create_actor_player()
    actor_wizard = create_actor_wizard()
    assert actor_warrior.kick_off_message == "", "战士角色的kick_off_message应为空"
    actor_warrior.kick_off_message = f"""# 游戏启动！告诉我你是谁？请说出你的全名。并说出你的目标(回答简短)。你的目标是: 以自由卫士身份磨砺武技，探索裂隙遗迹寻找压制时空裂隙出现的方法并为死去的战友复仇。"""
    assert actor_wizard.kick_off_message == "", "玩家角色的kick_off_message应为空"
    actor_wizard.kick_off_message = f"""# 游戏启动！告诉我你是谁？请说出你的全名。并说出你的目标(回答简短)。你的目标是: 通过破解裂隙遗迹中的符文机械秘密,找到平息魔网紊乱危机和压制时空裂隙出现的方法。"""
    # 创建场景
    stage_ally_safe_room = create_demo_ally_safe_room()
    stage_ally_dining_room = create_demo_ally_dining_room()
    stage_monitoring_house = create_stage_monitoring_house()

    # 设置英雄营地场景的初始状态
    stage_ally_safe_room.kick_off_message = f"""# # 游戏启动! 以第三人称视角，直接描写场景内部的可见环境。
        
使用纯粹的感官描写：视觉、听觉、嗅觉、触觉等具体细节。
输出为单段紧凑文本，不使用换行或空行。"""

    # 设置英雄餐厅场景的初始状态
    stage_ally_dining_room.kick_off_message = f"""# 游戏启动! 以第三人称视角，直接描写场景内部的可见环境。
        
使用纯粹的感官描写：视觉、听觉、嗅觉、触觉等具体细节。
输出为单段紧凑文本，不使用换行或空行。

## 环境叙事基调
餐馆里弥漫着美食的香气，模糊的人影在木桌间交错，嘈杂的交谈声混成低沉的背景音。
这些人影是环境氛围的一部分，作为整体存在感呈现，不应被描述为具体的个体或互动行为。"""

    # 设置关系和消息
    stage_ally_safe_room.actors = [actor_warrior, actor_wizard, actor_player]
    stage_monitoring_house.actors = []

    # 创建世界
    world_blueprint = Blueprint(
        name=game_name,
        player_actor=actor_player.name,  # 玩家角色为穿越者
        player_only_stage=stage_monitoring_house.name,
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        stages=[],
        world_systems=[],
    )

    # 设置英雄营地场景的初始状态
    world_blueprint.stages = [
        stage_ally_safe_room,
        stage_ally_dining_room,
        stage_monitoring_house,
    ]

    # 添加世界系统
    world_blueprint.world_systems = []

    # 返回
    return world_blueprint
