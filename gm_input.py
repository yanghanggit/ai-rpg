from rpg_game import RPGGame
from typing import Optional, Union
from loguru import logger
from auxiliary.components import (
    WorldComponent,
    StageComponent, 
    NPCComponent)
from auxiliary.actor_agent import ActorAgent
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
        
        npc_entity: Optional[Entity] = context.getnpc(name)
        if npc_entity is not None:
            npc_comp: NPCComponent = npc_entity.get(NPCComponent)
            npc_request: Optional[str] = npc_comp.agent.request(content)
            if npc_request is not None:
                npc_comp.agent.chat_history.pop()
            return npc_comp
        
        stage_entity: Optional[Entity] = context.getstage(name)
        if stage_entity is not None:
            stage_comp: StageComponent = stage_entity.get(StageComponent)
            stage_request: Optional[str] = stage_comp.agent.request(content)
            if stage_request is not None:
                stage_comp.agent.chat_history.pop()
            return stage_comp
        
        world_entity: Optional[Entity] = context.getworld()
        if world_entity is not None:
            world_comp: WorldComponent = world_entity.get(WorldComponent)
            request: Optional[str] = world_comp.agent.request(content)
            if request is not None:
                world_comp.agent.chat_history.pop()
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
        pushed_comp = gmcommandpush.execute()
        if pushed_comp is None:
            logger.warning(f"debug_ask: {self.targetname} not found.")
            return
        pushed_agent: ActorAgent = pushed_comp.agent
        pushed_agent.chat_history.pop()
   
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
            npc_comp: NPCComponent = entity.get(NPCComponent)
            npc_agent: ActorAgent = npc_comp.agent
            logger.info(f"{'=' * 50}\ndebug_chat_history for {npc_comp.name} => :")
            for history in npc_agent.chat_history:
                if isinstance(history, HumanMessage):
                    logger.info(f"{'=' * 50}\nHuman:{history.content}")
                elif isinstance(history, AIMessage):
                    logger.info(f"{'=' * 50}\nAI:{history.content}")
            logger.info(f"{'=' * 50}")
            return
        
        entity = context.getstage(name)
        if entity is not None:
            stage_comp: StageComponent = entity.get(StageComponent)
            stage_agent: ActorAgent = stage_comp.agent
            logger.info(f"{'=' * 50}\ndebug_chat_history for {stage_comp.name} => :\n")
            for history in stage_agent.chat_history:
                if isinstance(history, HumanMessage):
                    logger.info(f"Human:{history.content}")
                elif isinstance(history, AIMessage):
                    logger.info(f"AI:{history.content}")
            logger.info(f"{'=' * 50}")
            return
        
        entity = context.getworld()
        if entity is not None:
            world_comp: WorldComponent = entity.get(WorldComponent)
            world_agent: ActorAgent = world_comp.agent
            logger.info(f"{'=' * 50}\ndebug_chat_history for {world_comp.name} => :\n")
            for history in world_agent.chat_history:
                if isinstance(history, HumanMessage):
                    logger.info(f"Human:{history.content}")
                elif isinstance(history, AIMessage):
                    logger.info(f"AI:{history.content}")
            logger.info(f"{'=' * 50}")
            return
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################