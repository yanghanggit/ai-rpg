from entitas import Entity #type: ignore
from rpg_game import RPGGame
from loguru import logger
from auxiliary.components import (BroadcastActionComponent, SpeakActionComponent, StageComponent, ActorComponent, AttackActionComponent, PlayerComponent, 
    GoToActionComponent, UsePropActionComponent, WhisperActionComponent, SearchActionComponent, PortalStepActionComponent,
    PerceptionActionComponent, StealActionComponent, TradeActionComponent, CheckStatusActionComponent)
from auxiliary.actor_plan_and_action import ActorAction
from auxiliary.player_proxy import PlayerProxy
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

    def __init__(self, _description: str, game: RPGGame, playerproxy: PlayerProxy) -> None:
        self._description: str = _description
        self.game: RPGGame = game
        self.playerproxy: PlayerProxy = playerproxy

    @abstractmethod
    def execute(self) -> None:
        pass

    # 为了方便，直接在这里添加消息，不然每个子类都要写一遍
    # player 控制的actor本质和其他actor没有什么不同，这里模拟一个plan的动作。因为每一个actor都是plan -> acton -> direction(同步上下文) -> 再次plan的循环
    def add_human_message(self, entity: Entity, newmsg: str) -> None:
        self.game.extendedcontext.safe_add_human_message_to_entity(entity, newmsg)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerLogin(PlayerCommand):

    """
    玩家登陆的行为，本质就是直接控制一个actor，将actor的playercomp的名字改为玩家的名字
    """

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, actor_name: str) -> None:
        super().__init__(name, game, playerproxy)
        self.actor_name: str = actor_name # 玩家控制的actor.

    def execute(self) -> None:
        context = self.game.extendedcontext
        actor_name = self.actor_name
        player_name = self.playerproxy.name
        logger.debug(f"{self._description}, player name: {player_name}, target name: {actor_name}")

        _entity = context.get_actor_entity(actor_name)
        if _entity is None:
            # 扮演的角色，本身就不存在于这个世界
            logger.error(f"{actor_name}, actor is None, login failed")
            return

        playerentity = context.get_player_entity(player_name)
        if playerentity is not None:
            # 已经登陆完成
            logger.error(f"{player_name}, already login")
            return
        
        playercomp: PlayerComponent = _entity.get(PlayerComponent)
        if playercomp is None:
            # 扮演的角色不是设定的玩家可控制Actor
            logger.error(f"{actor_name}, actor is not player ctrl actor, login failed")
            return
        
        if playercomp.name != "" and playercomp.name != player_name:
            # 已经有人控制了，但不是你
            logger.error(f"{actor_name}, player already ctrl by some player {playercomp.name}, login failed")
            return
    
        # 更改player的名字，算作登陆成功
        _entity.replace(PlayerComponent, player_name)

        # todo 添加游戏的介绍到客户端消息中
        self.playerproxy.add_system_message(self.game.about_game)
        
        # todo 添加登陆新的信息到客户端消息中
        time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.playerproxy.add_system_message(f"login: {player_name}, time = {time}")

        # actor的kickoff记忆到客户端消息中
        kick_off_memory = context.kick_off_memory_system.get_kick_off_memory(self.actor_name)
        self.playerproxy.add_actor_message(self.actor_name, kick_off_memory)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################   
class PlayerAttack(PlayerCommand):

    """
    玩家攻击的行为：AttackActionComponent
    """

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, attack_target_name: str) -> None:
        super().__init__(name, game, playerproxy)
        self.attack_target_name: str= attack_target_name

    def execute(self) -> None:
        context = self.game.extendedcontext 
        attack_target_name = self.attack_target_name
        playerentity = context.get_player_entity(self.playerproxy.name)
        if playerentity is None:
            logger.warning("debug_attack: player is None")
            return

        if playerentity.has(ActorComponent):
            actor_comp: ActorComponent = playerentity.get(ActorComponent)
            action = ActorAction(actor_comp.name, AttackActionComponent.__name__, [attack_target_name])
            playerentity.add(AttackActionComponent, action)

        elif playerentity.has(StageComponent):
            stagecomp: StageComponent = playerentity.get(StageComponent)
            action = ActorAction(stagecomp.name, AttackActionComponent.__name__, [attack_target_name])
            playerentity.add(AttackActionComponent, action)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################     
class PlayerGoTo(PlayerCommand):

    """
    玩家移动的行为：GoToActionComponent
    """

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, target_stage_name: str) -> None:
        super().__init__(name, game, playerproxy)
        self.target_stage_name: str = target_stage_name

    def execute(self) -> None:
        context = self.game.extendedcontext
        target_stage_name = self.target_stage_name
        playerentity = context.get_player_entity(self.playerproxy.name)
        if playerentity is None:
            # 玩家实体不存在
            logger.warning("debug: player is None")
            return
        
        # 添加行动
        actor_comp: ActorComponent = playerentity.get(ActorComponent)
        action = ActorAction(actor_comp.name, GoToActionComponent.__name__, [target_stage_name])
        playerentity.add(GoToActionComponent, action)

        # 模拟添加一个plan的发起。
        human_message = f"""{{"{GoToActionComponent.__name__}": ["{target_stage_name}"]}}"""
        self.add_human_message(playerentity, human_message)
