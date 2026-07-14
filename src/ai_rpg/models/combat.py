"""战斗相关模型定义

包含战斗状态、战斗结果、战斗回合与战斗实例核心模型。
状态效果与卡牌相关模型见 cards.py。
"""

from enum import IntEnum, unique
from typing import List, Optional, final
from pydantic import BaseModel


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
    action_order: List[str] = (
        []
    )  # 回合开始时确定的行动顺序快照（去重、按优先级排列）；写入后本回合内不再变动
    current_actor: Optional[str] = (
        None  # 当前 turn 应行动的角色名；由系统写入，供 TUI 等无 ECS 访问的消费点读取
    )
    is_completed: bool = False  # 回合结束标记；
    draw_completed: bool = False  # 抽牌阶段结束标记；
    cards_combat_log: List[str] = []  # 出牌战斗日志，每次 PlayCardsAction 追加一条
    cards_narrative: List[str] = []  # 出牌叙事文本，每次 PlayCardsAction 追加一条
    consumable_combat_log: List[str] = (
        []
    )  # 消耗品战斗日志，每次 UseConsumableItemAction 追加一条
    consumable_narrative: List[str] = (
        []
    )  # 消耗品叙事文本，每次 UseConsumableItemAction 追加一条
    consumable_use_count: int = 0  # 本回合消耗品使用次数
    gear_combat_log: List[str] = []  # 装备战斗日志，每次 UseGearItemAction 追加一条
    gear_narrative: List[str] = []  # 装备叙事文本，每次 UseGearItemAction 追加一条
    gear_use_count: int = 0  # 本回合装备使用次数


###############################################################################################################################################
@final
class Combat(BaseModel):
    """战斗实例"""

    name: str
    state: CombatState = CombatState.NONE
    result: CombatResult = CombatResult.NONE
    rounds: List[Round] = []
    retreated: bool = False  # 是否通过撤退结束本次战斗

    ########################################################################################################################
    @property
    def is_ongoing(self) -> bool:
        return self.state == CombatState.ONGOING

    ########################################################################################################################
    @property
    def is_combat_completed(self) -> bool:
        return self.state == CombatState.COMPLETE

    ########################################################################################################################
    @property
    def is_initializing(self) -> bool:
        return self.state == CombatState.INITIALIZATION

    ########################################################################################################################
    @property
    def is_post_combat(self) -> bool:
        return self.state == CombatState.POST_COMBAT

    ########################################################################################################################
    @property
    def is_won(self) -> bool:
        return self.result == CombatResult.WIN

    ########################################################################################################################
    @property
    def is_lost(self) -> bool:
        return self.result == CombatResult.LOSE

    ########################################################################################################################
    @property
    def latest_round(self) -> Optional[Round]:
        if len(self.rounds) == 0:
            return None
        return self.rounds[-1]


###############################################################################################################################################
