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
    HumanInterferenceComponent,
    WhisperActionComponent,
    SearchActionComponent)
from auxiliary.actor_action import ActorAction
from player_proxy import PlayerProxy

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
class PlayerCommandNPC(PlayerInput):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, targetname: str) -> None:
        super().__init__(name, game, playerproxy)
        self.targetname = targetname

    def execute(self) -> None:

        context = self.game.extendedcontext
        name = self.targetname
        playname = self.playerproxy.name

        playerentity = context.get1player()
        if playerentity is not None:
            playercomp: PlayerComponent = playerentity.get(PlayerComponent)
            logger.debug(f"{self.inputname}, current player name: {playercomp.name}")
            playerentity.remove(PlayerComponent)

        entity = context.getnpc(name)
        if entity is not None:
            npccomp: NPCComponent = entity.get(NPCComponent)
            logger.debug(f"{self.inputname}: [{npccomp.name}] is now controlled by the player [{playname}]")
            entity.add(PlayerComponent, playname)
            return
        
        entity = context.getstage(name)
        if entity is not None:
            stagecomp: StageComponent = entity.get(StageComponent)
            logger.debug(f"{self.inputname}: [{stagecomp.name}] is now controlled by the player [{playname}]")
            entity.add(PlayerComponent, playname)
            return
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################     
class PlayerCommandAttack(PlayerInput):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, targetname: str) -> None:
        super().__init__(name, game, playerproxy)
        self.targetname = targetname

    def execute(self) -> None:
        context = self.game.extendedcontext 
        dest = self.targetname
        playerentity = context.get1player()
        if playerentity is None:
            logger.warning("debug_attack: player is None")
            return
        
        if playerentity.has(NPCComponent):
            npc_comp: NPCComponent = playerentity.get(NPCComponent)
            action = ActorAction(npc_comp.name, "FightActionComponent", [dest])
            playerentity.add(FightActionComponent, action)
            if not playerentity.has(HumanInterferenceComponent):
                playerentity.add(HumanInterferenceComponent, f'{npc_comp.name}攻击{dest}')
            logger.debug(f"debug_attack: {npc_comp.name} add {action}")
            return
        
        elif playerentity.has(StageComponent):
            stage_comp: StageComponent = playerentity.get(StageComponent)
            action = ActorAction(stage_comp.name, "FightActionComponent", [dest])
            if not playerentity.has(HumanInterferenceComponent):
                playerentity.add(HumanInterferenceComponent, f'{stage_comp.name}攻击{dest}')
            playerentity.add(FightActionComponent, action)
            logger.debug(f"debug_attack: {stage_comp.name} add {action}")
            return
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################     
class PlayerCommandLeaveFor(PlayerInput):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, stagename: str) -> None:
        super().__init__(name, game, playerproxy)
        self.stagename = stagename

    def execute(self) -> None:
        context = self.game.extendedcontext
        stagename = self.stagename
        playerentity = context.get1player()
        if playerentity is None:
            logger.warning("debug_leave: player is None")
            return
        
        npc_comp: NPCComponent = playerentity.get(NPCComponent)
        action = ActorAction(npc_comp.name, "LeaveForActionComponent", [stagename])
        playerentity.add(LeaveForActionComponent, action)
        if not playerentity.has(HumanInterferenceComponent):
            playerentity.add(HumanInterferenceComponent, f'{npc_comp.name}离开了{stagename}')

        newmemory = f"""{{
            "LeaveForActionComponent": ["{stagename}"]
        }}"""
        context.add_agent_memory(playerentity, newmemory)
        logger.debug(f"debug_leave: {npc_comp.name} add {action}")
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
        playerentity = context.get1player()
        if playerentity is None:
            logger.warning("debug_broadcast: player is None")
            return
        
        npc_comp: NPCComponent = playerentity.get(NPCComponent)
        action = ActorAction(npc_comp.name, "BroadcastActionComponent", [content])
        playerentity.add(BroadcastActionComponent, action)
        playerentity.add(HumanInterferenceComponent, f'{npc_comp.name}大声说道：{content}')

        newmemory = f"""{{
            "BroadcastActionComponent": ["{content}"]
        }}"""
        context.add_agent_memory(playerentity, newmemory)
        logger.debug(f"debug_broadcast: {npc_comp.name} add {action}")
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerCommandSpeak(PlayerInput):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, commandstr: str) -> None:
        super().__init__(name, game, playerproxy)
        self.commandstr = commandstr

    def execute(self) -> None:
        context = self.game.extendedcontext
        content = self.commandstr
        playerentity = context.get1player()
        if playerentity is None:
            logger.warning("debug_speak: player is None")
            return
        
        npc_comp: NPCComponent = playerentity.get(NPCComponent)
        action = ActorAction(npc_comp.name, "SpeakActionComponent", [content])
        playerentity.add(SpeakActionComponent, action)
        if not playerentity.has(HumanInterferenceComponent):
            playerentity.add(HumanInterferenceComponent, f'{npc_comp.name}说道：{content}')

        newmemory = f"""{{
            "SpeakActionComponent": ["{content}"]
        }}"""
        context.add_agent_memory(playerentity, newmemory)
        logger.debug(f"debug_speak: {npc_comp.name} add {action}")
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerCommandWhisper(PlayerInput):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, commandstr: str) -> None:
        super().__init__(name, game, playerproxy)
        self.commandstr = commandstr

    def execute(self) -> None:
        context = self.game.extendedcontext
        content = self.commandstr
        playerentity = context.get1player()
        if playerentity is None:
            logger.warning("debug_whisper: player is None")
            return
        
        npc_comp: NPCComponent = playerentity.get(NPCComponent)
        action = ActorAction(npc_comp.name, "WhisperActionComponent", [content])
        playerentity.add(WhisperActionComponent, action)
        if not playerentity.has(HumanInterferenceComponent):
            playerentity.add(HumanInterferenceComponent, f'{npc_comp.name}低语道：{content}')

        newmemory = f"""{{
            "WhisperActionComponent": ["{content}"]
        }}"""
        context.add_agent_memory(playerentity, newmemory)
        logger.debug(f"debug_whisper: {npc_comp.name} add {action}")
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerCommandSearch(PlayerInput):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, targetname: str) -> None:
        super().__init__(name, game, playerproxy)
        self.targetname = targetname

    def execute(self) -> None:
        context = self.game.extendedcontext
        content = self.targetname
        playerentity = context.get1player()
        if playerentity is None:
            logger.warning("debug_search: player is None")
            return
        
        npc_comp: NPCComponent = playerentity.get(NPCComponent)
        action = ActorAction(npc_comp.name, "SearchActionComponent", [content])
        playerentity.add(SearchActionComponent, action)
        if not playerentity.has(HumanInterferenceComponent):
            playerentity.add(HumanInterferenceComponent, f'{npc_comp.name}搜索{content}')

        newmemory = f"""{{
            "SearchActionComponent": ["{content}"]
        }}"""
        context.add_agent_memory(playerentity, newmemory)
        logger.debug(f"debug_search: {npc_comp.name} add {action}")
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################