
from entitas import Entity, Matcher, ExecuteProcessor
from components import StageComponent, NPCComponent
from typing import List
from extended_context import ExtendedContext
from prompt_maker import director_prompt
from actor_agent import ActorAgent

class DirectorSystem(ExecuteProcessor):
    """
    The DirectorSystem class is responsible for handling the director's scripts and managing the execution of the game's stages.

    Attributes:
        context (ExtendedContext): The extended context object that provides access to the game's entities and components.

    Methods:
        execute(): Executes the director system by calling the handle() and clear() methods.
        handle(): Handles the stages by iterating through the entities with StageComponent and calling the handlestage() method for each entity.
        clear(): Clears the director scripts of all entities with StageComponent.
        handlestage(entity: Entity): Handles a specific stage entity by printing the director's scripts and prompting the agent for responses.
    """

    def __init__(self, context: ExtendedContext) -> None:
        """
        Initializes a new instance of the DirectorSystem class.

        Args:
            context (ExtendedContext): The extended context object that provides access to the game's entities and components.
        """
        self.context = context

    def execute(self) -> None:
        """
        Executes the director system by calling the handle() and clear() methods.
        """
        print("<<<<<<<<<<<<<  DirectorSystem  >>>>>>>>>>>>>>>>>")
        self.handle()
        self.clear()

    def handle(self) -> None:
        """
        Handles the stages by iterating through the entities with StageComponent and calling the handlestage() method for each entity.
        """
        entities = self.context.get_group(Matcher(StageComponent)).entities
        for entity in entities:
            self.handlestage(entity)
           
    
    def clear(self) -> None:
        """
        Clears the director scripts of all entities with StageComponent.
        """
        entities = self.context.get_group(Matcher(StageComponent)).entities
        for entity in entities:
            comp = entity.get(StageComponent)
            comp.directorscripts.clear()

    def handlestage(self, entity: Entity) -> None:
        """
        Handles a specific stage entity by printing the director's scripts and prompting the agent for responses.

        Args:
            entity (Entity): The stage entity to handle.
        """
        stagecomp = entity.get(StageComponent)
        print(f"[{stagecomp.name}] 开始导演+++++++++++++++++++++++++++++++++++++++++++++++++++++")

        directorscripts: list[str] = stagecomp.directorscripts
        if len(directorscripts) == 0:
            return

        dirprompt = director_prompt("\n".join(directorscripts), entity, self.context)

        print(f"剧本Prompt:\n{dirprompt}\n")
        
        response = stagecomp.agent.request(dirprompt)

        npcs_in_stage = self.context.get_npcs_in_stage(stagecomp.name)
        # npcs_names = "\n".join([npc.get(NPCComponent).name for npc in npcs_in_stage])
        # confirm_prompt = f"""
        # # 你目睹或者参与了这一切，并更新了你的记忆,如果与你记忆不相符则按照下面内容强行更新你的记忆
        # - {response}
        # # 你能确认
        # - {npcs_names} 都还在此 {stagecomp.name} 场景中。
        # """

        ## 直接更新NPC的记忆成导演的剧本
        for npcen in npcs_in_stage:
            npc_comp: NPCComponent = npcen.get(NPCComponent)
            npc_agent: ActorAgent = npc_comp.agent
            npc_agent.add_chat_history(response)

        print(f"[{stagecomp.name}] 结束导演+++++++++++++++++++++++++++++++++++++++++++++++++++++")