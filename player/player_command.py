from entitas import Entity  # type: ignore
from rpg_game.rpg_game import RPGGame
from loguru import logger
from gameplay_systems.action_components import (
    BroadcastAction,
    SpeakAction,
    GoToAction,
    WhisperAction,
    PickUpPropAction,
    PerceptionAction,
    StealPropAction,
    GivePropAction,
    CheckStatusAction,
    BehaviorAction,
)
from gameplay_systems.components import (
    ActorComponent,
    PlayerComponent,
    PlayerIsWebClientComponent,
    PlayerIsTerminalClientComponent,
)

# from my_agent.agent_action import AgentAction
from player.player_proxy import PlayerProxy
from abc import ABC, abstractmethod
import datetime
from typing import Dict, List
import json


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerCommand(ABC):
    """
    玩家行为的抽象类，所有的玩家行为都继承这个类，实现execute方法。
    玩家的行为抽象成对象，方便在游戏中进行管理。
    也是好习惯～？^-^
    """

    def __init__(
        self, description: str, rpg_game: RPGGame, playerproxy: PlayerProxy
    ) -> None:
        self._description: str = description
        self._rpggame: RPGGame = rpg_game
        self._player_proxy: PlayerProxy = playerproxy

    @abstractmethod
    def execute(self) -> None:
        pass

    # 为了方便，直接在这里添加消息，不然每个子类都要写一遍
    # player 控制的actor本质和其他actor没有什么不同，这里模拟一个plan的动作。因为每一个actor都是plan -> acton -> direction(同步上下文) -> 再次plan的循环
    def simu_player_planning_input_message(
        self, entity: Entity, human_message_content: str
    ) -> None:
        # self._rpggame._entitas_context.safe_add_human_message_to_entity(
        #     entity, human_message_content
        # )
        self._rpggame._entitas_context.safe_add_ai_message_to_entity(
            entity, human_message_content
        )


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerLogin(PlayerCommand):
    """
    玩家登陆的行为，本质就是直接控制一个actor，将actor的playercomp的名字改为玩家的名字
    """

    def __init__(
        self,
        name: str,
        rpg_game: RPGGame,
        player_proxy: PlayerProxy,
        actor_name: str,
        is_web_client: bool,
    ) -> None:
        super().__init__(name, rpg_game, player_proxy)
        self._actor_name: str = actor_name  # 玩家控制的actor.
        self._is_web_client: bool = is_web_client

    def execute(self) -> None:
        context = self._rpggame._entitas_context
        actor_name = self._actor_name
        player_name = self._player_proxy._name
        logger.info(
            f"{self._description}, player name: {player_name}, actor name: {actor_name}"
        )

        actor_entity = context.get_actor_entity(actor_name)
        if actor_entity is None:
            # 扮演的角色，本身就不存在于这个世界
            logger.error(f"{actor_name}, actor is None, login failed")
            return

        player_entity = context.get_player_entity(player_name)
        if player_entity is not None:
            # 已经登陆完成
            logger.error(f"{player_name}, already login")
            return

        player_comp = actor_entity.get(PlayerComponent)
        if player_comp is None:
            # 扮演的角色不是设定的玩家可控制Actor
            logger.error(f"{actor_name}, actor is not player ctrl actor, login failed")
            return

        if player_comp.name != "" and player_comp.name != player_name:
            # 已经有人控制了，但不是你
            logger.error(
                f"{actor_name}, player already ctrl by some player {player_comp.name}, login failed"
            )
            return

        # 更改player的名字，算作登陆成功
        actor_entity.replace(PlayerComponent, player_name)

        # 判断登陆的方式：是web客户端还是终端客户端
        if self._is_web_client:
            if actor_entity.has(PlayerIsWebClientComponent):
                actor_entity.remove(PlayerIsWebClientComponent)
            actor_entity.add(PlayerIsWebClientComponent, player_name)
        else:
            if actor_entity.has(PlayerIsTerminalClientComponent):
                actor_entity.remove(PlayerIsTerminalClientComponent)
            actor_entity.add(PlayerIsTerminalClientComponent, player_name)

        # todo 添加游戏的介绍到客户端消息中
        self._player_proxy.add_system_message(self._rpggame.about_game)

        # todo 添加登陆新的信息到客户端消息中
        time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._player_proxy.add_system_message(
            f"login: {player_name}, time = {time}, 控制角色 = {actor_name}"
        )

        # actor的kickoff记忆到客户端消息中
        kick_off_message = context._kick_off_message_system.get_message(
            self._actor_name
        )
        assert kick_off_message != ""
        self._player_proxy.add_login_message(self._actor_name, kick_off_message)


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
# class PlayerAttack(PlayerCommand):
#     """
#     玩家攻击的行为：AttackAction
#     """

