from entitas import (TearDownProcessor, Matcher, Entity) #type: ignore
from auxiliary.components import (
    NPCComponent,
    StageComponent,
    WorldComponent,
)
from auxiliary.actor_agent import ActorAgent
#from agents.tools.extract_md_content import wirte_content_into_md
from auxiliary.prompt_maker import gen_npc_archive_prompt, gen_stage_archive_prompt, gen_world_archive_prompt
from auxiliary.extended_context import ExtendedContext

class DataSaveSystem(TearDownProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__()
        self.context = context

    def tear_down(self) -> None:
        self.output_all_npc_archive()

    def output_all_npc_archive(self) -> None:
        #
        #entities: set[Entity] = self.context.get_group(Matcher(WorldComponent)).entities
        for entity in self.context.get_group(Matcher(WorldComponent)).entities:
            worldcomp: WorldComponent = entity.get(WorldComponent)
            wagent: ActorAgent = worldcomp.agent
            archive_prompt = gen_world_archive_prompt(self.context)
            archive = wagent.request(archive_prompt)
            self.context.savearchive(archive, wagent.name)
            
        # 对Stage的chat_history进行梳理总结输出
        #entities: set[Entity] = self.context.get_group(Matcher(StageComponent)).entities
        for entity in self.context.get_group(Matcher(StageComponent)).entities:
            stagecomp: StageComponent = entity.get(StageComponent)
            sagent: ActorAgent = stagecomp.agent
            archive_prompt = gen_stage_archive_prompt(self.context)
            archive = sagent.request(archive_prompt)
            self.context.savearchive(archive, sagent.name)

        # 对NPC的chat_history进行梳理总结输出
        #entities: set[Entity] = self.context.get_group(Matcher(NPCComponent)).entities
        for entity in self.context.get_group(Matcher(NPCComponent)).entities:
            npccomp: NPCComponent = entity.get(NPCComponent)
            nagent: ActorAgent = npccomp.agent
            archive_prompt = gen_npc_archive_prompt(self.context)
            archive = nagent.request(archive_prompt)
            self.context.savearchive(archive, nagent.name)


