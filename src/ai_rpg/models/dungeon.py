from enum import IntEnum, unique
from typing import List, Optional, final
from loguru import logger
from pydantic import BaseModel
from .entities import Actor, Stage, CharacterStats
from .image import GeneratedImage


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
    """状态效果（增益/减益）

    字段说明：
    - name: 状态效果名称
    - category: 分类（增益/减益/复合/条件触发/环境）
    - manifestation: 表现（第一人称描述具体表现）
    - effect: 效果（数值影响）
    """

    name: str
    category: str  # 分类：增益 | 减益 | 复合 | 条件触发 | 环境
    manifestation: str  # 表现：第一人称描述具体表现
    effect: str  # 效果：数值影响（±X点攻击力/防御力）

    @property
    def formatted_description(self) -> str:
        """自动合成三段式 description（用于向后兼容）

        Returns:
            格式化的三段式描述字符串
        """
        return f"【{self.category}】\n{self.manifestation}\n{self.effect}"


###############################################################################################################################################
@final
class Card(BaseModel):
    """卡牌模型"""

    name: str
    action: str  # 第一人称行动叙事描述
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

    action_order: List[str]  # 行动顺序，按顺序记录角色名称
    combat_log: str = ""  # 战斗计算日志
    narrative: str = ""  # 叙事文本/演出描述

    @property
    def is_round_completed(self) -> bool:
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
    retreated: bool = False  # 是否通过撤退结束本次战斗


###############################################################################################################################################
@final
class DungeonRoom(BaseModel):
    """地下城房间（关卡包装）"""

    stage: Stage  # 必须，对应关卡场景
    combat: Combat = Combat(name="")  # 当前房间的战斗数据，默认为空战斗（state=NONE）
    image: GeneratedImage = GeneratedImage()  # 当前房间的文生图数据，默认为空


