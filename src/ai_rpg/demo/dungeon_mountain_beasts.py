"""
地下城副本工厂模块

本模块用于创建桃花源世界观下的山林相关地下城副本，包含不同生态层级的怪物挑战。

核心内容：
- create_mountain_beasts_dungeon: 多场景副本，递进式挑战山魈（精怪）与山中虎（大妖）。
- create_tiger_lair_dungeon: 单场景副本，仅挑战山中虎（大妖），适合高难度狩猎。
- create_wild_boar_territory_dungeon: 单场景副本，仅挑战野猪（常物），适合新手练习与基础素材获取。

各副本均采用碎片化环境叙事，突出感官细节，体现东方生态分层与狩猎体验。
"""

from ..models import (
    Dungeon,
    StageProfile,
    StageType,
)
from .actor_mountain_monkey import create_actor_mountain_monkey
from .actor_mountain_tiger import create_actor_mountain_tiger
from .actor_wild_boar import create_actor_wild_boar
from .global_settings import (
    RPG_CAMPAIGN_SETTING,
    RPG_SYSTEM_RULES,
    # RPG_COMBAT_MECHANICS,
)
from .entity_factory import (
    create_stage,
)
from .prompt_templates import PUBLIC_STAGE_KICK_OFF_MESSAGE


def create_mountain_beasts_dungeon() -> Dungeon:
    """
    创建山林妖兽狩猎副本。

    包含两个递进式场景：
    - 山林边缘：精怪级山魈，擅长利用环境物品作战
    - 密林深处：大妖级山中虎，生态链顶点的强大妖兽

    Returns:
        Dungeon: 山林妖兽副本实例
    """
    # 创建山魈栖息地场景（山林边缘）
    stage_forest_edge = create_stage(
        name="场景.山林边缘",
        stage_profile=StageProfile(
            name="forest_edge",
            type=StageType.DUNGEON,
            profile="山脉的山林边缘地带，树木稀疏，地面散落着石块、断枝和干燥的落叶。周围有多处适合攀爬的岩石和树干，视野相对开阔。",
        ),
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        # combat_mechanics=RPG_COMBAT_MECHANICS,
    )

    # 添加山魈作为场景中的敌对角色
    actor_monkey = create_actor_mountain_monkey()

    # 将山魈的生命值设为1，方便测试击杀
    # actor_monkey.character_stats.hp = 1

    # 将山魈添加到场景的角色列表中
    stage_forest_edge.actors = [actor_monkey]

    # 设置场景启动消息，指导游戏如何描写环境
    stage_forest_edge.kick_off_message = PUBLIC_STAGE_KICK_OFF_MESSAGE

    # 创建山中虎领地场景（密林深处）
    stage_deep_forest = create_stage(
        name="场景.密林深处",
        stage_profile=StageProfile(
            name="deep_forest",
            type=StageType.DUNGEON,
            profile="山脉的密林深处，古木参天遮蔽天日，地面铺满厚重的腐叶。粗壮的树干上留有深深的爪痕，周围散布着巨大的兽骨。空气沉闷压抑，弥漫着强烈的兽类气息。",
        ),
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        # combat_mechanics=RPG_COMBAT_MECHANICS,
    )

    # 添加山中虎作为场景中的敌对角色
    actor_tiger = create_actor_mountain_tiger()

    # 将山中虎的生命值设为1，方便测试击杀
    # actor_tiger.character_stats.hp = 1

    # 将山中虎添加到场景的角色列表中
    stage_deep_forest.actors = [actor_tiger]

    # 设置场景启动消息，指导游戏如何描写环境
    stage_deep_forest.kick_off_message = PUBLIC_STAGE_KICK_OFF_MESSAGE

    return Dungeon(
        name="地下城.山林妖兽",
        description="山林边缘出现精怪山魈，密林深处盘踞大妖山中虎。需递进挑战两个生态层级的妖兽，磨练狩猎技艺。注意山魈擅长利用环境作战，山中虎为生态链顶点的强大存在。",
        stages=[
            stage_forest_edge,
            stage_deep_forest,
        ],
    )


def create_tiger_lair_dungeon() -> Dungeon:
    """
    创建山中虎巢穴副本。

    包含单个场景：
    - 密林深处：大妖级山中虎，生态链顶点的强大妖兽

    Returns:
        Dungeon: 山中虎巢穴副本实例
    """
    # 创建山中虎领地场景（密林深处）
    stage_deep_forest = create_stage(
        name="场景.密林深处",
        stage_profile=StageProfile(
            name="deep_forest",
            type=StageType.DUNGEON,
            profile="山脉的密林深处，古木参天遮蔽天日，地面铺满厚重的腐叶。粗壮的树干上留有深深的爪痕，周围散布着巨大的兽骨。空气沉闷压抑，弥漫着强烈的兽类气息。",
        ),
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        # combat_mechanics=RPG_COMBAT_MECHANICS,
    )

    # 添加山中虎作为场景中的敌对角色
    actor_tiger = create_actor_mountain_tiger()

    # 将山中虎的生命值设为1，方便测试击杀
    # actor_tiger.character_stats.hp = 2

    # 准备测试穿透防御的攻击力，所以防御力设高一些
    # actor_tiger.character_stats.defense = 100

    # 将山中虎添加到场景的角色列表中
    stage_deep_forest.actors = [actor_tiger]

    # 设置场景启动消息，指导游戏如何描写环境
    stage_deep_forest.kick_off_message = PUBLIC_STAGE_KICK_OFF_MESSAGE

    return Dungeon(
        name="地下城.山中虎巢穴",
        description="密林深处发现大妖级山中虎的巢穴，这是生态链顶点的强大妖兽。高难度狩猎任务，需谨慎应对其恐怖的攻击力与敏捷身法。",
        stages=[
            stage_deep_forest,
        ],
    )


def create_wild_boar_territory_dungeon() -> Dungeon:
    """
    创建野猪领地副本。

    包含单个场景：
    - 林间空地：常物级野猪，适合初期狩猎练习的基础猎物

    Returns:
        Dungeon: 野猪领地副本实例
    """
    # 创建野猪领地场景（林间空地）
    stage_forest_clearing = create_stage(
        name="场景.林间空地",
        stage_profile=StageProfile(
            name="forest_clearing",
            type=StageType.DUNGEON,
            profile="山脚下的林间空地，树木稀疏，阳光透过树冠洒落。地面覆盖着橡果和野菜，泥土松软留有蹄印。周围灌木丛茂密，散发着野兽粪便和翻土的气味。适合野猪觅食的天然场所。",
        ),
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        # combat_mechanics=RPG_COMBAT_MECHANICS,
    )

    # 添加野猪作为场景中的敌对角色
    actor_boar = create_actor_wild_boar()

    # 将野猪的生命值设为1，方便测试击杀
    # actor_boar.character_stats.hp = 1

    # 将野猪添加到场景的角色列表中
    stage_forest_clearing.actors = [actor_boar]

    # 设置场景启动消息，指导游戏如何描写环境
    stage_forest_clearing.kick_off_message = PUBLIC_STAGE_KICK_OFF_MESSAGE

    return Dungeon(
        name="地下城.野猪领地",
        description="林间空地发现常物级野猪的觅食领地。适合初期狩猎练习，可获取基础兽皮、兽肉等素材。野猪虽为常物但獠牙攻击不可轻视。",
        stages=[
            stage_forest_clearing,
        ],
    )
