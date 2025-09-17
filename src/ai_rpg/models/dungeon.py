from enum import IntEnum, unique
from typing import List, Optional, final
from loguru import logger
from pydantic import BaseModel, Field
from .objects import Actor, Stage


###############################################################################################################################################
# 表示战斗的状态 Phase
@final
@unique
class CombatPhase(IntEnum):
    NONE = (0,)
    KICK_OFF = (1,)  # 初始化，需要同步一些数据与状态
    ONGOING = (2,)  # 运行中，不断进行战斗推理
    COMPLETE = 3  # 结束，需要进行结算
    POST_WAIT = 4  # 战斗等待进入新一轮战斗或者回家


###############################################################################################################################################
# 表示战斗的状态
@final
@unique
class CombatResult(IntEnum):
    NONE = (0,)
    HERO_WIN = (1,)  # 胜利
    HERO_LOSE = (2,)  # 失败


###############################################################################################################################################
# 技能产生的影响。
@final
class StatusEffect(BaseModel):
    name: str = Field(..., description="效果名称")
    description: str = Field(..., description="效果描述")
    duration: int = Field(..., description="持续回合数")


###############################################################################################################################################
@final
class Skill(BaseModel):
    name: str = Field(..., description="此技能名称")
    description: str = Field(..., description="此技能描述")
    # effect: str = Field(..., description="此技能产生的效果以及造成的影响")
    target: str = Field(default="", description="技能的目标")


###############################################################################################################################################
# 表示一个回合
@final
class Round(BaseModel):
    tag: str
    round_turns: List[str]
    environment: str = ""
    calculation: str = ""
    performance: str = ""

    @property
    def has_ended(self) -> bool:
        return (
            len(self.round_turns) > 0
            and self.calculation != ""
            and self.performance != ""
        )


###############################################################################################################################################
# 表示一个战斗
@final
class Combat(BaseModel):
    name: str
    phase: CombatPhase = CombatPhase.NONE
    result: CombatResult = CombatResult.NONE
    rounds: List[Round] = []


###############################################################################################################################################


@final
class Engagement(BaseModel):
    combats: List[Combat] = []

    ###############################################################################################################################################
    @property
    def last_combat(self) -> Combat:
        assert len(self.combats) > 0
        if len(self.combats) == 0:
            return Combat(name="")

        return self.combats[-1]

    ###############################################################################################################################################
    @property
    def rounds(self) -> List[Round]:
        return self.last_combat.rounds

    ###############################################################################################################################################
    @property
    def last_round(self) -> Round:
        assert len(self.rounds) > 0
        if len(self.rounds) == 0:
            return Round(tag="", round_turns=[])

        return self.rounds[-1]

    ###############################################################################################################################################
    @property
    def combat_result(self) -> CombatResult:
        return self.last_combat.result

    ###############################################################################################################################################
    @property
    def combat_phase(self) -> CombatPhase:
        return self.last_combat.phase

    ###############################################################################################################################################
    def new_round(self, round_turns: List[str]) -> Round:
        round = Round(
            tag=f"round_{len(self.last_combat.rounds) + 1}",
            round_turns=round_turns,
        )
        self.last_combat.rounds.append(round)
        logger.debug(f"新的回合开始 = {len(self.last_combat.rounds)}")
        return round

    ###############################################################################################################################################
    @property
    def is_on_going_phase(self) -> bool:
        return self.combat_phase == CombatPhase.ONGOING

    ###############################################################################################################################################
    @property
    def is_complete_phase(self) -> bool:
        return self.combat_phase == CombatPhase.COMPLETE

    ###############################################################################################################################################
    @property
    def is_kickoff_phase(self) -> bool:
        return self.combat_phase == CombatPhase.KICK_OFF

    ###############################################################################################################################################
    @property
    def is_post_wait_phase(self) -> bool:
        return self.combat_phase == CombatPhase.POST_WAIT

    ###############################################################################################################################################
    @property
    def has_hero_won(self) -> bool:
        return self.combat_result == CombatResult.HERO_WIN

    ###############################################################################################################################################
    @property
    def has_hero_lost(self) -> bool:
        return self.combat_result == CombatResult.HERO_LOSE

    ###############################################################################################################################################
    # 启动一个战斗！！！ 注意状态转移
    def combat_kickoff(self, combat: Combat) -> None:
        assert combat.phase == CombatPhase.NONE
        combat.phase = CombatPhase.KICK_OFF
        self.combats.append(combat)

    ###############################################################################################################################################
    def combat_ongoing(self) -> None:
        assert self.combat_phase == CombatPhase.KICK_OFF
        assert self.combat_result == CombatResult.NONE
        self.last_combat.phase = CombatPhase.ONGOING

    ###############################################################################################################################################
    def combat_complete(self, result: CombatResult) -> None:
        # 设置战斗结束阶段！
        assert self.combat_phase == CombatPhase.ONGOING
        assert result == CombatResult.HERO_WIN or result == CombatResult.HERO_LOSE
        assert self.combat_result == CombatResult.NONE

        # "战斗已经结束"
        self.last_combat.phase = CombatPhase.COMPLETE
        # 设置战斗结果！
        self.last_combat.result = result

    ###############################################################################################################################################
    def combat_post_wait(self) -> None:
        assert (
            self.combat_result == CombatResult.HERO_WIN
            or self.combat_result == CombatResult.HERO_LOSE
        )
        assert self.combat_phase == CombatPhase.COMPLETE

        # 设置战斗等待阶段！
        self.last_combat.phase = CombatPhase.POST_WAIT

    ###############################################################################################################################################


###############################################################################################################################################
# TODO, 临时的，先管理下。
@final
class Dungeon(BaseModel):
    name: str
    levels: List[Stage] = []
    engagement: Engagement = Engagement()
    position: int = -1

    @property
    def actors(self) -> List[Actor]:
        return [actor for stage in self.levels for actor in stage.actors]

    ########################################################################################################################
    def current_level(self) -> Optional[Stage]:
        if len(self.levels) == 0:
            logger.warning("地下城系统为空！")
            return None

        if not self._validate_position(self.position):
            logger.warning("当前地下城关卡已经完成！或者尚未开始！")
            return None

        return self.levels[self.position]

    ########################################################################################################################
    def next_level(self) -> Optional[Stage]:

        if len(self.levels) == 0:
            logger.warning("地下城系统为空！")
            return None

        if not self._validate_position(self.position):
            logger.warning("当前地下城关卡已经完成！或者尚未开始！")
            return None

        return (
            self.levels[self.position + 1]
            if self.position + 1 < len(self.levels)
            else None
        )

    ########################################################################################################################
    def advance_level(self) -> bool:

        if len(self.levels) == 0:
            logger.warning("地下城系统为空！")
            return False

        if not self._validate_position(self.position):
            logger.warning("当前地下城关卡已经完成！或者尚未开始！")
            return False

        self.position += 1
        return True

    ########################################################################################################################
    def _validate_position(self, position: int) -> bool:
        return position >= 0 and position < len(self.levels)

    ########################################################################################################################
