from rpg_game import RPGGame
from typing import Optional, Union
from loguru import logger
from auxiliary.components import (
    WorldComponent,
    StageComponent, 
    NPCComponent)
from entitas.entity import Entity
from langchain_core.messages import (
    HumanMessage,
    AIMessage)


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class GMInput:

    def __init__(self, name: str, game: RPGGame) -> None:
        self.name: str = name
        self.game: RPGGame = game
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class GMCommandPush(GMInput):

    def __init__(self, name: str, game: RPGGame, targetname: str, content: str) -> None:
        super().__init__(name, game)
        self.targetname = targetname
        self.content = content

    def execute(self) -> Union[None, NPCComponent, StageComponent, WorldComponent]:
        context = self.game.extendedcontext
        name = self.targetname
        content = self.content
        agent_connect_system = context.agent_connect_system
        
        npc_entity: Optional[Entity] = context.getnpc(name)
        if npc_entity is not None:
            npc_comp: NPCComponent = npc_entity.get(NPCComponent)
            npc_request: Optional[str] = agent_connect_system.request(npc_comp.name, content)
            if npc_request is not None:
                agent_connect_system.remove_last_conversation_between_human_and_ai(npc_comp.name)
            return npc_comp
        
        stage_entity: Optional[Entity] = context.getstage(name)
        if stage_entity is not None:
            stage_comp: StageComponent = stage_entity.get(StageComponent)
            stage_request: Optional[str] = agent_connect_system.request(stage_comp.name, content)
            if stage_request is not None:
                agent_connect_system.remove_last_conversation_between_human_and_ai(stage_comp.name)
            return stage_comp
        
        world_entity: Optional[Entity] = context.get1world()
        if world_entity is not None:
            world_comp: WorldComponent = world_entity.get(WorldComponent)
            request: Optional[str] = agent_connect_system.request(world_comp.name, content)
            if request is not None:
                agent_connect_system.remove_last_conversation_between_human_and_ai(world_comp.name)
            return world_comp

        return None        

####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class GMCommandAsk(GMInput):

    def __init__(self, name: str, game: RPGGame, targetname: str, content: str) -> None:
        super().__init__(name, game)
        self.targetname = targetname
        self.content = content

    def execute(self) -> None:
        gmcommandpush = GMCommandPush(self.name, self.game, self.targetname, self.content)
        unknowncomp = gmcommandpush.execute()
        if unknowncomp is None:
            logger.warning(f"debug_ask: {self.targetname} not found.")
            return
        
        context = self.game.extendedcontext
        agent_connect_system = context.agent_connect_system
        
        if isinstance(unknowncomp, NPCComponent):
            agent_connect_system.remove_last_conversation_between_human_and_ai(unknowncomp.name)
            return
        elif isinstance(unknowncomp, StageComponent):
            agent_connect_system.remove_last_conversation_between_human_and_ai(unknowncomp.name)
            return
        elif isinstance(unknowncomp, WorldComponent):
            agent_connect_system.remove_last_conversation_between_human_and_ai(unknowncomp.name)
            return
    
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class GMCommandLogChatHistory(GMInput):

    def __init__(self, name: str, game: RPGGame, targetname: str) -> None:
        super().__init__(name, game)
        self.targetname = targetname

    def execute(self) -> None:
        context = self.game.extendedcontext
        name = self.targetname
        
        entity = context.getnpc(name)
        if entity is not None:
            npcomp: NPCComponent = entity.get(NPCComponent)
            self.log_chat_history(npcomp.name)
            return
        
        entity = context.getstage(name)
        if entity is not None:
            stagecomp: StageComponent = entity.get(StageComponent)
            self.log_chat_history(stagecomp.name)
            return
        
        entity = context.get1world()
        if entity is not None:
            worldcomp: WorldComponent = entity.get(WorldComponent)
            self.log_chat_history(worldcomp.name)
            return
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
    def log_chat_history(self, targetname: str) -> None:
        agent_connect_system = self.game.extendedcontext.agent_connect_system
        logger.info(f"{'=' * 50}\ndebug_chat_history for {targetname} => :\n")
        chat_history = agent_connect_system.get_chat_history(targetname)
        for history in chat_history:
            if isinstance(history, HumanMessage):
                logger.info(f"Human:{history.content}")
            elif isinstance(history, AIMessage):
                logger.info(f"AI:{history.content}")
        logger.info(f"{'=' * 50}")
        
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################