####################################################################################################################################
####################################################################################################################################
#################################################################################################################################### 
class PlayerPortalStep(PlayerCommand):

    """
    玩家传送的行为：PortalStepActionComponent    
    """

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy) -> None:
        super().__init__(name, game, playerproxy)

    def execute(self) -> None:
        context = self.game.extendedcontext
        playerentity = context.get_player_entity(self.playerproxy.name)
        if playerentity is None:
            logger.warning("debug: player is None")
            return
        
        actor_comp: ActorComponent = playerentity.get(ActorComponent)
        current_stage_name: str = actor_comp.current_stage
        stageentity = context.get_stage_entity(current_stage_name)
        if stageentity is None:
            logger.error(f"PortalStepActionSystem: {current_stage_name} is None")
            return

        # 添加一个行动
        action = ActorAction(actor_comp.name, PortalStepActionComponent.__name__, [current_stage_name])
        playerentity.add(PortalStepActionComponent, action)
        
        # 模拟添加一个plan的发起。
        human_message = f"""{{"{PortalStepActionComponent.__name__}": ["{current_stage_name}"]}}"""
        self.add_human_message(playerentity, human_message)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerBroadcast(PlayerCommand):

    """
    玩家广播的行为：BroadcastActionComponent
    """

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, content: str) -> None:
        super().__init__(name, game, playerproxy)
        self.content: str = content

    def execute(self) -> None:
        context = self.game.extendedcontext
        content = self.content
        playerentity = context.get_player_entity(self.playerproxy.name)
        if playerentity is None:
            logger.warning("debug_broadcast: player is None")
            return
        
        # 添加行动
        actor_comp: ActorComponent = playerentity.get(ActorComponent)
        action = ActorAction(actor_comp.name, BroadcastActionComponent.__name__, [content])
        playerentity.add(BroadcastActionComponent, action)

        # 模拟添加一个plan的发起。
        human_message = f"""{{"{BroadcastActionComponent.__name__}": ["{content}"]}}"""
        self.add_human_message(playerentity, human_message)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerSpeak(PlayerCommand):

    """
    玩家说话的行为：SpeakActionComponent
    """

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, speakcontent: str) -> None:
        super().__init__(name, game, playerproxy)
        self.speakcontent: str = speakcontent

    def execute(self) -> None:
        context = self.game.extendedcontext
        speakcontent = self.speakcontent
        playerentity = context.get_player_entity(self.playerproxy.name)
        if playerentity is None:
            logger.warning("debug_speak: player is None")
            return
        
        # 添加行动
        actor_comp: ActorComponent = playerentity.get(ActorComponent)
        action = ActorAction(actor_comp.name, SpeakActionComponent.__name__, [speakcontent])
        playerentity.add(SpeakActionComponent, action)
        
        # 模拟添加一个plan的发起。
        human_message = f"""{{"{SpeakActionComponent.__name__}": ["{speakcontent}"]}}"""
        self.add_human_message(playerentity, human_message)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerWhisper(PlayerCommand):

    """
    玩家私聊的行为：WhisperActionComponent
    """

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, whispercontent: str) -> None:
        super().__init__(name, game, playerproxy)
        self.whispercontent: str = whispercontent

    def execute(self) -> None:
        context = self.game.extendedcontext
        whispercontent = self.whispercontent
        playerentity = context.get_player_entity(self.playerproxy.name)
        if playerentity is None:
            logger.warning("debug_whisper: player is None")
            return
        
        # 添加行动
        actor_comp: ActorComponent = playerentity.get(ActorComponent)
        action = ActorAction(actor_comp.name, WhisperActionComponent.__name__, [whispercontent])
        playerentity.add(WhisperActionComponent, action)

        # 模拟添加一个plan的发起。
        human_message = f"""{{"{WhisperActionComponent.__name__}": ["{whispercontent}"]}}"""
        self.add_human_message(playerentity, human_message)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerSearch(PlayerCommand):

    """
    玩家搜索的行为：SearchActionComponent
    """

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, search_target_prop_name: str) -> None:
        super().__init__(name, game, playerproxy)
        self.search_target_prop_name: str = search_target_prop_name

    def execute(self) -> None:
        context = self.game.extendedcontext
        search_target_prop_name = self.search_target_prop_name
        playerentity = context.get_player_entity(self.playerproxy.name)
        if playerentity is None:
            logger.warning("debug_search: player is None")
            return
        
        # 添加行动
        actor_comp: ActorComponent = playerentity.get(ActorComponent)
        action = ActorAction(actor_comp.name, SearchActionComponent.__name__, [search_target_prop_name])
        playerentity.add(SearchActionComponent, action)

        # 模拟添加一个plan的发起。
        human_message = f"""{{"{SearchActionComponent.__name__}": ["{search_target_prop_name}"]}}"""
        self.add_human_message(playerentity, human_message)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerPerception(PlayerCommand):

    """
    玩家感知的行为：PerceptionActionComponent
    """

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy) -> None:
        super().__init__(name, game, playerproxy)
        

    def execute(self) -> None:
        context = self.game.extendedcontext
        playerentity = context.get_player_entity(self.playerproxy.name)
        if playerentity is None:
            return
        
        # 添加行动
        actor_comp: ActorComponent = playerentity.get(ActorComponent)
        action = ActorAction(actor_comp.name, PerceptionActionComponent.__name__, [actor_comp.current_stage])
        playerentity.add(PerceptionActionComponent, action)

        # 模拟添加一个plan的发起。
        human_message = f"""{{"{PerceptionActionComponent.__name__}": ["{actor_comp.current_stage}"]}}"""
        self.add_human_message(playerentity, human_message)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerSteal(PlayerCommand):

    """
    玩家偷东西的行为：StealActionComponent
    """

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, command: str) -> None:
        super().__init__(name, game, playerproxy)
        # "@要偷的人>偷他的啥东西"
        self.command: str = command

    def execute(self) -> None:
        context = self.game.extendedcontext
        playerentity = context.get_player_entity(self.playerproxy.name)
        if playerentity is None:
            return
        
        # 添加行动
        actor_comp: ActorComponent = playerentity.get(ActorComponent)
        action = ActorAction(actor_comp.name, StealActionComponent.__name__, [self.command])
        playerentity.add(StealActionComponent, action)

        # 模拟添加一个plan的发起。
        human_message = f"""{{"{StealActionComponent.__name__}": ["{self.command}"]}}"""
        self.add_human_message(playerentity, human_message)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerTrade(PlayerCommand):
    
    """
    玩家交易的行为：TradeActionComponent
    """

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, command: str) -> None:
        super().__init__(name, game, playerproxy)
        # "@交易的对象>我的啥东西"
        self.command: str = command

    def execute(self) -> None:
        context = self.game.extendedcontext
        playerentity = context.get_player_entity(self.playerproxy.name)
        if playerentity is None:
            return
        
        # 添加行动
        actor_comp: ActorComponent = playerentity.get(ActorComponent)
        action = ActorAction(actor_comp.name, TradeActionComponent.__name__, [self.command])
        playerentity.add(TradeActionComponent, action)

        # 模拟添加一个plan的发起。
        human_message = f"""{{"{TradeActionComponent.__name__}": ["{self.command}"]}}"""
        self.add_human_message(playerentity, human_message)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerCheckStatus(PlayerCommand):
    
    """
    玩家查看状态的行为：CheckStatusActionComponent
    """

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy) -> None:
        super().__init__(name, game, playerproxy)

    def execute(self) -> None:
        context = self.game.extendedcontext
        playerentity = context.get_player_entity(self.playerproxy.name)
        if playerentity is None:
            return
        
        if playerentity.has(CheckStatusActionComponent):
            logger.warning("debug: player has CheckStatusActionComponent????") # 应该是有问题的，如果存在。
            playerentity.remove(CheckStatusActionComponent)
        
        # 添加行动
        actor_comp: ActorComponent = playerentity.get(ActorComponent)
        action = ActorAction(actor_comp.name, CheckStatusActionComponent.__name__, [actor_comp.name])
        playerentity.add(CheckStatusActionComponent, action)

        # 模拟添加一个plan的发起。
        human_message = f"""{{"{CheckStatusActionComponent.__name__}": ["{actor_comp.name}"]}}"""
        self.add_human_message(playerentity, human_message)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerUseProp(PlayerCommand):
    
    """
    玩家使用道具的行为：UsePropActionComponent
    """

    def __init__(self, inputname: str, game: RPGGame, playerproxy: PlayerProxy, command: str) -> None:
        super().__init__(inputname, game, playerproxy)
        # "@使用道具对象>道具名"
        self.command: str = command

    def execute(self) -> None:
        context = self.game.extendedcontext
        playerentity = context.get_player_entity(self.playerproxy.name)
        if playerentity is None:
            return
        
        # 添加行动
        actor_comp: ActorComponent = playerentity.get(ActorComponent)
        action = ActorAction(actor_comp.name, UsePropActionComponent.__name__, [self.command])
        playerentity.add(UsePropActionComponent, action)

        # 模拟添加一个plan的发起。
        human_message = f"""{{"{UsePropActionComponent.__name__}": ["{self.command}"]}}"""
        self.add_human_message(playerentity, human_message)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################