#     def __init__(
#         self, name: str, rpg_game: RPGGame, player_proxy: PlayerProxy, target_name: str
#     ) -> None:
#         super().__init__(name, rpg_game, player_proxy)
#         self._target_name: str = target_name

#     def execute(self) -> None:
#         context = self._rpggame._entitas_context
#         attack_target_name = self._target_name
#         player_entity = context.get_player_entity(self._player_proxy._name)
#         if player_entity is None:
#             logger.warning("debug_attack: player is None")
#             return

#         if player_entity.has(ActorComponent):
#             actor_comp = player_entity.get(ActorComponent)
#             player_entity.add(
#                 AttackAction,
#                 actor_comp.name,
#                 AttackAction.__name__,
#                 [attack_target_name],
#             )

#         elif player_entity.has(StageComponent):
#             stage_comp = player_entity.get(StageComponent)
#             player_entity.add(
#                 AttackAction,
#                 stage_comp.name,
#                 AttackAction.__name__,
#                 [attack_target_name],
#             )


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerGoTo(PlayerCommand):
    """
    玩家移动的行为：GoToAction
    """

    def __init__(
        self, name: str, rpg_game: RPGGame, player_proxy: PlayerProxy, stage_name: str
    ) -> None:
        super().__init__(name, rpg_game, player_proxy)
        self._stage_name: str = stage_name

    def execute(self) -> None:
        context = self._rpggame._entitas_context
        target_stage_name = self._stage_name
        player_entity = context.get_player_entity(self._player_proxy._name)
        if player_entity is None:
            # 玩家实体不存在
            logger.warning("debug: player is None")
            return

        # 添加行动
        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(
            GoToAction, actor_comp.name, GoToAction.__name__, [target_stage_name]
        )

        # 模拟添加一个plan的发起。
        human_message = f"""{{"{GoToAction.__name__}": ["{target_stage_name}"]}}"""
        self.simu_player_planning_input_message(player_entity, human_message)


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerBroadcast(PlayerCommand):
    """
    玩家广播的行为：BroadcastAction
    """

    def __init__(
        self,
        name: str,
        rpg_game: RPGGame,
        player_proxy: PlayerProxy,
        broadcast_content: str,
    ) -> None:
        super().__init__(name, rpg_game, player_proxy)
        self._broadcast_content: str = broadcast_content

    def execute(self) -> None:
        context = self._rpggame._entitas_context
        player_entity = context.get_player_entity(self._player_proxy._name)
        if player_entity is None:
            logger.warning("debug_broadcast: player is None")
            return

        # 添加行动
        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(
            BroadcastAction,
            actor_comp.name,
            BroadcastAction.__name__,
            [self._broadcast_content],
        )

        # 模拟添加一个plan的发起。
        human_message = (
            f"""{{"{BroadcastAction.__name__}": ["{self._broadcast_content}"]}}"""
        )
        self.simu_player_planning_input_message(player_entity, human_message)


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerSpeak(PlayerCommand):
    """
    玩家说话的行为：SpeakAction
    """

    def __init__(
        self,
        name: str,
        rpg_game: RPGGame,
        player_proxy: PlayerProxy,
        speak_content: str,
    ) -> None:
        super().__init__(name, rpg_game, player_proxy)
        self._speak_content: str = speak_content

    def execute(self) -> None:
        context = self._rpggame._entitas_context
        player_entity = context.get_player_entity(self._player_proxy._name)
        if player_entity is None:
            logger.warning("debug_speak: player is None")
            return

        # 添加行动
        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(
            SpeakAction, actor_comp.name, SpeakAction.__name__, [self._speak_content]
        )

        # 模拟添加一个plan的发起。
        human_message = f"""{{"{SpeakAction.__name__}": ["{self._speak_content}"]}}"""
        self.simu_player_planning_input_message(player_entity, human_message)


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerWhisper(PlayerCommand):
    """
    玩家私聊的行为：WhisperAction
    """

    def __init__(
        self,
        name: str,
        rpg_game: RPGGame,
        player_proxy: PlayerProxy,
        whisper_content: str,
    ) -> None:
        super().__init__(name, rpg_game, player_proxy)
        self._whisper_content: str = whisper_content

    def execute(self) -> None:
        context = self._rpggame._entitas_context
        player_entity = context.get_player_entity(self._player_proxy._name)
        if player_entity is None:
            logger.warning("debug_whisper: player is None")
            return

        # 添加行动
        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(
            WhisperAction,
            actor_comp.name,
            WhisperAction.__name__,
            [self._whisper_content],
        )

        # 模拟添加一个plan的发起。
        human_message = (
            f"""{{"{WhisperAction.__name__}": ["{self._whisper_content}"]}}"""
        )
        self.simu_player_planning_input_message(player_entity, human_message)


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerSearchProp(PlayerCommand):
    """
    玩家搜索的行为：PickUpPropAction
    """

    def __init__(
        self, name: str, rpg_game: RPGGame, player_proxy: PlayerProxy, prop_name: str
    ) -> None:
        super().__init__(name, rpg_game, player_proxy)
        self._prop_name: str = prop_name

    def execute(self) -> None:
        context = self._rpggame._entitas_context
        player_entity = context.get_player_entity(self._player_proxy._name)
        if player_entity is None:
            logger.warning("debug_search: player is None")
            return

        # 添加行动
        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(
            PickUpPropAction,
            actor_comp.name,
            PickUpPropAction.__name__,
            [self._prop_name],
        )

        # 模拟添加一个plan的发起。
        human_message = f"""{{"{PickUpPropAction.__name__}": ["{self._prop_name}"]}}"""
        self.simu_player_planning_input_message(player_entity, human_message)


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerPerception(PlayerCommand):
    """
    玩家感知的行为：PerceptionAction
    """

    def __init__(self, name: str, rpg_game: RPGGame, player_proxy: PlayerProxy) -> None:
        super().__init__(name, rpg_game, player_proxy)

    def execute(self) -> None:
        context = self._rpggame._entitas_context
        player_entity = context.get_player_entity(self._player_proxy._name)
        if player_entity is None:
            return

        # 添加行动
        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(
            PerceptionAction,
            actor_comp.name,
            PerceptionAction.__name__,
            [actor_comp.current_stage],
        )

        # 模拟添加一个plan的发起。
        human_message = (
            f"""{{"{PerceptionAction.__name__}": ["{actor_comp.current_stage}"]}}"""
        )
        self.simu_player_planning_input_message(player_entity, human_message)


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerSteal(PlayerCommand):
    """
    玩家偷东西的行为：StealActionComponent
    """

    def __init__(
        self,
        name: str,
        rpg_game: RPGGame,
        player_proxy: PlayerProxy,
        target_and_message_format_string: str,
    ) -> None:
        super().__init__(name, rpg_game, player_proxy)
        # "@要偷的人>偷他的啥东西"
        self._target_and_message_format_string: str = target_and_message_format_string

    def execute(self) -> None:
        context = self._rpggame._entitas_context
        player_entity = context.get_player_entity(self._player_proxy._name)
        if player_entity is None:
            return

        # 添加行动
        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(
            StealPropAction,
            actor_comp.name,
            StealPropAction.__name__,
            [self._target_and_message_format_string],
        )

        # 模拟添加一个plan的发起。
        human_message = f"""{{"{StealPropAction.__name__}": ["{self._target_and_message_format_string}"]}}"""
        self.simu_player_planning_input_message(player_entity, human_message)


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerGiveProp(PlayerCommand):
    """
    玩家交易的行为：GivePropAction
    """

    def __init__(
        self,
        name: str,
        rpg_game: RPGGame,
        player_proxy: PlayerProxy,
        target_and_message_format_string: str,
    ) -> None:
        super().__init__(name, rpg_game, player_proxy)
        # "@交易的对象>我的啥东西"
        self._target_and_message_format_string: str = target_and_message_format_string

    def execute(self) -> None:
        context = self._rpggame._entitas_context
        player_entity = context.get_player_entity(self._player_proxy._name)
        if player_entity is None:
            return

        # 添加行动
        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(
            GivePropAction,
            actor_comp.name,
            GivePropAction.__name__,
            [self._target_and_message_format_string],
        )

        # 模拟添加一个plan的发起。
        human_message = f"""{{"{GivePropAction.__name__}": ["{self._target_and_message_format_string}"]}}"""
        self.simu_player_planning_input_message(player_entity, human_message)


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerCheckStatus(PlayerCommand):
    """
    玩家查看状态的行为：CheckStatusAction
    """

    def __init__(self, name: str, rpg_game: RPGGame, player_proxy: PlayerProxy) -> None:
        super().__init__(name, rpg_game, player_proxy)

    def execute(self) -> None:
        context = self._rpggame._entitas_context
        player_entity = context.get_player_entity(self._player_proxy._name)
        if player_entity is None:
            return

        if player_entity.has(CheckStatusAction):
            logger.warning(
                "debug: player has CheckStatusAction????"
            )  # 应该是有问题的，如果存在。
            player_entity.remove(CheckStatusAction)

        # 添加行动
        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(
            CheckStatusAction,
            actor_comp.name,
            CheckStatusAction.__name__,
            [actor_comp.name],
        )

        # 模拟添加一个plan的发起。
        human_message = f"""{{"{CheckStatusAction.__name__}": ["{actor_comp.name}"]}}"""
        self.simu_player_planning_input_message(player_entity, human_message)


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
# class PlayerUseProp(PlayerCommand):
#     """
#     玩家使用道具的行为：UsePropAction
#     """

