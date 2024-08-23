from entitas import Entity, ExecuteProcessor  # type: ignore
from typing import override, Set, List, cast
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from rpg_game.rpg_game import RPGGame
from rpg_game.terminal_rpg_game import TerminalRPGGame
import player.utils
from gameplay_systems.components import (
    PlayerComponent,
    ActorComponent,
    StageGraphComponent,
    GUIDComponent,
)
from file_system.files_def import StageArchiveFile
from player.player_proxy import PlayerProxy
import gameplay_systems.cn_builtin_prompt as builtin_prompt


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

        self.tips_stages()

    ############################################################################################################
    def tips_stages(self) -> None:

        for player_name in self._rpg_game.player_names:

            player_proxy = player.utils.get_player_proxy(player_name)
            if player_proxy is None:
                logger.warning("玩家不存在，或者玩家未加入游戏")
                continue

            player_entity = self._context.get_player_entity(player_name)
            assert player_entity is not None
            assert player_entity.has(PlayerComponent)
            assert player_entity.has(ActorComponent)

            # 当前场景能去往的场景
            self.tips_next_stages(player_proxy, player_entity)

            # 人物已知的场景
            self.tip_stage_archives(player_proxy, player_entity)

    ############################################################################################################
    def tips_next_stages(
        self, player_proxy: PlayerProxy, player_entity: Entity
    ) -> None:
        assert player_entity is not None
        assert player_proxy is not None

        actor_name = self._context.safe_get_entity_name(player_entity)
        stage_entity = self._context.safe_get_stage_entity(player_entity)
        assert stage_entity is not None

        if not stage_entity.has(StageGraphComponent):
            player_proxy.add_actor_message(
                actor_name, "当前场景没有相连接的场景，无法离开"
            )
            return

        stage_graph_comp = stage_entity.get(StageGraphComponent)
        assert stage_graph_comp is not None

        stage_names: List[str] = [
            self.parse_stage_name(stage_name, actor_name)
            for stage_name in cast(Set[str], stage_graph_comp.stage_graph)
        ]
        player_proxy.add_stage_message(
            self._context.safe_get_entity_name(stage_entity),
            f"可去往场景:\n{'\n'.join(stage_names)}",
        )

    ############################################################################################################
    def parse_stage_name(self, stage_name: str, actor_name: str) -> str:

        if self._context._file_system.has_file(
            StageArchiveFile, actor_name, stage_name
        ):
            return stage_name

        stage_entity = self._context.get_stage_entity(stage_name)
        assert stage_entity is not None

        assert stage_entity.has(GUIDComponent)
        guid_comp = stage_entity.get(GUIDComponent)
        return builtin_prompt.make_unknown_guid_stage_name_prompt(guid_comp.GUID)

    ############################################################################################################
    def tip_stage_archives(
        self, player_proxy: PlayerProxy, player_entity: Entity
    ) -> None:

        assert player_entity is not None
        assert player_proxy is not None

        actor_name = self._context.safe_get_entity_name(player_entity)
        stage_archives = self._context._file_system.get_files(
            StageArchiveFile, actor_name
        )
        stage_names: List[str] = [
            stage_archive.name for stage_archive in stage_archives
        ]

        player_proxy.add_actor_message(
            actor_name, f"已知场景:\n{'\n'.join(stage_names)}"
        )


############################################################################################################
