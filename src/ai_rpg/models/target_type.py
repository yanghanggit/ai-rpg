"""目标类型模型定义"""

from enum import StrEnum, unique
from typing import final


###############################################################################################################################################
@final
@unique
class TargetType(StrEnum):
    """目标类型"""

    SINGLE = "single"
    ENEMY_ALL = "enemy_all"
    ENEMY_SPREAD = "enemy_spread"
    ALLY_ALL = "ally_all"
    SELF_ONLY = "self_only"


###############################################################################################################################################
