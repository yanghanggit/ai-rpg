from entitas import ExecuteProcessor #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.player_proxy import PlayerProxy, get_player_proxy, TEST_TERMINAL_NAME, PLAYER_INPUT_MODE, determine_player_input_mode
from auxiliary.extended_context import ExtendedContext
from typing import Any, cast


############################################################################################################
class TerminalPlayerInputSystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext, rpggame: Any) -> None:
        self.context: ExtendedContext = context
        self.rpggame = rpggame
############################################################################################################
    def execute(self) -> None:
        # 临时的设置，通过IP地址来判断是不是测试的客户端
        if determine_player_input_mode(self.context.user_ip) != PLAYER_INPUT_MODE.TERMINAL:
            logger.debug("只处理终端的输入")
            return
        # 通过终端输入
        self.play_via_terminal_and_handle_player_input(TEST_TERMINAL_NAME)
############################################################################################################
    def play_via_terminal_and_handle_player_input(self, playername: str) -> None:

        playerproxy = get_player_proxy(playername)
        if playerproxy is None:
            logger.warning("玩家不存在，或者玩家未加入游戏")
            return
        
        while True:
           
            # 客户端应该看到的
            self.display_client_messages(playerproxy, 10)    
           
            # 测试的客户端反馈
            usrinput = input(f"[{playername}]:")
            playerproxy.add_system_message(usrinput)

            # 处理玩家的输入
            self.handle_input(self.rpggame, playerproxy, usrinput)
            logger.debug(f"{'=' * 50}")

            ## 总之要跳出循环
            break
############################################################################################################ 
    def display_client_messages(self, playerproxy: PlayerProxy, display_messages_count: int) -> None:
        clientmessages = playerproxy.clientmessages
        for message in clientmessages[-display_messages_count:]:
            tag = message[0]
            content = message[1]
            logger.warning(f"{tag}=>{content}")
############################################################################################################
    def handle_input(self, rpggame: Any, playerproxy: PlayerProxy, usrinput: str) -> None:
        if "/quit" in usrinput:
            from rpg_game import RPGGame 
            cast(RPGGame, rpggame).exit()
        else:
            playerproxy.commands.append(str(usrinput))
############################################################################################################

