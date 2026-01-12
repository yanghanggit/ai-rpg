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
from .actor_hunter import create_hunter
from .actor_mystic import create_mystic
from .global_settings import RPG_CAMPAIGN_SETTING
from .stage_village import (
    create_hunter_storage,
    create_village_hall,
    create_shi_family_house,
)


#######################################################################################################################
def create_hunter_mystic_blueprint(game_name: str) -> Blueprint:
    """
    创建演示游戏世界Blueprint实例 - 猎人与术士双角色版本。

    该函数创建一个包含猎人和术士两个角色的完整游戏世界，
    包含猎人备物所、村中议事堂和石氏木屋三个场景。两个角色为同伴关系，
    各自有不同的游戏目标。

    Args:
        game_name: 游戏世界的名称

    Returns:
        Blueprint: 初始化完成的游戏世界实例，包含:
            - 2个角色(猎人和术士)
            - 3个场景(猎人备物所、村中议事堂、石氏木屋)
            - 角色的初始kick_off_message
            - 预设的战役设定

    角色目标:
        - 猎人: 作为石氏猎人家族传人，磨练狩猎技艺，维护桃花源周边山林的生态平衡，
          并探索古先民遗迹的秘密
        - 术士: 通过研究古先民遗迹中的神秘符文，理解古先民引导自然之力的方法，
          并揭示桃花源隐藏的秘密
    """

    # 创建英雄营地场景和角色
    actor_warrior = create_hunter()
    actor_mystic = create_mystic()

    # 创建场景
    stage_hunter_storage = create_hunter_storage()
    stage_village_hall = create_village_hall()
    stage_shi_family_house = create_shi_family_house()

    # 设置关系和消息
    stage_hunter_storage.actors = [actor_warrior, actor_mystic]
    # 设置角色的初始状态
    assert actor_warrior.kick_off_message == "", "战士角色的kick_off_message应为空"
    actor_warrior.kick_off_message = f"""# 游戏启动！告诉我你是谁？请说出你的全名。并说出你的目标(回答简短)。你的目标是: 作为石氏猎人家族传人，磨练狩猎技艺，维护桃花源周边山林的生态平衡，并探索古先民遗迹的秘密。"""

    assert actor_mystic.kick_off_message == "", "法师角色的kick_off_message应为空"
    actor_mystic.kick_off_message = f"""# 游戏启动！告诉我你是谁？请说出你的全名。并说出你的目标(回答简短)。你的目标是: 通过研究古先民遗迹中的神秘符文，理解古先民引导自然之力的方法，并揭示桃花源隐藏的秘密。"""

    # 设置英雄营地场景的初始状态
    stage_hunter_storage.kick_off_message = f"""# 游戏启动! 以第三人称视角，直接描写场景内部的可见环境。
        
使用纯粹的感官描写：视觉、听觉、嗅觉、触觉等具体细节。
输出为单段紧凑文本，不使用换行或空行。"""

    # 设置英雄餐厅场景的初始状态
    stage_village_hall.kick_off_message = f"""# 游戏启动! 以第三人称视角，直接描写场景内部的可见环境。
        
使用纯粹的感官描写：视觉、听觉、嗅觉、触觉等具体细节。
输出为单段紧凑文本，不使用换行或空行。"""

    # 创建世界
    return Blueprint(
        name=game_name,
        player_actor=actor_warrior.name,  # 玩家角色为战士
        player_only_stage=stage_shi_family_house.name,
        campaign_setting=RPG_CAMPAIGN_SETTING,
        stages=[
            stage_hunter_storage,
            stage_village_hall,
            stage_shi_family_house,
        ],
        world_systems=[],
    )


#######################################################################################################################
def create_single_hunter_blueprint(game_name: str) -> Blueprint:
    """
    创建演示游戏世界Blueprint实例 - 单猎人版本。

    该函数创建一个只包含猎人角色的简化游戏世界，
    场景为石氏木屋（玩家专属场景）。适合单人游戏或测试场景。
    猎人配备基础的竹弦狩猎弓和兽皮短衫作为测试装备。

    Args:
        game_name: 游戏世界的名称

    Returns:
        Blueprint: 初始化完成的游戏世界实例，包含:
            - 1个角色(石氏猎人)
            - 1个场景(石氏木屋，玩家专属)
            - 角色的初始kick_off_message
            - 基础猎人装备(竹弦狩猎弓、兽皮短衫)
            - 预设的战役设定

    角色目标:
        - 猎人: 作为石氏猎人家族传人，磨练狩猎技艺，维护桃花源周边山林的生态平衡，
          并探索古先民遗迹的秘密。

    测试装备:
        - 武器: 竹弦狩猎弓（山竹弓臂，山魈筋腱为弦）
        - 防具: 兽皮短衫（窃脂妖兽皮革，硬化兽皮加固）
    """

    # 创建角色: 测试猎人
    actor_hunter = create_hunter()
    assert actor_hunter.kick_off_message == "", "猎人角色的kick_off_message应为空"
    actor_hunter.kick_off_message = f"""# 游戏启动！告诉我你是谁？请说出你的全名。并说出你的目标(回答简短)。你的目标是: 作为石氏猎人家族传人，磨练狩猎技艺，维护桃花源周边山林的生态平衡，并探索古先民遗迹的秘密。"""

    # 添加猎人测试装备
    actor_hunter.items.extend(
        [
            WeaponItem(
                name="武器.竹弦狩猎弓",
                uuid="",
                description="以坚韧的山竹为弓臂，山魈筋腱为弦，弓身刻有简单的兽纹。村中猎人常用的基础装备。",
                count=1,
            ),
            # 猎人测试护具
            EquipmentItem(
                name="防具.兽皮短衫",
                uuid="",
                description="以窃脂妖兽皮革缝制的轻便短衫，胸口和肩部用硬化兽皮加固，腰间系麻绳束带。适合山林间灵活移动。",
                count=1,
            ),
        ]
    )

    # 创建场景
    stage_shi_family_house = create_shi_family_house()

    # 设置关系和消息
    stage_shi_family_house.actors = [actor_hunter]

    # 创建世界
    return Blueprint(
        name=game_name,
        player_actor=actor_hunter.name,  # 玩家角色为战士
        player_only_stage=stage_shi_family_house.name,
        campaign_setting=RPG_CAMPAIGN_SETTING,
        stages=[stage_shi_family_house],
        world_systems=[],
    )


###############################################################################################################################
