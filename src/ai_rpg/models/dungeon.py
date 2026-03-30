from datetime import datetime, timezone
from typing import List, Optional, final
from loguru import logger
from pydantic import BaseModel, Field
from .combat import CombatState, CombatResult, Combat, Round
from .entities import Actor, Stage
from .image import GeneratedImage


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
    ecology: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )  # 创建时间戳（UTC）
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
