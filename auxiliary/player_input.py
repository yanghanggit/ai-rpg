from rpg_game import RPGGame
from loguru import logger
from auxiliary.components import (
    BroadcastActionComponent, 
    SpeakActionComponent, 
    StageComponent, 
    NPCComponent, 
    FightActionComponent, 
    PlayerComponent, 
    LeaveForActionComponent, 
    WhisperActionComponent,
    SearchActionComponent,
    PrisonBreakActionComponent)
from auxiliary.actor_action import ActorAction
from auxiliary.player_proxy import PlayerProxy

####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerInput:
    def __init__(self, inputname: str, game: RPGGame, playerproxy: PlayerProxy) -> None:
        self.inputname: str = inputname
        self.game: RPGGame = game
        self.playerproxy: PlayerProxy = playerproxy
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerCommandLogin(PlayerInput):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, targetname: str) -> None:
        super().__init__(name, game, playerproxy)
        self.targetname = targetname

    def execute(self) -> None:
        context = self.game.extendedcontext
        name = self.targetname
        playername = self.playerproxy.name
        logger.debug(f"{self.inputname}, player name: {playername}, target name: {name}")

        npcentity = context.getnpc(name)
        if npcentity is None:
            # 扮演的角色，本身就不存在于这个世界
            logger.error(f"{self.inputname}, npc is None, login failed")
            return

        playerentity = context.getplayer(playername)
        if playerentity is not None:
            # 已经登陆完成
            logger.error(f"{self.inputname}, already login")
            return
        
        playercomp: PlayerComponent = npcentity.get(PlayerComponent)
        if playercomp is None:
            # 扮演的角色不是设定的玩家可控制NPC
            logger.error(f"{self.inputname}, npc is not player ctrl npc, login failed")
            return
        
        if playercomp.name != "" and playercomp.name != playername:
            # 已经有人控制了，但不是你
            logger.error(f"{self.inputname}, player already ctrl by some player, login failed")
            return
    
        npcentity.replace(PlayerComponent, playername)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerCommandChangeCtrlNPC(PlayerInput):
    
    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, npc_name_to_be_controlled: str) -> None:
        super().__init__(name, game, playerproxy)
        self.npc_name_to_be_controlled = npc_name_to_be_controlled

    def execute(self) -> None:
        context = self.game.extendedcontext
        target_npc_name = self.npc_name_to_be_controlled
        myname = self.playerproxy.name

        #寻找要控制的NPC
        to_ctrl_npc_entity = context.getnpc(target_npc_name)
        if to_ctrl_npc_entity is None:
            logger.error(f"{target_npc_name}, npc is None")
            return
        
        if to_ctrl_npc_entity.has(PlayerComponent):
            hisplayercomp: PlayerComponent = to_ctrl_npc_entity.get(PlayerComponent)
            if hisplayercomp.name == myname:
                # 不用继续了
                logger.warning(f"{target_npc_name}, already control {hisplayercomp.name}")
                return
            else:
                # 已经有人控制了，但不是你，你不能抢
                logger.error(f"{target_npc_name}, already control by other player {hisplayercomp.name}")
                return
        else:
            # 可以继续
            logger.debug(f"{target_npc_name} is not controlled by any player")

        logger.debug(f"{self.inputname}, player name: {myname}, target name: {target_npc_name}")
        my_player_entity = context.getplayer(myname)
        if my_player_entity is None:
            # 你现在不控制任何人，就不能做更换，先登陆
            logger.warning(f"{myname}, player is None, can not change control target")
            return
        
        # 更换控制
        my_player_entity.remove(PlayerComponent)
        to_ctrl_npc_entity.add(PlayerComponent, myname)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################     
class PlayerCommandAttack(PlayerInput):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, attack_target_name: str) -> None:
        super().__init__(name, game, playerproxy)
        self.attack_target_name = attack_target_name

    def execute(self) -> None:
        context = self.game.extendedcontext 
        attack_target_name = self.attack_target_name
        playerentity = context.getplayer(self.playerproxy.name)
        if playerentity is None:
            logger.warning("debug_attack: player is None")
            return

        if playerentity.has(NPCComponent):
            npccomp: NPCComponent = playerentity.get(NPCComponent)
            action = ActorAction(npccomp.name, FightActionComponent.__name__, [attack_target_name])
            playerentity.add(FightActionComponent, action)

        elif playerentity.has(StageComponent):
            stagecomp: StageComponent = playerentity.get(StageComponent)
            action = ActorAction(stagecomp.name, FightActionComponent.__name__, [attack_target_name])
            playerentity.add(FightActionComponent, action)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################     
