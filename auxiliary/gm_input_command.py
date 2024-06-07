# from rpg_game import RPGGame
# from abc import ABC, abstractmethod
# from loguru import logger
# from auxiliary.player_proxy import PlayerProxy
# from auxiliary.components import PlayerComponent

# ####################################################################################################################################
# ####################################################################################################################################
# ####################################################################################################################################
# class GMCommand(ABC):

#     def __init__(self, name: str, game: RPGGame) -> None:
#         self.name: str = name
#         self.game: RPGGame = game

#     @abstractmethod
#     def execute(self) -> None:
#         pass
# ####################################################################################################################################
# ####################################################################################################################################
# ####################################################################################################################################
# class GMCommandSimulateRequest(GMCommand):

#     def __init__(self, name: str, game: RPGGame, targetname: str, content: str) -> None:
#         super().__init__(name, game)
#         self.targetname = targetname
#         self.content = content

#     def execute(self) -> None:
#         self.game.extendedcontext.agent_connect_system.request(self.targetname, self.content)
# ####################################################################################################################################
# ####################################################################################################################################
# ####################################################################################################################################
# class GMCommandSimulateRequestThenRemoveConversation(GMCommand):

#     def __init__(self, name: str, game: RPGGame, targetname: str, content: str) -> None:
#         super().__init__(name, game)
#         self.targetname = targetname
#         self.content = content

#     def execute(self) -> None:
#         context = self.game.extendedcontext
#         name = self.targetname
#         agent_connect_system = context.agent_connect_system
#         reponse = agent_connect_system.request(name, self.content)
#         if reponse is not None:
#             agent_connect_system.remove_last_conversation_between_human_and_ai(name)
# ####################################################################################################################################
# ####################################################################################################################################
# ####################################################################################################################################
# ### 这个基本和GM指令差不多了，不允许随便用。不允许普通玩家使用。
# class GMCommandPlayerCtrlAnyNPC(GMCommand):
    
#     def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, npc_name_to_be_controlled: str) -> None:
#         super().__init__(name, game)
#         self.playerproxy = playerproxy
#         self.npc_name_to_be_controlled = npc_name_to_be_controlled

#     def execute(self) -> None:
#         context = self.game.extendedcontext
#         target_npc_name = self.npc_name_to_be_controlled
#         myname = self.playerproxy.name

#         #寻找要控制的NPC
#         to_ctrl_npc_entity = context.getnpc(target_npc_name)
#         if to_ctrl_npc_entity is None:
#             logger.error(f"{target_npc_name}, npc is None")
#             return
        
#         if to_ctrl_npc_entity.has(PlayerComponent):
#             hisplayercomp: PlayerComponent = to_ctrl_npc_entity.get(PlayerComponent)
#             if hisplayercomp.name == myname:
#                 # 不用继续了
#                 logger.warning(f"{target_npc_name}, already control {hisplayercomp.name}")
#                 return
#             else:
#                 # 已经有人控制了，但不是你，你不能抢
#                 logger.error(f"{target_npc_name}, already control by other player {hisplayercomp.name}")
#                 return
#         else:
#             # 可以继续
#             logger.debug(f"{target_npc_name} is not controlled by any player")

#         logger.debug(f"{self.name}, player name: {myname}, target name: {target_npc_name}")
#         my_player_entity = context.getplayer(myname)
#         if my_player_entity is None:
#             # 你现在不控制任何人，就不能做更换，必须先登陆
#             logger.warning(f"{myname}, player is None, can not change control target")
#             return
        
#         # 更换控制
#         my_player_entity.remove(PlayerComponent)
#         to_ctrl_npc_entity.add(PlayerComponent, myname)
# ####################################################################################################################################
# ####################################################################################################################################
# ####################################################################################################################################