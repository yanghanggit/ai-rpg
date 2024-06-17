from typing import override
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
from rpg_game import RPGGame 

class TerminalPlayerInterruptAndWaitSystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext, rpggame: RPGGame) -> None:
        self.context: ExtendedContext = context
        self.rpggame = rpggame
############################################################################################################
    @override
    def execute(self) -> None:

        # todo
        # 临时的设置，通过IP地址来判断是不是测试的客户端
        user_ips = self.rpggame.user_ips    
        # 判断，user_ips 与 self.context.user_ips 是否一致：元素的顺序和个数，和元素的内容
        if user_ips != self.context.user_ips:
            assert False, "user_ips 与 self.context.user_ips 不一致"

        input_mode = determine_player_input_mode(user_ips)
        if input_mode != PLAYER_INPUT_MODE.TERMINAL:
            return
            
        #就是展示一下并点击继续，没什么用
        playerproxy = get_player_proxy(TEST_TERMINAL_NAME)
        player_entity = self.context.get_player_entity(TEST_TERMINAL_NAME)
        if player_entity is None or playerproxy is None:
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
            logger.info(f"{tag}=>{content}")
############################################################################################################
    
    