###############################################################################################################################################
@final
class Dungeon(BaseModel):
    """地下城模型"""

    name: str
    rooms: List[DungeonRoom]
    description: str
    current_room_index: int = -1  # 当前所在房间索引，初始为 -1，表示尚未进入任何房间
    setup_entities: bool = (
        False  # 是否已经根据模型创建了实体（敌人和场景），默认 False，创建后置 True
    )
    image: GeneratedImage = GeneratedImage()  # 地下城封面文生图数据，默认为空

    ########################################################################################################################
    @property
    def actors(self) -> List[Actor]:
        return [actor for room in self.rooms for actor in room.stage.actors]

    ########################################################################################################################
    @property
    def current_room(self) -> Optional[DungeonRoom]:
        if not self._is_valid_room_index(self.current_room_index):
            return None
        return self.rooms[self.current_room_index]

    ########################################################################################################################
    # ============ 战斗状态代理（内联自原 CombatSequence） ============
    ########################################################################################################################
    @property
    def current_combat(self) -> Optional[Combat]:
        if self.current_room is None:
            return None
        return self.current_room.combat

    ########################################################################################################################
    @property
    def current_rounds(self) -> Optional[List[Round]]:
        if self.current_combat is None:
            return None
        return self.current_combat.rounds

    ########################################################################################################################
    @property
    def latest_round(self) -> Optional[Round]:
        if self.current_combat is None:
            return None
        if len(self.current_combat.rounds) == 0:
            return None
        return self.current_combat.rounds[-1]

    ########################################################################################################################
    @property
    def current_result(self) -> Optional[CombatResult]:
        if self.current_combat is None:
            return None
        return self.current_combat.result

    ########################################################################################################################
    @property
    def current_state(self) -> Optional[CombatState]:
        if self.current_combat is None:
            return None
        return self.current_combat.state

    ########################################################################################################################
    @property
    def is_ongoing(self) -> bool:
        if self.current_room is None:
            return False
        return self.current_room.combat.state == CombatState.ONGOING

    ########################################################################################################################
    @property
    def is_combat_completed(self) -> bool:
        if self.current_room is None:
            return False
        return self.current_room.combat.state == CombatState.COMPLETE

    ########################################################################################################################
    @property
    def is_initializing(self) -> bool:
        if self.current_room is None:
            return False
        return self.current_room.combat.state == CombatState.INITIALIZATION

    ########################################################################################################################
    @property
    def is_post_combat(self) -> bool:
        if self.current_room is None:
            return False
        return self.current_room.combat.state == CombatState.POST_COMBAT

    ########################################################################################################################
    @property
    def is_won(self) -> bool:
        if self.current_room is None:
            return False
        return self.current_room.combat.result == CombatResult.WIN

    ########################################################################################################################
    @property
    def is_lost(self) -> bool:
        if self.current_room is None:
            return False
        return self.current_room.combat.result == CombatResult.LOSE

    ########################################################################################################################
    def start_combat(self, combat: Combat) -> None:
        """启动战斗，设置当前房间的战斗为初始化状态"""
        assert self.current_room is not None, "当前没有有效的房间"
        assert combat.state == CombatState.NONE
        assert (
            self.current_room.combat.state == CombatState.NONE
        ), "当前房间已存在战斗，不能重复创建！"
        combat.state = CombatState.INITIALIZATION
        self.current_room.combat = combat

    ########################################################################################################################
    def complete_combat(self, result: CombatResult) -> None:
        """完成战斗，设置结果"""
        assert self.current_room is not None, "当前没有有效的房间"
        assert self.current_room.combat.state == CombatState.ONGOING
        assert result == CombatResult.WIN or result == CombatResult.LOSE
        assert self.current_room.combat.result == CombatResult.NONE
        self.current_room.combat.state = CombatState.COMPLETE
        self.current_room.combat.result = result

    ########################################################################################################################
    def transition_to_ongoing(self) -> None:
        """将战斗状态转换为进行中"""
        assert self.current_room is not None, "当前没有有效的房间"
        assert self.current_room.combat.state == CombatState.INITIALIZATION
        assert self.current_room.combat.result == CombatResult.NONE
        self.current_room.combat.state = CombatState.ONGOING

    ########################################################################################################################
    def transition_to_post_combat(self) -> None:
        """将战斗状态转换为战后阶段"""
        assert self.current_room is not None, "当前没有有效的房间"
        assert self.current_room.combat.result in (CombatResult.WIN, CombatResult.LOSE)
        assert self.current_room.combat.state == CombatState.COMPLETE
        self.current_room.combat.state = CombatState.POST_COMBAT

    ########################################################################################################################
    # ============ 关卡导航 ============
    ########################################################################################################################
    def get_current_stage(self) -> Optional[Stage]:
        """获取当前关卡"""
        if len(self.rooms) == 0:
            logger.warning("地下城系统为空！")
            return None

        if not self._is_valid_room_index(self.current_room_index):
            logger.warning("当前地下城关卡已经完成！或者尚未开始！")
            return None

        return self.rooms[self.current_room_index].stage

    ########################################################################################################################
    def peek_next_stage(self) -> Optional[Stage]:
        """预览下一关卡"""
        if len(self.rooms) == 0:
            logger.warning("地下城系统为空！")
            return None

        if not self._is_valid_room_index(self.current_room_index):
            logger.warning("当前地下城关卡已经完成！或者尚未开始！")
            return None

        return (
            self.rooms[self.current_room_index + 1].stage
            if self.current_room_index + 1 < len(self.rooms)
            else None
        )

    ########################################################################################################################
    def advance_to_next_stage(self) -> Optional[Stage]:
        """前进到下一关卡"""
        if len(self.rooms) == 0:
            logger.warning("地下城系统为空！")
            return None

        if not self._is_valid_room_index(self.current_room_index):
            logger.warning("当前地下城关卡已经完成！或者尚未开始！")
            return None

        self.current_room_index += 1
        return self.get_current_stage()

    ########################################################################################################################
    def _is_valid_room_index(self, position: int) -> bool:
        return position >= 0 and position < len(self.rooms)

    ########################################################################################################################
