"""战斗初始化系统（场景侧）：为战斗场景注入战斗专用规则，将战斗状态转换为进行中。"""

from typing import Final, final, override

from loguru import logger

from ..entitas import ExecuteProcessor
from ..game.dbg_game import DBGGame
from ..models import StageDescriptionComponent


###################################################################################################################################################################
@final
class CombatInitStageSystem(ExecuteProcessor):
    """战斗初始化系统（场景侧）：注入战斗专用规则、转换战斗状态为进行中。"""

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ###################################################################################################################################################################
    @override
    async def execute(self) -> None:

        if not self._game.current_dungeon_combat_room.combat.is_initializing:
            logger.debug("当前战斗状态非 initializing，跳过战斗初始化（场景侧）")
            return

        logger.info("战斗初始化（场景侧）开始，正在注入战斗规则并转换战斗状态...")

        # 获取玩家实体，player 所在场景即战斗场景
        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "无法找到玩家实体！"

        # 获取当前场景实体
        current_stage_entity = self._game.resolve_stage_entity(player_entity)
        assert current_stage_entity is not None, "无法找到当前场景实体！"
        assert current_stage_entity.has(
            StageDescriptionComponent
        ), "当前场景实体缺少 StageDescriptionComponent 组件！"

        # 设置战斗为进行中（第一回合将由 CombatRoundTransitionSystem 创建）
        self._game.current_dungeon_combat_room.combat.transition_to_ongoing()
        assert (
            self._game.current_dungeon_combat_room.combat.is_ongoing
        ), "战斗状态转换失败，当前状态非 ONGOING！"


###################################################################################################################################################################
