from entitas import (
    TearDownProcessor,
    Context,
    Matcher,
    Entity
                     )
from components import (
    NPCComponent,
    StageComponent,
    WorldComponent,
)
from actor_agent import ActorAgent
#from agents.tools.extract_md_content import wirte_content_into_md
from prompt_maker import gen_npc_archive_prompt, gen_stage_archive_prompt, gen_world_archive_prompt
from extended_context import ExtendedContext

class DataSaveSystem(TearDownProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__()
        self.context = context

    def tear_down(self):
        self.output_all_npc_archive()

    def output_all_npc_archive(self) -> None:
        #
        entities: set[Entity] = self.context.get_group(Matcher(WorldComponent)).entities
        for entity in entities:
            comp: WorldComponent = entity.get(WorldComponent)
            agent: ActorAgent = comp.agent
            # archive_prompt = """
            # 请根据上下文，对自己知道的事情进行梳理总结成markdown格式后输出,但不要生成```markdown xxx```的形式:
            # # 游戏世界存档
            # ## 地点
            # ### xxx
            # #### 发生的事件
            # - xxxx
            # - xxxx
            # - xxxx
            # ### xxx
            # #### 发生的事件
            # - xxxx
            # - xxxx
            # - xxxx
            # """
            archive_prompt = gen_world_archive_prompt(self.context)
            archive = agent.request(archive_prompt)
            # print(f"{agent.name}:\n{archive}")
            #wirte_content_into_md(archive, f"/savedData/{agent.name}.md")
            self.context.savearchive(archive, agent.name)
            

        # 对Stage的chat_history进行梳理总结输出
        entities: set[Entity] = self.context.get_group(Matcher(StageComponent)).entities
        for entity in entities:
            comp: StageComponent = entity.get(StageComponent)
            agent: ActorAgent = comp.agent
            # archive_prompt = """
            # 请根据上下文，对自己知道的事情进行梳理总结成markdown格式后输出,但不要生成```markdown xxx```的形式:
            # # 游戏世界存档
            # ## 地点
            # - xxxxx
            # ## 发生的事情
            # - xxxx
            # - xxxx
            # - xxxx
            # """
            archive_prompt = gen_stage_archive_prompt(self.context)
            archive = agent.request(archive_prompt)
            # print(f"{agent.name}:\n{archive}")
            #wirte_content_into_md(archive, f"/savedData/{agent.name}.md")
            self.context.savearchive(archive, agent.name)

        # 对NPC的chat_history进行梳理总结输出
        entities: set[Entity] = self.context.get_group(Matcher(NPCComponent)).entities
        for entity in entities:
            comp: NPCComponent = entity.get(NPCComponent)
            agent: ActorAgent = comp.agent
            # archive_prompt = """
            # 请根据上下文，对自己知道的事情进行梳理总结成markdown格式后输出,但不要生成```markdown xxx```的形式:
            # # 游戏世界存档
            # ## 地点
            # ### xxx
            # #### 和我有关的事
            # - xxxx
            # - xxxx
            # - xxxx
            # - xxxx
            # ### xxx
            # #### 和我有关的事
            # - xxxx
            # - xxxx
            # - xxxx
            # - xxxx
            # """
            archive_prompt = gen_npc_archive_prompt(self.context)
            archive = agent.request(archive_prompt)
            # print(f"{agent.name}:\n{archive}")
            #wirte_content_into_md(archive, f"/savedData/{agent.name}.md")
            self.context.savearchive(archive, agent.name)


