"""目标类型模型定义

包含战斗中通用的目标范围声明枚举：TargetType。
可被卡牌（Card）、消耗品（ConsumableItem）等任何需要声明打击范围的实体复用。
"""

from enum import StrEnum, unique
from typing import final


###############################################################################################################################################
@final
@unique
class TargetType(StrEnum):
    """目标类型"""

    ENEMY_SINGLE = "enemy_single"
    ENEMY_ALL = "enemy_all"
    ENEMY_SPREAD = "enemy_spread"
    ALLY_SINGLE = "ally_single"
    ALLY_ALL = "ally_all"
    SELF_ONLY = "self_only"


###############################################################################################################################################
