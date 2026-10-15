"""战斗相关模型定义"""

from enum import IntEnum, StrEnum, unique
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
@unique
class RoundEntryKind(StrEnum):
    """回合内一条记录的种类标记。"""

    CARDS = "cards"  # 出牌 / 回合结束仲裁
    CONSUMABLE = "consumable"  # 使用消耗品
    GEAR = "gear"  # 装备转化
    ARTIFACT = "artifact"  # 场景神器仲裁


###############################################################################################################################################
@final
class RoundEntry(BaseModel):
    """回合内的一条操作记录。

    把原先分散的 log / narrative 合并为同一条目，使跨种类的操作先后顺序可被表达。
    """

    kind: RoundEntryKind  # 种类标记
    log: str  # 战斗数据日志
    narrative: str  # 叙事文本


###############################################################################################################################################
@final
class Round(BaseModel):
    """战斗回合"""

    completed_actors: List[str] = []  # 已完成出牌的角色名称（按出手顺序追加，允许重复）
    action_order: List[str] = (
        []
    )  # 回合开始时确定的行动顺序快照（去重、按优先级排列）；写入后本回合内不再变动
    current_actor: Optional[str] = (
        None  # 当前 turn 应行动的角色名；由系统写入，供无 ECS 访问的消费点读取
    )
    is_completed: bool = False  # 回合结束标记；
    draw_completed: bool = False  # 抽牌阶段结束标记；
    entries: List[RoundEntry] = []  # 本回合内所有操作的记录队列（按发生顺序线性追加）

    ########################################################################################################################
    def record(self, kind: RoundEntryKind, log: str, narrative: str) -> RoundEntry:
        """记录一条本回合内的操作。所有写点统一经由本接口，保证全局先后顺序。"""
        entry = RoundEntry(kind=kind, log=log, narrative=narrative)
        self.entries.append(entry)
        return entry


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

    ########################################################################################################################
    def complete_combat(self, result: CombatResult) -> None:
        """完成战斗，设置结果"""
        assert self.state == CombatState.ONGOING
        assert result == CombatResult.WIN or result == CombatResult.LOSE
        assert self.result == CombatResult.NONE
        self.state = CombatState.COMPLETE
        self.result = result

    ########################################################################################################################
    def transition_to_ongoing(self) -> None:
        """将战斗状态转换为进行中"""
        assert self.state == CombatState.INITIALIZATION
        assert self.result == CombatResult.NONE
        self.state = CombatState.ONGOING

    ########################################################################################################################
    def transition_to_post_combat(self) -> None:
        """将战斗状态转换为战后阶段"""
        assert self.result in (
            CombatResult.WIN,
            CombatResult.LOSE,
        )
        assert self.state == CombatState.COMPLETE
        self.state = CombatState.POST_COMBAT


###############################################################################################################################################
