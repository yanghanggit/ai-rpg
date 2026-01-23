"""演示世界创建模块

提供工厂函数创建预配置的游戏世界，包括双角色和单角色版本。
"""

from typing import Final
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
from .world_system_player_action_audit import create_player_action_audit


# 公共场景启动消息模板
PUBLIC_STAGE_KICK_OFF_MESSAGE: Final[
    str
] = f"""# 游戏启动! 以第三人称视角，直接描写场景内部的可见环境。
        
使用纯粹的感官描写：视觉、听觉、嗅觉、触觉等具体细节。
输出为单段紧凑文本，不使用换行或空行."""


#######################################################################################################################
def create_hunter_mystic_blueprint(game_name: str) -> Blueprint:
    """
    创建演示游戏世界Blueprint实例 - 猎人与术士双角色版本。

    该函数创建一个包含猎人和术士两个角色的完整游戏世界，
    包含猎人备物所、村中议事堂和石氏木屋三个场景。两个角色为同伴关系,
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
    actor_hunter = create_hunter()

    # 添加猎人测试装备
    actor_hunter.items.extend(
        [
            WeaponItem(
                name="武器.山魈骨猎刀",
                uuid="",
                description="以山魈前臂骨磨制的单刃猎刀，刃长一尺，锋利坚韧。刀柄缠以兽皮，握持稳固。刀身泛着暗黄色的骨质光泽。村中猎人常用的基础装备。",
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

    # 直接使用外观描述，这样就减少一次推理生成。
    actor_hunter.character_sheet.appearance = "一名年近三十的男子，身形精悍，肌肉线条分明，是常年高强度活动留下的痕迹。他的肤色是经年风吹日晒形成的健康褐色。眼神沉静而警觉，下颌蓄着打理整齐的短须，头发在脑后简单束成一个发髻。他穿着一件轻便的短衫，由某种暗红色带细密纹路的皮革制成，胸口与肩部有颜色略深的加固部分，腰间用麻绳束紧。未被衣物覆盖的左肩处，清晰可见三道平行的、已经愈合的旧疤痕。他的右手虎口位置，皮肤因长期摩擦而显得格外粗糙厚实。"

    # 测试攻击力，打的快一点。
    actor_hunter.character_stats.attack = 100000

    # 创建术士角色
    actor_mystic = create_mystic()

    # 创建场景
    stage_hunter_storage = create_hunter_storage()
    stage_village_hall = create_village_hall()
    stage_shi_family_house = create_shi_family_house()

    # 设置关系和消息
    stage_hunter_storage.actors = [actor_hunter, actor_mystic]
    # 设置角色的初始状态
    assert actor_hunter.kick_off_message == "", "猎人角色的kick_off_message应为空"
    actor_hunter.kick_off_message = f"""# 游戏启动！告诉我你是谁？请说出你的全名。并说出你的目标(回答简短)。你的目标是: 作为石氏猎人家族传人，磨练狩猎技艺，维护桃花源周边山林的生态平衡，并探索古先民遗迹的秘密。"""

    assert actor_mystic.kick_off_message == "", "术士角色的kick_off_message应为空"
    actor_mystic.kick_off_message = f"""# 游戏启动！告诉我你是谁？请说出你的全名。并说出你的目标(回答简短)。你的目标是: 通过研究古先民遗迹中的神秘符文，理解古先民引导自然之力的方法，并揭示桃花源隐藏的秘密。"""

    # 设置英雄营地场景的初始状态
    stage_hunter_storage.kick_off_message = PUBLIC_STAGE_KICK_OFF_MESSAGE

    # 设置英雄餐厅场景的初始状态
    stage_village_hall.kick_off_message = PUBLIC_STAGE_KICK_OFF_MESSAGE

    # 设置石氏木屋场景的初始状态
    stage_shi_family_house.kick_off_message = PUBLIC_STAGE_KICK_OFF_MESSAGE

    # 创建世界
    return Blueprint(
        name=game_name,
        player_actor=actor_hunter.name,  # 玩家角色为战士
        player_only_stage=stage_shi_family_house.name,
        campaign_setting=RPG_CAMPAIGN_SETTING,
        stages=[
            stage_hunter_storage,
            stage_village_hall,
            stage_shi_family_house,
        ],
        world_systems=[create_player_action_audit()],
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
    actor_hunter.kick_off_message = f"""# 游戏启动！告诉我你是谁？请说出你的全名。并说出你的目标(回答简短)。你的目标是: 作为石氏猎人家族传人，磨练狩猎技艺，维护桃花源周边山林的生态平衡，并探索古先民遗迹的秘密。而且你最讨厌虎类的妖兽，因为你对其有刻骨铭心的仇恨，你只要见到就会全力发起攻击！"""
    # 而且你最讨厌虎类的妖兽，因为你对其有刻骨铭心的仇恨，你只要见到就会全力发起攻击！

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

    # 测试攻击力，打的快一点。
    actor_hunter.character_stats.attack = 10000

    # 创建场景
    stage_shi_family_house = create_shi_family_house()

    # 添加 启动消息
    stage_shi_family_house.kick_off_message = PUBLIC_STAGE_KICK_OFF_MESSAGE

    # 直接给 外观描述，减少一次推理生成。
    actor_hunter.character_sheet.appearance = """一名年近三十的男子，身形精悍灵活，肌肉线条结实分明，是常年山林活动留下的痕迹。肤色呈健康的褐色，是风吹日晒的结果。他蓄着短须，头发简单束成发髻。眼神沉静而警觉。上身穿着轻便的短衫，由某种带有细密鳞纹的暗褐色皮革缝制，胸口和肩部有颜色略深的硬化皮革加固，腰间用麻绳束带系紧。左肩从短衫领口边缘露出三道平行的、已愈合的淡白色疤痕。右手虎口处有明显的厚茧。他背负着一把以山竹为材、刻有简单兽纹的长弓，弓弦紧绷。"""

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
