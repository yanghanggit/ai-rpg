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
    """目标类型

    声明一个战斗行动的打击范围，由 LLM 在生成阶段写入 `target_type` 字段，
    出牌/使用阶段系统据此做目标验证或自动填充。

    当前约束策略：
    - enemy_single：targets 必须恰好包含 1 名存活敌方角色名
    - enemy_all：targets 由系统自动替换为场上全部存活敌方，调用方传入值被忽略
    - enemy_random_multi：targets 由系统预先随机生成，长度 = hit_count，每段独立随机命中一名存活敌方
                          （允许重复命中同一目标）；仲裁系统按段分配结算
    - ally_single / ally_all：暂不约束，targets 由调用方自由传入（占位，后续扩展）
    - self_only：targets 由系统自动替换为施法者自身，调用方传入值被忽略；
                 典型用途：纯防御（提升格挡）、呼吸法（自我恢复）、强化自身 buff 等
                 与 ally_single 的区别：ally_single 可指向任意存活友方，self_only 严格限定为施法者本人
    """

    ENEMY_SINGLE = "enemy_single"
    ENEMY_ALL = "enemy_all"
    ENEMY_RANDOM_MULTI = "enemy_random_multi"
    ALLY_SINGLE = "ally_single"
    ALLY_ALL = "ally_all"
    SELF_ONLY = "self_only"


###############################################################################################################################################
