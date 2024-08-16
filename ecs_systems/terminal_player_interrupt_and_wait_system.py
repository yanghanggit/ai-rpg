from typing import override
from entitas import ExecuteProcessor #type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from player.player_proxy import (PlayerProxy)
import player.utils
from rpg_game.rpg_entitas_context import RPGEntitasContext
from rpg_game.rpg_game import RPGGame 
from rpg_game.terminal_rpg_game import TerminalRPGGame

class TerminalPlayerInterruptAndWaitSystem(ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._rpg_game: RPGGame = rpg_game
############################################################################################################
    @override
    def execute(self) -> None:
        if not isinstance(self._rpg_game, TerminalRPGGame):
            logger.debug("不是终端模式，不需要中断等待")
            return

        single_player = self._rpg_game.single_player()
        player_proxy = player.utils.get_player_proxy(single_player)
        player_entity = self._context.get_player_entity(single_player)
        if player_entity is None or player_proxy is None:
            return
        
        self.display_client_messages(player_proxy, 20)
        while True:
            # 测试的客户端反馈
            input(f"[{single_player}]:当前为中断等待，请任意键继续")
            break   
############################################################################################################ 
    def display_client_messages(self, playerproxy: PlayerProxy, display_messages_count: int) -> None:
        if display_messages_count <= 0:
            return
        client_messages = playerproxy._client_messages
        for message in client_messages[-display_messages_count:]:
            tag = message[0]
            content = message[1]
            logger.info(f"{tag}=>{content}")
############################################################################################################
    
    