from loguru import logger
from components.components_v_0_0_1 import (
    DungeonComponent,
    CombatAttributesComponent,
    HeroComponent,
)
from entitas import ExecuteProcessor, Matcher  # type: ignore
from overrides import override
from typing import final
from game.tcg_game import TCGGame
from extended_systems.combat_system import CombatResult
from models.v_0_0_1 import StageInstance
from game.terminal_tcg_game import TerminalTCGGame


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

            if isinstance(self._game, TerminalTCGGame):
                while True:
                    user_input = input(
                        f"下一关为：{next_stage.name}，可以进入。是否进入？(y/n): "
                    )
                    if user_input == "y":
                        break

            self._next_dungeon_level(next_stage)

    #######################################################################################################################################
    def _next_dungeon_level(self, next_stage: StageInstance) -> None:
        logger.info(f"下一关为：{next_stage.name}，可以进入！！！！")

        heros_entities = self._game.get_group(Matcher(all_of=[HeroComponent])).entities
        assert len(heros_entities) > 0
        if len(heros_entities) == 0:
            logger.error("没有找到英雄!")
            return

        trans_message = (
            f"""# 提示！你准备继续你的冒险，准备进入下一个地下城: {next_stage.name}"""
        )
        for hero_entity in heros_entities:
            # 添加故事
            logger.info(f"添加故事: {hero_entity._name} => {trans_message}")
            self._game.append_human_message(hero_entity, trans_message)

        # 开始传送。
        self._game.stage_transition(heros_entities, next_stage.name)

        # 第一场战斗
        if not self._game.combat_system.has_combat(next_stage.name):
            logger.info(f"再次战斗！！！！开始地下城level：{next_stage.name}")
            self._game.combat_system.launch_combat_engagement(next_stage.name)
        else:
            # logger.info(f"再次战斗！！！！已经有了地下城level：{next_stage.name}")
            assert False, "不可能出现的情况！"

    #######################################################################################################################################
    def _resolve_hero_lose(self) -> None:
        logger.info("英雄失败，应该返回营地！！！！")

    #######################################################################################################################################
