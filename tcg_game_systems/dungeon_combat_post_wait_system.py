from loguru import logger
from components.components_v_0_0_1 import DungeonComponent, CombatAttributesComponent
from entitas import ExecuteProcessor  # type: ignore
from overrides import override
from typing import final
from game.tcg_game import TCGGame
from extended_systems.combat_system import CombatResult


#######################################################################################################################################
@final
class DungeonCombatPostWaitSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    #######################################################################################################################################
    @override
    def execute(self) -> None:
        latest_combat = self._game.combat_system.latest_combat
        if not latest_combat.is_post_wait:
            return

        if latest_combat.result == CombatResult.HERO_WIN:
            self._resolve_hero_win()
        elif latest_combat.result == CombatResult.HERO_LOSE:
            self._resolve_hero_lose()
        else:
            assert False, "不可能出现的情况！"

    #######################################################################################################################################
    def _resolve_hero_win(self) -> None:

        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "player_entity 不可能为空！"
        assert player_entity.has(
            CombatAttributesComponent
        ), "player_entity 必须有 CombatAttributesComponent！"

        stage_entity = self._game.safe_get_stage_entity(player_entity)
        assert stage_entity is not None, "stage_entity 不可能为空！"
        assert stage_entity.has(
            DungeonComponent
        ), "stage_entity 必须有 DungeonComponent！"

        next_stage = self._game.dungeon_system.get_next_dungeon_level(
            stage_entity._name
        )

        if next_stage is None:
            logger.info("没有下一关，你胜利了，应该返回营地！！！！")
        else:
            logger.info(f"下一关为：{next_stage.name}，可以进入！！！！")

    #######################################################################################################################################
    def _resolve_hero_lose(self) -> None:
        logger.info("英雄失败，应该返回营地！！！！")

    #######################################################################################################################################
