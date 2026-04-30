"""战斗相关模型定义

包含战斗状态、战斗结果、战斗回合与战斗实例核心模型。
状态效果与卡牌相关模型见 cards.py。
"""

from enum import IntEnum, unique
from typing import List, Optional, final
from pydantic import BaseModel, Field
from .cards import Card, CardTargetType, StatusEffect, StatusEffectPhase  # noqa: F401


###############################################################################################################################################
# 战斗状态枚举
@final
@unique
class CombatState(IntEnum):
    NONE = 0  # 无状态
    INITIALIZATION = 1  # 初始化，需要同步一些数据与状态
    ONGOING = 2  # 运行中，不断进行战斗推理
    COMPLETE = 3  # 结束，需要进行结算
    POST_COMBAT = 4  # 战斗等待进入新一轮战斗或者回家


###############################################################################################################################################
# 表示战斗的状态
@final
@unique
class CombatResult(IntEnum):
    NONE = 0  # 无结果
    WIN = 1  # 胜利
    LOSE = 2  # 失败


###############################################################################################################################################
@final
class Round(BaseModel):
    """战斗回合"""

    completed_actors: List[str] = []  # 已完成出牌的角色名称（按出手顺序追加，允许重复）
    actor_order_snapshots: List[List[str]] = Field(
        default_factory=list
    )  # 每次回合开始时的有行动力角色快照（去重、按优先级排列）；由 CombatRoundTransitionSystem 写入
    current_turn_actor_name: Optional[str] = (
        None  # 当前 turn 应行动的角色名；由系统写入，供 TUI 等无 ECS 访问的消费点读取
    )
    is_completed: bool = False  # 回合结束标记；由 CombatRoundCompletionSystem 写入
    combat_log: List[str] = []  # 战斗计算日志，每次出手追加一条
    narrative: List[str] = []  # 叙事文本/演出描述，每次出手追加一条


###############################################################################################################################################
@final
class Combat(BaseModel):
    """战斗实例"""

    name: str
    state: CombatState = CombatState.NONE
    result: CombatResult = CombatResult.NONE
    rounds: List[Round] = []
    retreated: bool = False  # 是否通过撤退结束本次战斗


###############################################################################################################################################
