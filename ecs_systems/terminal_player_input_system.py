from entitas import ExecuteProcessor #type: ignore
from my_entitas.extended_context import ExtendedContext
from loguru import logger
from player.player_proxy import PlayerProxy, get_player_proxy
from typing import Any, cast, override
from rpg_game.rpg_game import RPGGame 
from rpg_game.terminal_rpg_game import TerminalRPGGame
from rpg_game.web_server_multi_players_rpg_game import WebServerMultiplayersRPGGame

############################################################################################################
class TerminalPlayerInputSystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext, rpggame: RPGGame) -> None:
        self.context: ExtendedContext = context
        self.rpggame: RPGGame = rpggame
############################################################################################################
    @override
    def execute(self) -> None:
        assert len(self.rpggame.player_names) > 0
        assert isinstance(self.rpggame, WebServerMultiplayersRPGGame) or isinstance(self.rpggame, TerminalRPGGame)
        if not isinstance(self.rpggame, TerminalRPGGame):
            logger.error("只处理终端的输入")
            return
        #
        single_player = self.rpggame.single_player()
        self.play_via_terminal_and_handle_player_input(single_player)

        # # todo
        # # 临时的设置，通过IP地址来判断是不是测试的客户端
        # user_ips = self.rpggame._player_names
        # # 临时的设置，通过IP地址来判断是不是测试的客户端
        # if determine_player_input_mode(user_ips) != PLAYER_INPUT_MODE.TERMINAL:
        #     #logger.debug("只处理终端的输入")
        #     return
        # # 通过终端输入
        # self.play_via_terminal_and_handle_player_input(TEST_TERMINAL_NAME)
############################################################################################################
    def play_via_terminal_and_handle_player_input(self, playername: str) -> None:

        playerproxy = get_player_proxy(playername)
        if playerproxy is None:
            logger.warning(f"玩家{playername}不存在，或者玩家未加入游戏")
            return
        
        while True:
            # 客户端应该看到的
            self.display_client_messages(playerproxy, 20)    
            # 测试的客户端反馈
            usrinput = input(f"[{playername}]:")
            # 处理玩家的输入
            self.handle_input(self.rpggame, playerproxy, usrinput)
            ## 总之要跳出循环
            break
############################################################################################################ 
    def display_client_messages(self, playerproxy: PlayerProxy, display_messages_count: int) -> None:
        clientmessages = playerproxy._client_messages
        for message in clientmessages[-display_messages_count:]:
            tag = message[0]
            content = message[1]
            logger.warning(f"{tag}=>{content}")
############################################################################################################
    def handle_input(self, rpggame: Any, playerproxy: PlayerProxy, usrinput: str) -> None:
        if "/quit" in usrinput:
            from rpg_game.rpg_game import RPGGame 
            cast(RPGGame, rpggame).exit()
        else:
            playerproxy._inputs.append(str(usrinput))
############################################################################################################

