from entitas import ExecuteProcessor #type: ignore
from typing import override
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from rpg_game.rpg_game import RPGGame 
from player.player_proxy import PlayerProxy, get_player_proxy
from player.player_command import (
                          PlayerAttack, 
                          PlayerGoTo, 
                          PlayerBroadcast, 
                          PlayerSpeak,
                          PlayerUseProp, 
                          PlayerWhisper, 
                          PlayerSearchProp,
                          PlayerPortalStep,
                          PlayerSteal,
                          PlayerGiveProp, 
                          PlayerPerception,
                          PlayerCheckStatus)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from rpg_game.terminal_rpg_game import TerminalRPGGame
from rpg_game.web_server_multi_players_rpg_game import WebServerMultiplayersRPGGame

############################################################################################################
def split_command(input_val: str, split_str: str)-> str:
    if split_str in input_val:
        return input_val.split(split_str)[1].strip()
    return input_val
############################################################################################################
class HandlePlayerInputSystem(ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext, rpggame: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._rpggame: RPGGame = rpggame
############################################################################################################
    @override
    def execute(self) -> None:
        assert isinstance(self._rpggame, WebServerMultiplayersRPGGame) or isinstance(self._rpggame, TerminalRPGGame)
        assert len(self._rpggame.player_names) > 0
        for player_name in self._rpggame.player_names:
            self.play_via_client_and_handle_player_input(player_name)
############################################################################################################
    def play_via_client_and_handle_player_input(self, playername: str) -> None:
        playerproxy = get_player_proxy(playername)
        if playerproxy is None:
            logger.warning("玩家不存在，或者玩家未加入游戏")
            return
        
        for command in playerproxy._input_commands:
            singleplayer = self._context.get_player_entity(playername)
            assert singleplayer is not None
            #
            safename = self._context.safe_get_entity_name(singleplayer)
            playerproxy.add_actor_message(safename, command)
            
            ## 处理玩家的输入
            create_any_player_command_by_input = self.handle_input(self._rpggame, playerproxy, command)
            #logger.debug(f"{'=' * 50}")

            if not create_any_player_command_by_input:
                ## 是立即模式，显示一下客户端的消息
                logger.debug("立即模式的input = " + command)     

            ## 总之要跳出循环 
            break
                  
        playerproxy._input_commands.clear()
############################################################################################################
    def handle_input(self, rpggame: RPGGame, playerproxy: PlayerProxy, usrinput: str) -> bool:

        if "/quit" in usrinput:
            rpggame.exited = True
        
        elif "/attack" in usrinput:
            command = "/attack"
            targetname = split_command(usrinput, command)           
            PlayerAttack(command, rpggame, playerproxy, targetname).execute()
                        
        elif "/goto" in usrinput:
            command = "/goto"
            stagename = split_command(usrinput, command)
            PlayerGoTo(command, rpggame, playerproxy, stagename).execute()
  
        elif "/broadcast" in usrinput:
            command = "/broadcast"
            content = split_command(usrinput, command)
            PlayerBroadcast(command, rpggame, playerproxy, content).execute()
            
        elif "/speak" in usrinput:
            command = "/speak"
            content = split_command(usrinput, command)
            PlayerSpeak(command, rpggame, playerproxy, content).execute()

        elif "/whisper" in usrinput:
            command = "/whisper"
            content = split_command(usrinput, command)
            PlayerWhisper(command, rpggame,playerproxy, content).execute()

        elif "/searchprop" in usrinput:
            command = "/searchprop"
            propname = split_command(usrinput, command)
            PlayerSearchProp(command, rpggame, playerproxy, propname).execute()

        elif "/portalstep" in usrinput:
            command = "/portalstep"
            PlayerPortalStep(command, rpggame, playerproxy).execute()

        elif "/stealprop" in usrinput:
            command = "/stealprop"
            propname = split_command(usrinput, command)
            PlayerSteal(command, rpggame, playerproxy, propname).execute()

        elif "/giveprop" in usrinput:
            command = "/giveprop"
            propname = split_command(usrinput, command)
            PlayerGiveProp(command, rpggame, playerproxy, propname).execute()

        elif "/perception" in usrinput:
            command = "/perception"
            #self.imme_handle_perception(playerproxy)
            PlayerPerception(command, rpggame, playerproxy).execute()
            #return False

        elif "/checkstatus" in usrinput:
            command = "/checkstatus"
            #self.imme_handle_check_status(playerproxy)
            PlayerCheckStatus(command, rpggame, playerproxy).execute()
            #return False
        
        elif "/useprop" in usrinput:
            command = "/useprop"
            content = split_command(usrinput, command)
            PlayerUseProp(command, rpggame, playerproxy, content).execute()

        return True
############################################################################################################

