from entitas import ExecuteProcessor  # type: ignore
from typing import override
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from rpg_game.rpg_game import RPGGame
from player.player_proxy import PlayerProxy
import player.utils
from player.player_command import (
    PlayerGoTo,
    PlayerBroadcast,
    PlayerSpeak,
    PlayerWhisper,
    PlayerPickUpProp,
    PlayerSteal,
    PlayerGiveProp,
    PlayerBehavior,
    PlayerEquip,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from rpg_game.terminal_rpg_game import TerminalRPGGame
from rpg_game.web_server_multi_players_rpg_game import WebServerMultiplayersRPGGame


############################################################################################################
def split_command(input_val: str, split_str: str) -> str:
    if split_str in input_val:
        return input_val.split(split_str)[1].strip()
    return input_val


############################################################################################################
class HandlePlayerInputSystem(ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:
        assert isinstance(self._game, WebServerMultiplayersRPGGame) or isinstance(
            self._game, TerminalRPGGame
        )
        # assert len(self._game.player_names) > 0
        for player_name in self._game.player_names:
            self.play_via_client_and_handle_player_input(player_name)

    ############################################################################################################
    def play_via_client_and_handle_player_input(self, player_name: str) -> None:
        player_proxy = player.utils.get_player_proxy(player_name)
        if player_proxy is None:
            logger.warning("玩家不存在，或者玩家未加入游戏")
            return

        for command in player_proxy._input_commands:
            player_entity = self._context.get_player_entity(player_name)
            if player_entity is None:
                # logger.warning("玩家实体不存在")
                continue
            assert player_entity is not None

            ## 处理玩家的输入
            create_any_player_command_by_input = self.handle_input(
                self._game, player_proxy, command
            )

            if not create_any_player_command_by_input:
                ## 是立即模式，显示一下客户端的消息
                logger.debug("立即模式的input = " + command)

            ## 总之要跳出循环
            break

        player_proxy._input_commands.clear()

    ############################################################################################################
    def handle_input(
        self, rpg_game: RPGGame, player_proxy: PlayerProxy, usr_input: str
    ) -> bool:

        if "/quit" in usr_input:
            rpg_game.exited = True

        elif "/goto" in usr_input:
            command = "/goto"
            stagename = split_command(usr_input, command)
            PlayerGoTo(command, rpg_game, player_proxy, stagename).execute()

        elif "/broadcast" in usr_input:
            command = "/broadcast"
            content = split_command(usr_input, command)
            PlayerBroadcast(command, rpg_game, player_proxy, content).execute()

        elif "/speak" in usr_input:
            command = "/speak"
            content = split_command(usr_input, command)
            PlayerSpeak(command, rpg_game, player_proxy, content).execute()

        elif "/whisper" in usr_input:
            command = "/whisper"
            content = split_command(usr_input, command)
            PlayerWhisper(command, rpg_game, player_proxy, content).execute()

        elif "/pickup" in usr_input:
            command = "/pickup"
            prop_name = split_command(usr_input, command)
            PlayerPickUpProp(command, rpg_game, player_proxy, prop_name).execute()

        elif "/steal" in usr_input:
            command = "/steal"
            prop_name = split_command(usr_input, command)
            PlayerSteal(command, rpg_game, player_proxy, prop_name).execute()

        elif "/give" in usr_input:
            command = "/give"
            prop_name = split_command(usr_input, command)
            PlayerGiveProp(command, rpg_game, player_proxy, prop_name).execute()

        elif "/behavior" in usr_input:
            PlayerBehavior(
                "/behavior",
                rpg_game,
                player_proxy,
                split_command(usr_input, "/behavior"),
            ).execute()

        elif "/equip" in usr_input:

            PlayerEquip(
                "/equip",
                rpg_game,
                player_proxy,
                split_command(usr_input, "/equip"),
            ).execute()

        return True


############################################################################################################
