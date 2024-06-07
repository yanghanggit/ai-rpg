from entitas import ExecuteProcessor #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.player_proxy import (PlayerProxy, 
                                    get_player_proxy, 
                                    TEST_TERMINAL_NAME, 
                                    PLAYER_INPUT_MODE, 
                                    determine_player_input_mode, 
                                    TEST_CLIENT_SHOW_MESSAGE_COUNT)
from auxiliary.extended_context import ExtendedContext

class TerminalPlayerInterruptAndWaitSystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    def execute(self) -> None:
        input_mode = determine_player_input_mode(self.context.user_ips)
        if input_mode != PLAYER_INPUT_MODE.TERMINAL:
            return
            
        #就是展示一下并点击继续，没什么用
        playerproxy = get_player_proxy(TEST_TERMINAL_NAME)
        player_npc_entity = self.context.getplayer(TEST_TERMINAL_NAME)
        if player_npc_entity is None or playerproxy is None:
            return
        
        self.display_client_messages(playerproxy, TEST_CLIENT_SHOW_MESSAGE_COUNT)
        while True:
            # 测试的客户端反馈
            input(f"[{TEST_TERMINAL_NAME}]:当前为中断等待，请任意键继续")
            break   
############################################################################################################ 
    def display_client_messages(self, playerproxy: PlayerProxy, display_messages_count: int) -> None:
        if display_messages_count <= 0:
            return
        clientmessages = playerproxy.client_messages
        for message in clientmessages[-display_messages_count:]:
            tag = message[0]
            content = message[1]
            logger.error(f"{tag}=>{content}")
############################################################################################################
    
    