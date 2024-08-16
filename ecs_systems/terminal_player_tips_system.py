from entitas import ExecuteProcessor #type: ignore
from typing import override, Set, List
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from rpg_game.rpg_game import RPGGame 
from rpg_game.terminal_rpg_game import TerminalRPGGame
import player.utils
from ecs_systems.components import PlayerComponent, ActorComponent, StageGraphComponent, GUIDComponent
from file_system.files_def import StageArchiveFile

class TerminalPlayerTipsSystem(ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._rpg_game: RPGGame = rpg_game
############################################################################################################
    @override
    def execute(self) -> None:
        if not isinstance(self._rpg_game, TerminalRPGGame):
            logger.debug("不是终端模式，不需要中断等待")
            return
        
        self.tips_next_stages()
############################################################################################################
    def tips_next_stages(self) -> None:
        for player_name in self._rpg_game.player_names:
            self._tips_next_stages(player_name)
############################################################################################################
    def _tips_next_stages(self, player_name: str) -> None:
        player_proxy = player.utils.get_player_proxy(player_name)
        if player_proxy is None:
            logger.warning("玩家不存在，或者玩家未加入游戏")
            return
        
        player_entity = self._context.get_player_entity(player_name)
        assert player_entity is not None
        assert player_entity.has(PlayerComponent)
        assert player_entity.has(ActorComponent)

        actor_name = self._context.safe_get_entity_name(player_entity)
        stage_entity = self._context.safe_get_stage_entity(player_entity)
        assert stage_entity is not None

        if not stage_entity.has(StageGraphComponent):
            player_proxy.add_actor_message(actor_name, "当前场景没有相连接的场景，无法离开")
            return

        stage_graph_comp = stage_entity.get(StageGraphComponent)
        assert stage_graph_comp is not None

        stage_graph: Set[str] = stage_graph_comp.stage_graph
        stage_names: List[str] = []
        for stage_name in stage_graph:
            stage_names.append(self.parse_stage_name(stage_name, actor_name))
    
        player_proxy.add_actor_message(actor_name, f"可去往场景：{','.join(stage_names)}")
############################################################################################################
    def parse_stage_name(self, stage_name: str, actor_name: str) -> str:

        if self._context._file_system.has_file(StageArchiveFile, actor_name, stage_name):
            return stage_name

        stage_entity = self._context.get_stage_entity(stage_name)
        assert stage_entity is not None
        
        assert stage_entity.has(GUIDComponent)
        guid_comp = stage_entity.get(GUIDComponent)
        return f"unknown({guid_comp.GUID})"
############################################################################################################
    