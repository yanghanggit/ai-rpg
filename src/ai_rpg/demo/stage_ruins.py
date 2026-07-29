"""
沙漠残垣场景模块。
"""

from ..models import Stage, StageProfile, StageType, RPG_SYSTEM_RULES
from .global_settings import (
    CAMPAIGN_SETTING,
)
from ..models.entity_factory import (
    create_stage,
)


def create_broken_wall_enclosure() -> Stage:
    """
    创建断壁石室场景实例
    """

    return create_stage(
        name="场景.断壁石室",
        stage_profile=StageProfile(
            name="broken_wall_enclosure",
            type=StageType.HOME,
            profile="""你是沙漠残垣遗迹深处的一处封闭内室，由两面仍完整交汇的厚重石墙构成墙角，顶部横压着一块因地基沉降而错位下滑的巨型石楣，将空间压得低矮而幽暗。
唯一的出入口是石楣与右侧断壁之间遗留的一道窄缝，宽度仅容一人侧身通过。室内地面铺有石板，缝隙中积着细沙，靠墙角的石板面较其他处更为平整干燥。
石楣遮挡了日光与风沙，室内气温明显低于外部，空气中有砂岩特有的干燥矿物气息。外部的风声与沙粒撞击石墙的声响在此处显得遥远而模糊。""",
        ),
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
    )


def create_stone_platform() -> Stage:
    """
    创建石台广场场景实例。
    """

    return create_stage(
        name="场景.石台广场",
        stage_profile=StageProfile(
            name="stone_platform",
            type=StageType.HOME,
            profile="""你是沙漠残垣遗迹中央的开阔地带，地面由大块灰白色石板铺就，石板间的接缝已被风沙填平，部分石板边缘微微翘起。
场地内竖立着数根高矮不一的断柱与风蚀石墩，截面平整，石面上覆有一层薄薄的沙尘。四周是低矮的碎石堆与零散的残垣，视野向远处的沙丘和风蚀岩柱敞开。
日光直射在石台上，石板表面温度极高，靠近断柱底部的背阴处有少量细沙聚积。某些方向的地平线上可见更规整的石堆轮廓。""",
        ),
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
    )
