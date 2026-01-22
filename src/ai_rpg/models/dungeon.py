from enum import IntEnum, unique
from typing import List, Optional, final
from loguru import logger
from pydantic import BaseModel
from .entities import Actor, Stage, CharacterStats


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
class StatusEffect(BaseModel):
    """状态效果（增益/减益、持续伤害/治疗等）"""

    name: str
    description: str


###############################################################################################################################################
@final
class Card(BaseModel):
    """卡牌模型"""

    name: str
    description: str
    stats: CharacterStats  # 卡牌的描述属性
    targets: List[str] = []  # 目标实体名称列表
    status_effects: List[StatusEffect] = []  # 附加状态效果列表
    affixes: List[str] = (
        []
    )  # 词条列表（类似暗黑破坏神的装备词条）, 词条的规则会完整越过draw cards的泛化，而直接进入仲裁，并强制仲裁执行。


###############################################################################################################################################
@final
class Round(BaseModel):
    """战斗回合"""

    tag: str  # 回合标签，记录回合序号等信息
    action_order: List[str]  # 行动顺序，按顺序记录角色名称
    combat_log: str = ""  # 战斗计算日志
    narrative: str = ""  # 叙事文本/演出描述

    @property
    def is_completed(self) -> bool:
        return (
            len(self.action_order) > 0
            and self.combat_log != ""
            and self.narrative != ""
        )


###############################################################################################################################################
@final
class Combat(BaseModel):
    """战斗实例"""

    name: str
    state: CombatState = CombatState.NONE
    result: CombatResult = CombatResult.NONE
    rounds: List[Round] = []


###############################################################################################################################################


@final
class CombatSequence(BaseModel):
    """战斗序列管理器"""

    combats: List[Combat] = []

    ###############################################################################################################################################
    @property
    def current_combat(self) -> Combat:
        assert len(self.combats) > 0
        if len(self.combats) == 0:
            return Combat(name="")

        return self.combats[-1]

    ###############################################################################################################################################
    @property
    def current_rounds(self) -> List[Round]:
        return self.current_combat.rounds

    ###############################################################################################################################################
    @property
    def latest_round(self) -> Round:
        assert len(self.current_rounds) > 0
        if len(self.current_rounds) == 0:
            return Round(tag="", action_order=[])

        return self.current_rounds[-1]

    ###############################################################################################################################################
    @property
    def current_result(self) -> CombatResult:
        return self.current_combat.result

    ###############################################################################################################################################
    @property
    def current_state(self) -> CombatState:
        return self.current_combat.state

    ###############################################################################################################################################
    # ============ 状态查询 ============
    @property
    def is_ongoing(self) -> bool:
        return self.current_state == CombatState.ONGOING

    ###############################################################################################################################################
    @property
    def is_completed(self) -> bool:
        return self.current_state == CombatState.COMPLETE

    ###############################################################################################################################################
    @property
    def is_initializing(self) -> bool:
        return self.current_state == CombatState.INITIALIZATION

    ###############################################################################################################################################
    @property
    def is_post_combat(self) -> bool:
        return self.current_state == CombatState.POST_COMBAT

    ###############################################################################################################################################
    @property
    def is_won(self) -> bool:
        return self.current_result == CombatResult.WIN

    ###############################################################################################################################################
    @property
    def is_lost(self) -> bool:
        return self.current_result == CombatResult.LOSE

    ###############################################################################################################################################
    def get_combat_by_name(self, name: str) -> Optional[Combat]:
        """根据名称查找战斗"""
        for combat in self.combats:
            if combat.name == name:
                return combat
        return None

    ###############################################################################################################################################
    def start_combat(self, combat: Combat) -> None:
        """启动战斗，设置为初始化状态"""
        assert combat.state == CombatState.NONE
        assert (
            self.get_combat_by_name(combat.name) is None
        ), "战斗已经存在，不能重复创建！"

        # 设置战斗启动阶段！
        combat.state = CombatState.INITIALIZATION

        # 添加战斗。
        self.combats.append(combat)

    ###############################################################################################################################################
    def complete_combat(self, result: CombatResult) -> None:
        """完成战斗，设置结果"""
        # 设置战斗结束阶段！
        assert self.current_state == CombatState.ONGOING
        assert result == CombatResult.WIN or result == CombatResult.LOSE
        assert self.current_result == CombatResult.NONE

        # "战斗已经结束"
        self.current_combat.state = CombatState.COMPLETE
        # 设置战斗结果！
        self.current_combat.result = result

    ###############################################################################################################################################
    def transition_to_ongoing(self) -> None:
        """将战斗状态转换为进行中"""
        assert self.current_state == CombatState.INITIALIZATION
        assert self.current_result == CombatResult.NONE
        self.current_combat.state = CombatState.ONGOING

    ###############################################################################################################################################
    def transition_to_post_combat(self) -> None:
        """将战斗状态转换为战后阶段"""
        assert self.is_won or self.is_lost
        assert self.current_state == CombatState.COMPLETE

        # 设置战斗等待阶段！
        self.current_combat.state = CombatState.POST_COMBAT

    ###############################################################################################################################################


###############################################################################################################################################
@final
class Dungeon(BaseModel):
    """地下城模型"""

    name: str
    stages: List[Stage]
    combat_sequence: CombatSequence = CombatSequence()
    current_stage_index: int = -1

    @property
    def actors(self) -> List[Actor]:
        return [actor for stage in self.stages for actor in stage.actors]

    ########################################################################################################################
    def get_current_stage(self) -> Optional[Stage]:
        """获取当前关卡"""
        if len(self.stages) == 0:
            logger.warning("地下城系统为空！")
            return None

        if not self._is_valid_stage_index(self.current_stage_index):
            logger.warning("当前地下城关卡已经完成！或者尚未开始！")
            return None

        return self.stages[self.current_stage_index]

    ########################################################################################################################
    def peek_next_stage(self) -> Optional[Stage]:
        """预览下一关卡"""

        if len(self.stages) == 0:
            logger.warning("地下城系统为空！")
            return None

        if not self._is_valid_stage_index(self.current_stage_index):
            logger.warning("当前地下城关卡已经完成！或者尚未开始！")
            return None

        return (
            self.stages[self.current_stage_index + 1]
            if self.current_stage_index + 1 < len(self.stages)
            else None
        )

    ########################################################################################################################
    def advance_to_next_stage(self) -> bool:
        """前进到下一关卡"""

        if len(self.stages) == 0:
            logger.warning("地下城系统为空！")
            return False

        if not self._is_valid_stage_index(self.current_stage_index):
            logger.warning("当前地下城关卡已经完成！或者尚未开始！")
            return False

        self.current_stage_index += 1
        return True

    ########################################################################################################################
    def _is_valid_stage_index(self, position: int) -> bool:
        return position >= 0 and position < len(self.stages)

    ########################################################################################################################
