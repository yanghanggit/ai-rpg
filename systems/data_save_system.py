from typing import List, Union
from langchain_core.messages import HumanMessage, AIMessage
from entitas import (TearDownProcessor, Matcher, Entity, ExecuteProcessor) #type: ignore
from auxiliary.components import (
    NPCComponent,
    StageComponent,
    WorldComponent,
)
from auxiliary.prompt_maker import gen_npc_archive_prompt, gen_stage_archive_prompt, gen_world_archive_prompt
from auxiliary.extended_context import ExtendedContext
from loguru import logger

################################################################################################
class DataSaveSystem(ExecuteProcessor, TearDownProcessor):

    def __init__(self, context: ExtendedContext, auto_save_count: int) -> None:
        super().__init__()
        self.context = context
        self.current_save_count = 0
        self.auto_save_count = auto_save_count
################################################################################################
    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  PreActionSystem  >>>>>>>>>>>>>>>>>")
        self.current_save_count += 1
        if self.current_save_count >= self.auto_save_count:
            self.current_save_count = 0
            self.make_world_archive()
            self.make_stage_archive()
            self.make_npc_archive()
################################################################################################
    def tear_down(self) -> None:
        self.make_world_archive()
        self.make_stage_archive()
        self.make_npc_archive()
################################################################################################
    def make_world_archive(self) -> None:
        agent_connect_system = self.context.agent_connect_system
        memory_system = self.context.memory_system

        entities: set[Entity] = self.context.get_group(Matcher(WorldComponent)).entities
        for entity in entities:
            worldcomp: WorldComponent = entity.get(WorldComponent)
            archiveprompt = gen_world_archive_prompt(self.context)
            genarchive = agent_connect_system._request_(worldcomp.name, archiveprompt)
            if genarchive is not None:
                memory_system.overwritememory(worldcomp.name, genarchive)
            else:
                chat_history = agent_connect_system.get_chat_history(worldcomp.name)
                memory_system.overwritememory(worldcomp.name, self.archive_chat_history(chat_history))
################################################################################################
    def make_stage_archive(self) -> None:
        agent_connect_system = self.context.agent_connect_system
        memory_system = self.context.memory_system

        entites: set[Entity] = self.context.get_group(Matcher(StageComponent)).entities
        for entity in entites:
            stagecomp: StageComponent = entity.get(StageComponent)
            archiveprompt = gen_stage_archive_prompt(self.context)
            genarchive = agent_connect_system._request_(stagecomp.name, archiveprompt)
            if genarchive is not None:
                memory_system.overwritememory(stagecomp.name, genarchive)
            else:
                chat_history = agent_connect_system.get_chat_history(stagecomp.name)
                memory_system.overwritememory(stagecomp.name, self.archive_chat_history(chat_history))
################################################################################################
    def make_npc_archive(self) -> None:
        agent_connect_system = self.context.agent_connect_system
        memory_system = self.context.memory_system

        entities: set[Entity] = self.context.get_group(Matcher(NPCComponent)).entities
        for entity in entities:
            npccomp: NPCComponent = entity.get(NPCComponent)
            archiveprompt = gen_npc_archive_prompt(self.context)
            genarchive = agent_connect_system._request_(npccomp.name, archiveprompt)
            if genarchive is not None:
                memory_system.overwritememory(npccomp.name, genarchive)
            else:
                chat_history = agent_connect_system.get_chat_history(npccomp.name)
                memory_system.overwritememory(npccomp.name, self.archive_chat_history(chat_history))
################################################################################################
    def archive_chat_history(self, chat_history: List[Union[HumanMessage, AIMessage]]) -> str:
        if len(chat_history) == 0:
            return ""
        archive = ""
        for message in chat_history:
            archive += f"({message.type:} + {message.content}\n)"
        return archive
################################################################################################

