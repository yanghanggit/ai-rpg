from entitas import Entity  # type: ignore
from rpg_game.rpg_game import RPGGame
from loguru import logger
from gameplay_systems.action_components import (
    BroadcastAction,
    SpeakAction,
    GoToAction,
    WhisperAction,
    PickUpPropAction,
    StealPropAction,
    GivePropAction,
    BehaviorAction,
)
from gameplay_systems.components import (
    ActorComponent,
    PlayerComponent,
    PlayerIsWebClientComponent,
    PlayerIsTerminalClientComponent,
)
from player.player_proxy import PlayerProxy
from abc import ABC, abstractmethod
import datetime


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

    def simu_player_planning_input_message(
        self, entity: Entity, human_message_content: str
    ) -> None:
        self._rpggame._entitas_context.safe_add_ai_message_to_entity(
            entity, human_message_content
        )


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerLogin(PlayerCommand):

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

        if not actor_entity.has(PlayerComponent):
            # 扮演的角色不是设定的玩家可控制Actor
            logger.error(f"{actor_name}, actor is not player ctrl actor, login failed")
            return

        player_comp = actor_entity.get(PlayerComponent)
        assert player_comp is not None

        if player_comp.name != "" and player_comp.name != player_name:
            # 已经有人控制了，但不是你
            logger.error(
                f"{actor_name}, player already ctrl by some player {player_comp.name}, login failed"
            )
            return

        # 更改算作登陆成功
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
        kick_off_messages = context._kick_off_message_system.get_message(
            self._actor_name
        )
        if len(kick_off_messages) == 0 or len(kick_off_messages) > 1:
            return
        self._player_proxy.add_login_message(
            self._actor_name, kick_off_messages[0].content
        )


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

        self.simu_player_planning_input_message(
            player_entity, f"""{{"{GoToAction.__name__}": ["{target_stage_name}"]}}"""
        )


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
        self.simu_player_planning_input_message(
            player_entity,
            f"""{{"{BroadcastAction.__name__}": ["{self._broadcast_content}"]}}""",
        )


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

        self.simu_player_planning_input_message(
            player_entity,
            f"""{{"{SpeakAction.__name__}": ["{self._speak_content}"]}}""",
        )


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
        self.simu_player_planning_input_message(
            player_entity,
            f"""{{"{WhisperAction.__name__}": ["{self._whisper_content}"]}}""",
        )


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerPickUpProp(PlayerCommand):

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
        self.simu_player_planning_input_message(
            player_entity,
            f"""{{"{PickUpPropAction.__name__}": ["{self._prop_name}"]}}""",
        )


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
        self.simu_player_planning_input_message(
            player_entity,
            f"""{{"{StealPropAction.__name__}": ["{self._target_and_message_format_string}"]}}""",
        )


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

        self.simu_player_planning_input_message(
            player_entity,
            f"""{{"{GivePropAction.__name__}": ["{self._target_and_message_format_string}"]}}""",
        )


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

        logger.debug(f"PlayerBehavior, {self._player_proxy._name}: {self._sentence}")
        actor_comp = player_entity.get(ActorComponent)

        player_entity.add(
            BehaviorAction,
            actor_comp.name,
            BehaviorAction.__name__,
            [self._sentence],
        )

        self.simu_player_planning_input_message(
            player_entity, f"""{{"{BehaviorAction.__name__}": ["{self._sentence}"]}}"""
        )


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