class PlayerCommandLeaveFor(PlayerInput):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, target_stage_name: str) -> None:
        super().__init__(name, game, playerproxy)
        self.target_stage_name = target_stage_name

    def execute(self) -> None:
        context = self.game.extendedcontext
        target_stage_name = self.target_stage_name
        playerentity = context.getplayer(self.playerproxy.name)
        if playerentity is None:
            logger.warning("debug_leave: player is None")
            return
        
        npccomp: NPCComponent = playerentity.get(NPCComponent)
        action = ActorAction(npccomp.name, LeaveForActionComponent.__name__, [target_stage_name])
        playerentity.add(LeaveForActionComponent, action)

        newmsg = f"""{{"{LeaveForActionComponent.__name__}": ["{target_stage_name}"]}}"""
        context.safe_add_human_message_to_entity(playerentity, newmsg)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################     
class PlayerCommandPrisonBreak(PlayerInput):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy) -> None:
        super().__init__(name, game, playerproxy)

    def execute(self) -> None:
        context = self.game.extendedcontext
        playerentity = context.getplayer(self.playerproxy.name)
        if playerentity is None:
            logger.warning("debug_leave: player is None")
            return
        
        npccomp: NPCComponent = playerentity.get(NPCComponent)
        current_stage_name: str = npccomp.current_stage
        stageentity = context.getstage(current_stage_name)
        if stageentity is None:
            logger.error(f"PrisonBreakActionSystem: {current_stage_name} is None")
            return

        action = ActorAction(npccomp.name, PrisonBreakActionComponent.__name__, [current_stage_name])
        playerentity.add(LeaveForActionComponent, action)
        
        newmsg = f"""{{"{PrisonBreakActionComponent.__name__}": ["{current_stage_name}"]}}"""
        context.safe_add_human_message_to_entity(playerentity, newmsg)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerCommandBroadcast(PlayerInput):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, content: str) -> None:
        super().__init__(name, game, playerproxy)
        self.content = content

    def execute(self) -> None:
        context = self.game.extendedcontext
        content = self.content
        playerentity = context.getplayer(self.playerproxy.name)
        if playerentity is None:
            logger.warning("debug_broadcast: player is None")
            return
        
        npccomp: NPCComponent = playerentity.get(NPCComponent)
        action = ActorAction(npccomp.name, BroadcastActionComponent.__name__, [content])
        playerentity.add(BroadcastActionComponent, action)
       
        newmsg = f"""{{"{BroadcastActionComponent.__name__}": ["{content}"]}}"""
        context.safe_add_human_message_to_entity(playerentity, newmsg)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerCommandSpeak(PlayerInput):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, speakcontent: str) -> None:
        super().__init__(name, game, playerproxy)
        self.speakcontent = speakcontent

    def execute(self) -> None:
        context = self.game.extendedcontext
        speakcontent = self.speakcontent
        playerentity = context.getplayer(self.playerproxy.name)
        if playerentity is None:
            logger.warning("debug_speak: player is None")
            return
        
        npccomp: NPCComponent = playerentity.get(NPCComponent)
        action = ActorAction(npccomp.name, SpeakActionComponent.__name__, [speakcontent])
        playerentity.add(SpeakActionComponent, action)
        
        newmsg = f"""{{"{SpeakActionComponent.__name__}": ["{speakcontent}"]}}"""
        context.safe_add_human_message_to_entity(playerentity, newmsg)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerCommandWhisper(PlayerInput):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, whispercontent: str) -> None:
        super().__init__(name, game, playerproxy)
        self.whispercontent = whispercontent

    def execute(self) -> None:
        context = self.game.extendedcontext
        whispercontent = self.whispercontent
        playerentity = context.getplayer(self.playerproxy.name)
        if playerentity is None:
            logger.warning("debug_whisper: player is None")
            return
        
        npccomp: NPCComponent = playerentity.get(NPCComponent)
        action = ActorAction(npccomp.name, WhisperActionComponent.__name__, [whispercontent])
        playerentity.add(WhisperActionComponent, action)

        newmemory = f"""{{"{WhisperActionComponent.__name__}": ["{whispercontent}"]}}"""
        context.safe_add_human_message_to_entity(playerentity, newmemory)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerCommandSearch(PlayerInput):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, search_target_prop_name: str) -> None:
        super().__init__(name, game, playerproxy)
        self.search_target_prop_name = search_target_prop_name

    def execute(self) -> None:
        context = self.game.extendedcontext
        search_target_prop_name = self.search_target_prop_name
        playerentity = context.getplayer(self.playerproxy.name)
        if playerentity is None:
            logger.warning("debug_search: player is None")
            return
        
        npccomp: NPCComponent = playerentity.get(NPCComponent)
        action = ActorAction(npccomp.name, SearchActionComponent.__name__, [search_target_prop_name])
        playerentity.add(SearchActionComponent, action)

        newmemory = f"""{{"{SearchActionComponent.__name__}": ["{search_target_prop_name}"]}}"""
        context.safe_add_human_message_to_entity(playerentity, newmemory)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################