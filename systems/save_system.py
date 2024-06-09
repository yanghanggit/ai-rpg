from typing import override
from entitas import (TearDownProcessor, ExecuteProcessor) #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger


class SaveSystem(ExecuteProcessor, TearDownProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__()
        self.context = context
        self.current_save_count = 0
################################################################################################
    @override
    def execute(self) -> None:
        ## 运行一定次数后自动保存
        if self.context.save_data_enable:
            self.auto_save_all(self.context.auto_save_trigger_count)
################################################################################################
    @override
    def tear_down(self) -> None:
        if self.context.save_data_enable:
            self.save_all()
################################################################################################
    def auto_save_all(self, auto_save_trigger_count: int) -> None:
        assert auto_save_trigger_count > 0
        self.current_save_count += 1
        if self.current_save_count >= auto_save_trigger_count:
            self.current_save_count = 0
            self.save_all()
################################################################################################
    def save_all(self) -> None:
        self.save_world()
        self.save_stage()
        self.save_actor()
################################################################################################
    def save_world(self) -> None:
        #todo
        logger.warning("save_world")
        # agent_connect_system = self.context.agent_connect_system
        # memory_system = self.context.memory_system

        # entities: set[Entity] = self.context.get_group(Matcher(WorldComponent)).entities
        # for entity in entities:
        #     worldcomp: WorldComponent = entity.get(WorldComponent)
        #     archiveprompt = gen_world_archive_prompt(self.context)
        #     genarchive = agent_connect_system.request(worldcomp.name, archiveprompt)
        #     if genarchive is not None:
        #         memory_system.set_and_write_memory(worldcomp.name, genarchive)
        #     else:
        #         chat_history = agent_connect_system.get_chat_history(worldcomp.name)
        #         memory_system.set_and_write_memory(worldcomp.name, self.archive_chat_history(chat_history))
################################################################################################
    def save_stage(self) -> None:
        #todo
        logger.warning("save_stage")
        # agent_connect_system = self.context.agent_connect_system
        # memory_system = self.context.memory_system

        # entites: set[Entity] = self.context.get_group(Matcher(StageComponent)).entities
        # for entity in entites:
        #     stagecomp: StageComponent = entity.get(StageComponent)
        #     archiveprompt = gen_stage_archive_prompt(self.context)
        #     genarchive = agent_connect_system.request(stagecomp.name, archiveprompt)
        #     if genarchive is not None:
        #         memory_system.set_and_write_memory(stagecomp.name, genarchive)
        #     else:
        #         chat_history = agent_connect_system.get_chat_history(stagecomp.name)
        #         memory_system.set_and_write_memory(stagecomp.name, self.archive_chat_history(chat_history))
################################################################################################
    def save_actor(self) -> None:
        #todo
        logger.warning("save_actor")
        # agent_connect_system = self.context.agent_connect_system
        # memory_system = self.context.memory_system

        # entities: set[Entity] = self.context.get_group(Matcher(ActorComponent)).entities
        # for entity in entities:
        #     npccomp: ActorComponent = entity.get(ActorComponent)
        #     archiveprompt = gen_npc_archive_prompt(self.context)
        #     genarchive = agent_connect_system.request(npccomp.name, archiveprompt)
        #     if genarchive is not None:
        #         memory_system.set_and_write_memory(npccomp.name, genarchive)
        #     else:
        #         chat_history = agent_connect_system.get_chat_history(npccomp.name)
        #         memory_system.set_and_write_memory(npccomp.name, self.archive_chat_history(chat_history))
################################################################################################
    # def archive_chat_history(self, chat_history: List[Union[HumanMessage, AIMessage]]) -> str:
    #     if len(chat_history) == 0:
    #         return ""
    #     archive = ""
    #     for message in chat_history:
    #         archive += f"({message.type:} + {message.content}\n)"
    #     return archive
################################################################################################

