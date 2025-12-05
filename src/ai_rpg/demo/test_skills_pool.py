"""
测试技能池
用于演示和测试的技能集合。
"""

from typing import Final, List
from ..models import Skill


TEST_SKILLS_POOL: Final[List[Skill]] = [
    Skill(
        name="破空一击",
        description="凝聚全身力量向目标发动猛烈攻击,撕裂空气形成强大冲击波,对敌人造成严重创伤,但会消耗大量体力。",
    ),
    Skill(
        name="铁壁守护",
        description="将意志力凝聚成无形屏障包裹全身,能够抵挡来自各个方向的攻击,维持期间无法移动和反击。",
    ),
    Skill(
        name="环境掌控",
        description="观察并利用周围环境中的一切事物,将其转化为攻击或防御手段,效果取决于当前场景。",
    ),
]
