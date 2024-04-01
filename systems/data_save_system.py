from typing import List, Union
from langchain_core.messages import HumanMessage, AIMessage
from entitas import (TearDownProcessor, Matcher, Entity) #type: ignore
from auxiliary.components import (
    NPCComponent,
    StageComponent,
    WorldComponent,
)
from auxiliary.actor_agent import ActorAgent
from auxiliary.prompt_maker import gen_npc_archive_prompt, gen_stage_archive_prompt, gen_world_archive_prompt
from auxiliary.extended_context import ExtendedContext

class DataSaveSystem(TearDownProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__()
        self.context = context

    def tear_down(self) -> None:
        self.make_world_archive()
        self.make_stage_archive()
        self.make_npc_archive()

    # 原来的写法在 npccomp 会有问题
    #def make_all_archive(self) -> None:
        # #
        # #entities: set[Entity] = self.context.get_group(Matcher(WorldComponent)).entities
        # for entity in self.context.get_group(Matcher(WorldComponent)).entities:
        #     worldcomp: WorldComponent = entity.get(WorldComponent)
        #     wagent: ActorAgent = worldcomp.agent
        #     archive_prompt = gen_world_archive_prompt(self.context)
        #     archive = wagent.request(archive_prompt)
        #     if archive is not None:
        #         self.context.savearchive(archive, wagent.name)
        #     else:
        #         self.context.savearchive(self.archive_chat_history(npccomp.agent.chat_history), nagent.name)
            
        # # 对Stage的chat_history进行梳理总结输出
        # #entities: set[Entity] = self.context.get_group(Matcher(StageComponent)).entities
        # for entity in self.context.get_group(Matcher(StageComponent)).entities:
        #     stagecomp: StageComponent = entity.get(StageComponent)
        #     sagent: ActorAgent = stagecomp.agent
        #     archive_prompt = gen_stage_archive_prompt(self.context)
        #     archive = sagent.request(archive_prompt)
        #     if archive is not None:
        #         self.context.savearchive(archive, sagent.name)
        #     else:
        #         self.context.savearchive(self.archive_chat_history(npccomp.agent.chat_history), nagent.name)

        # # 对NPC的chat_history进行梳理总结输出
        # #entities: set[Entity] = self.context.get_group(Matcher(NPCComponent)).entities
        # for entity in self.context.get_group(Matcher(NPCComponent)).entities:
        #     npccomp: NPCComponent = entity.get(NPCComponent)
        #     nagent: ActorAgent = npccomp.agent
        #     archive_prompt = gen_npc_archive_prompt(self.context)
        #     archive = nagent.request(archive_prompt)
        #     if archive is not None:
        #         self.context.savearchive(archive, nagent.name)
        #     else:
        #         self.context.savearchive(self.archive_chat_history(npccomp.agent.chat_history), nagent.name)


    def make_world_archive(self) -> None:
        entities: set[Entity] = self.context.get_group(Matcher(WorldComponent)).entities
        for entity in entities:
            worldcomp: WorldComponent = entity.get(WorldComponent)
            wagent: ActorAgent = worldcomp.agent
            archiveprompt = gen_world_archive_prompt(self.context)
            genarchive = wagent.request(archiveprompt)
            if genarchive is not None:
                self.context.savearchive(genarchive, wagent.name)
            else:
                self.context.savearchive(self.archive_chat_history(wagent.chat_history), wagent.name)

    def make_stage_archive(self) -> None:
        entites: set[Entity] = self.context.get_group(Matcher(StageComponent)).entities
        for entity in entites:
            stagecomp: StageComponent = entity.get(StageComponent)
            sagent: ActorAgent = stagecomp.agent
            archiveprompt = gen_stage_archive_prompt(self.context)
            genarchive = sagent.request(archiveprompt)
            if genarchive is not None:
                self.context.savearchive(genarchive, sagent.name)
            else:
                self.context.savearchive(self.archive_chat_history(sagent.agent.chat_history), stagecomp.name)

    def make_npc_archive(self) -> None:
        entities: set[Entity] = self.context.get_group(Matcher(NPCComponent)).entities
        for entity in entities:
            npccomp: NPCComponent = entity.get(NPCComponent)
            nagent: ActorAgent = npccomp.agent
            archiveprompt = gen_npc_archive_prompt(self.context)
            genarchive = nagent.request(archiveprompt)
            if genarchive is not None:
                self.context.savearchive(genarchive, nagent.name)
            else:
                self.context.savearchive(self.archive_chat_history(nagent.chat_history), nagent.name)

    def archive_chat_history(self, chat_history: List[Union[HumanMessage, AIMessage]]) -> str:
        if len(chat_history) == 0:
            return ""
        archive = ""
        for message in chat_history:
            archive += f"({message.type:} + {message.content}\n)"
        return archive