#     def __init__(
#         self,
#         name: str,
#         rpg_game: RPGGame,
#         player_proxy: PlayerProxy,
#         target_and_message_format_string: str,
#     ) -> None:
#         super().__init__(name, rpg_game, player_proxy)
#         # "@使用道具对象>道具名"
#         self._target_and_message_format_string: str = target_and_message_format_string

#     def execute(self) -> None:
#         context = self._rpggame._entitas_context
#         player_entity = context.get_player_entity(self._player_proxy._name)
#         if player_entity is None:
#             return

#         # 添加行动
#         actor_comp = player_entity.get(ActorComponent)
#         player_entity.add(
#             UsePropAction,
#             actor_comp.name,
#             UsePropAction.__name__,
#             [self._target_and_message_format_string],
#         )

#         # 模拟添加一个plan的发起。
#         human_message = f"""{{"{UsePropAction.__name__}": ["{self._target_and_message_format_string}"]}}"""
#         self.add_human_message(player_entity, human_message)


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerBehavior(PlayerCommand):

    def __init__(
        self, name: str, rpg_game: RPGGame, player_proxy: PlayerProxy, sentence: str
    ) -> None:
        super().__init__(name, rpg_game, player_proxy)
        self._sentence: str = sentence

    def execute(self) -> None:
        context = self._rpggame._entitas_context
        player_entity = context.get_player_entity(self._player_proxy._name)
        if player_entity is None:
            return
        # /behavior 激活#黑火印记
        # /behavior 攻击@冀州.中山.卢奴.秘密监狱.火字十一号牢房的腐化的木牌
        # 添加行动
        logger.debug(f"PlayerBehavior, {self._player_proxy._name}: {self._sentence}")
        actor_comp = player_entity.get(ActorComponent)
        # /behavior 对@冀州.中山.卢奴.秘密监狱.火字十一号牢房的铁栏门  使用/飞炎咒

        player_entity.add(
            BehaviorAction,
            actor_comp.name,
            BehaviorAction.__name__,
            [self._sentence],
        )

        human_message = f"""{{"{BehaviorAction.__name__}": ["{self._sentence}"]}}"""
        self.simu_player_planning_input_message(player_entity, human_message)


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
