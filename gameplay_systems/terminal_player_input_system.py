# from entitas import ExecuteProcessor  # type: ignore
# from rpg_game.rpg_entitas_context import RPGEntitasContext
# from loguru import logger
# from player.player_proxy import PlayerProxy

# # import player.utils
# from typing import Any, cast, override
# from rpg_game.rpg_game import RPGGame
# from rpg_game.terminal_rpg_game import TerminalRPGGame
# from rpg_game.web_server_multi_players_rpg_game import WebServerMultiplayersRPGGame
# from gameplay_systems.components import ActorComponent, StageComponent


# ############################################################################################################
# class TerminalPlayerInputSystem(ExecuteProcessor):
#     def __init__(self, context: RPGEntitasContext, rpggame: RPGGame) -> None:
#         self._context: RPGEntitasContext = context
#         self._rpggame: RPGGame = rpggame

#     ############################################################################################################
#     @override
#     def execute(self) -> None:
#         # assert len(self._rpggame.player_names) > 0
#         assert isinstance(self._rpggame, WebServerMultiplayersRPGGame) or isinstance(
#             self._rpggame, TerminalRPGGame
#         )
#         if not isinstance(self._rpggame, TerminalRPGGame):
#             logger.error("只处理终端的输入")
#             return
#         #
#         single_player = self._rpggame.single_player()
#         if single_player is not None:
#             self.play_via_terminal_and_handle_player_input(single_player)

#     ############################################################################################################
#     def play_via_terminal_and_handle_player_input(
#         self, player_proxy: PlayerProxy
#     ) -> None:

#         # player_proxy = player.utils.get_player_proxy(player_name)
#         # if player_proxy is None:
#         #     logger.warning(f"玩家{player_name}不存在，或者玩家未加入游戏")
#         #     return

#         player_actor_name = self.get_player_actor_name(player_proxy._name)

#         while True:
#             # 客户端应该看到的
#             self.display_client_messages(player_proxy, 20)
#             # 测试的客户端反馈
#             usr_input = input(f"[{player_proxy._name}/{player_actor_name}]:")
#             # 处理玩家的输入
#             self.handle_input(self._rpggame, player_proxy, usr_input)
#             # 添加消息
#             player_proxy.add_actor_message(
#                 f"{player_proxy._name}/{player_actor_name}:", f"input = {usr_input}"
#             )
#             ## 总之要跳出循环
#             break

#     ############################################################################################################
#     def get_player_actor_name(self, player_name: str) -> str:
#         player_entity = self._context.get_player_entity(player_name)
#         if player_entity is None:
#             return ""

#         if player_entity.has(ActorComponent):
#             actor_comp = player_entity.get(ActorComponent)
#             return cast(str, actor_comp.name)
#         elif player_entity.has(StageComponent):
#             stage_comp = player_entity.get(StageComponent)
#             return cast(str, stage_comp.name)

#         return ""

#     ############################################################################################################
#     def display_client_messages(
#         self, playerproxy: PlayerProxy, display_messages_count: int
#     ) -> None:
#         client_messages = playerproxy._client_messages
#         for message in client_messages[-display_messages_count:]:
#             tag = message[0]
#             content = message[1]
#             logger.warning(f"{tag}=>{content}")

#     ############################################################################################################
#     def handle_input(
#         self, rpg_game: Any, player_proxy: PlayerProxy, usr_input: str
#     ) -> None:
#         if "/quit" in usr_input:
#             assert False, "玩家退出游戏"
#             # from rpg_game.rpg_game import RPGGame

#             # cast(RPGGame, rpg_game).exit()
#         else:
#             pass
#             # player_proxy._commands.append(str(usr_input))


# ############################################################################################################
