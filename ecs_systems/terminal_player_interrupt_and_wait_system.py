from typing import override
from entitas import ExecuteProcessor #type: ignore
from my_entitas.extended_context import ExtendedContext
from loguru import logger
from player.player_proxy import (PlayerProxy, get_player_proxy)
from my_entitas.extended_context import ExtendedContext
from rpg_game.rpg_game import RPGGame 
from rpg_game.terminal_rpg_game import TerminalRPGGame

class TerminalPlayerInterruptAndWaitSystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext, rpggame: RPGGame) -> None:
        self.context: ExtendedContext = context
        self.rpggame: RPGGame = rpggame
############################################################################################################
    @override
    def execute(self) -> None:
        if not isinstance(self.rpggame, TerminalRPGGame):
            logger.debug("不是终端模式，不需要中断等待")
            return

        single_player = self.rpggame.single_player()
        player_proxy = get_player_proxy(single_player)
        player_entity = self.context.get_player_entity(single_player)
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
        clientmessages = playerproxy._client_messages
        for message in clientmessages[-display_messages_count:]:
            tag = message[0]
            content = message[1]
            logger.info(f"{tag}=>{content}")
############################################################################################################
    
    