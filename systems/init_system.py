from auxiliary.file_def import KnownNPCFile, KnownStageFile
from entitas import Entity, Matcher, InitializeProcessor # type: ignore
from auxiliary.components import WorldComponent, StageComponent, NPCComponent, PlayerComponent
from auxiliary.cn_builtin_prompt import (read_archives_when_system_init_prompt,
                                    read_all_neccesary_info_when_system_init_prompt)
from auxiliary.extended_context import ExtendedContext
# from langchain_core.messages import (HumanMessage, 
#                                     AIMessage)
from loguru import logger
from systems.known_information_helper import KnownInformationHelper


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
class InitSystem(InitializeProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
      
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
    def initialize(self) -> None:
        logger.debug("<<<<<<<<<<<<<  InitSystem  >>>>>>>>>>>>>>>>>")

        ##连接所有的agent
        self.connect_agents()
        
        ##初始化所有的记忆
        # self.read_agent_memory()
        self.init_agent_all_neccesary_memory()
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
    def connect_agents(self) -> None:
        #
        agent_connect_system = self.context.agent_connect_system
        #
        worlds: set[Entity] = self.context.get_group(Matcher(WorldComponent)).entities
        for world in worlds:
            worldcomp: WorldComponent = world.get(WorldComponent)
            agent_connect_system.connect_actor_agent(worldcomp.name)

        stages: set[Entity] = self.context.get_group(Matcher(StageComponent)).entities
        for stage in stages:
            stagecomp: StageComponent = stage.get(StageComponent)
            agent_connect_system.connect_actor_agent(stagecomp.name)

        #player agent不做连接操作，后面如果调用报错无所谓，因为服务器没连接
        npcs: set[Entity] = self.context.get_group(Matcher(all_of=[NPCComponent], none_of=[PlayerComponent])).entities
        for npc in npcs:
            npccomp: NPCComponent = npc.get(NPCComponent)
            agent_connect_system.connect_actor_agent(npccomp.name)
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
    def read_agent_memory(self) -> None:
        #
        context = self.context
        memory_system = context.memory_system
        agent_connect_system = context.agent_connect_system
        #chaos_engineering_system = context.chaos_engineering_system
        #
        worlds: set[Entity] = context.get_group(Matcher(WorldComponent)).entities
        for world in worlds:
            worldcomp: WorldComponent = world.get(WorldComponent)
            worldmemory = memory_system.getmemory(worldcomp.name)
            if worldmemory == "":
                logger.error(f"worldmemory is empty: {worldcomp.name}")
                continue
            readarchprompt = read_archives_when_system_init_prompt(worldmemory, world, context)
            # response = agent_connect_system.request(worldcomp.name, readarchprompt)
            # if response is None:
            #     chaos_engineering_system.on_read_memory_failed(context, worldcomp.name, readarchprompt)
            agent_connect_system.add_async_requet_task(worldcomp.name, readarchprompt)

        ##
        stages: set[Entity] = context.get_group(Matcher(StageComponent)).entities
        for stage in stages:
            stagecomp: StageComponent = stage.get(StageComponent)
            stagememory = memory_system.getmemory(stagecomp.name)
            if stagememory == "":
                logger.error(f"stagememory is empty: {stagecomp.name}")
                continue
            readarchprompt = read_archives_when_system_init_prompt(stagememory, stage, context)
            # response = agent_connect_system.request(stagecomp.name, readarchprompt)
            # if response is None:
            #     chaos_engineering_system.on_read_memory_failed(context, stagecomp.name, readarchprompt)
            agent_connect_system.add_async_requet_task(stagecomp.name, readarchprompt)

        ##
        npcs: set[Entity] = context.get_group(Matcher(all_of=[NPCComponent])).entities
        for npc in npcs:
            npccomp: NPCComponent = npc.get(NPCComponent)
            npcmemory = memory_system.getmemory(npccomp.name)
            if npcmemory == "":
                logger.error(f"npcmemory is empty: {npccomp.name}")
                continue
            readarchprompt = read_archives_when_system_init_prompt(npcmemory, npc, context)
            # response = agent_connect_system.request(npccomp.name, readarchprompt)
            # if response is None:
            #     chaos_engineering_system.on_read_memory_failed(context, npccomp.name, readarchprompt)
            agent_connect_system.add_async_requet_task(npccomp.name, readarchprompt)

        ##
        agent_connect_system.run_async_requet_tasks()

###############################################################################################################################################
###############################################################################################################################################
    def init_agent_all_neccesary_memory(self) -> None:
        #
        context = self.context
        memory_system = context.memory_system
        #file_system = context.file_system
        agent_connect_system = context.agent_connect_system
        #chaos_engineering_system = context.chaos_engineering_system

        #refactor
        known_info_helper = KnownInformationHelper(context)
        known_info_helper.build()

        #
        worlds: set[Entity] = context.get_group(Matcher(WorldComponent)).entities
        for world in worlds:
            worldcomp: WorldComponent = world.get(WorldComponent)
            worldmemory = memory_system.getmemory(worldcomp.name)
            if worldmemory == "":
                logger.error(f"worldmemory is empty: {worldcomp.name}")
                continue
            readarchprompt = read_archives_when_system_init_prompt(worldmemory, world, context)
            # response = agent_connect_system.request(worldcomp.name, readarchprompt)
            # if response is None:
            #     chaos_engineering_system.on_read_memory_failed(context, worldcomp.name, readarchprompt)
            agent_connect_system.add_async_requet_task(worldcomp.name, readarchprompt)

       #allstagenames: set[str] = set()
        ##
        stages: set[Entity] = context.get_group(Matcher(StageComponent)).entities
        for stage in stages:
            stagecomp: StageComponent = stage.get(StageComponent)
            stagememory = memory_system.getmemory(stagecomp.name)
            if stagememory == "":
                logger.error(f"stagememory is empty: {stagecomp.name}")
                continue
            readarchprompt = read_archives_when_system_init_prompt(stagememory, stage, context)
            # response = agent_connect_system.request(stagecomp.name, readarchprompt)
            # if response is None:
            #     chaos_engineering_system.on_read_memory_failed(context, stagecomp.name, readarchprompt)
            agent_connect_system.add_async_requet_task(stagecomp.name, readarchprompt)

            #allstagenames.add(stagecomp.name)
        
        # allnpcnames: set[str] = set()
        npcs: set[Entity] = context.get_group(Matcher(all_of=[NPCComponent])).entities
        # for npc_entity in npcs:
        #     npccomp1: NPCComponent = npc_entity.get(NPCComponent)
        #     allnpcnames.add(npccomp1.name)
        ##
        for npc in npcs:
            npccomp: NPCComponent = npc.get(NPCComponent)
            # prop and desc
            # props = file_system.get_prop_files(npccomp.name)
            # prop_and_desc: list[str] = []
            # for prop in props:
            #     prop_and_desc.append(f"{prop.name}:{prop.prop.description}")
            
            # extract where you know from prop
            # whereyouknow0: set[str] = set()
            # for stage_name in allstagenames:
            #     for prop_desc in prop_and_desc:
            #         if stage_name in prop_desc:
            #             whereyouknow0.add(stage_name)

            #npcmemory = memory_system.getmemory(npccomp.name)
            # who you know
            # whoyouknow1 = self.who_you_know_in_memory(npcsmem, allnpcnames)
            # # 从chat history中提取所有的关系
            # chathistory = agent_connect_system.get_chat_history(npccomp.name)
            # whoyouknow2 = self.who_you_know_in_chat_history(chathistory, allnpcnames)
            # # 最后关系网的网，更新进去
            # merge_who_you_know = whoyouknow1 | whoyouknow2

            who_do_you_know = known_info_helper.who_do_you_know(npccomp.name)
            self.add_known_npc_file(npccomp.name, who_do_you_know)
            #self.add_known_npc_file(npccomp.name, merge_who_you_know)

            # where you know
            # whereyouknow1 = self.where_you_know_in_memory(npcsmem, allstagenames)
            # chathistory = agent_connect_system.get_chat_history(npccomp.name)
            # whereyouknow2 = self.where_you_know_in_chat_history(chathistory, allstagenames)
            # merge_where_you_know = whereyouknow0 | whereyouknow1 | whereyouknow2 

            where_do_you_know = known_info_helper.where_do_you_know(npccomp.name)
            self.add_known_stage_file(npccomp.name, where_do_you_know)
            #self.add_known_stage_file(npccomp.name, merge_where_you_know)


            # where you can leave for
            #merge_where_you_know.discard(npccomp.current_stage)
            # 放弃当前地点，因为提示词中不应该包含当前地点
            where_you_can_go = where_do_you_know.copy()
            where_you_can_go.discard(npccomp.current_stage)


            # init memory
            # npcmemory = memory_system.getmemory(npccomp.name)
            # if npcmemory == "":
            #     logger.error(f"npcmemory is empty: {npccomp.name}")
            #     continue
            

            #切成字符串，给read_all_neccesary_info_when_system_init_prompt            
            props_info_prompt = ""
            listinfo = known_info_helper.get_npcs_with_props_info(npccomp.name)
            if len(listinfo) > 0:
                props_info_prompt = "\n".join(listinfo)
            
            where_you_can_go_prompt = ""
            if len(where_you_can_go) > 0:
                where_you_can_go_prompt = ",".join(where_you_can_go)

            who_do_you_know_prompt = ""
            if len(who_do_you_know) > 0:
                who_do_you_know_prompt = ",".join(who_do_you_know)

            #readarchprompt = read_all_neccesary_info_when_system_init_prompt(npcsmem, prop_and_desc, npccomp.current_stage, merge_where_you_know, merge_who_you_know)
            readarchprompt = read_all_neccesary_info_when_system_init_prompt(memory_system.getmemory(npccomp.name), 
                                                                             props_info_prompt, 
                                                                             npccomp.current_stage, 
                                                                             where_you_can_go_prompt, 
                                                                             who_do_you_know_prompt)

            
            
            # response = agent_connect_system.request(npccomp.name, readarchprompt)
            # if response is None:
            #     chaos_engineering_system.on_read_memory_failed(context, npccomp.name, readarchprompt)
            agent_connect_system.add_async_requet_task(npccomp.name, readarchprompt)

        ##
        agent_connect_system.run_async_requet_tasks()

###############################################################################################################################################
#     def who_you_know_in_memory(self, yourmemory: str, allnames: set[str]) -> set[str]:
#         return self.frommemory(yourmemory, allnames)
    
#     def who_you_know_in_chat_history(self, chathistory: list[HumanMessage | AIMessage], allnames: set[str]) -> set[str]:
#         return self.from_chat_history(chathistory, allnames)
# ###############################################################################################################################################
#     def where_you_know_in_memory(self, yourmemory: str, allnames: set[str]) -> set[str]:
#         return self.frommemory(yourmemory, allnames)
    
#     def where_you_know_in_chat_history(self, chathistory: list[HumanMessage | AIMessage], allnames: set[str]) -> set[str]:
#         return self.from_chat_history(chathistory, allnames)
# ###############################################################################################################################################
#     def frommemory(self, yourmemory: str, allnames: set[str]) -> set[str]:
#         result: set[str] = set()
#         for name in allnames:
#             if name in yourmemory:
#                 result.add(name)
#         return result
    
#     def from_chat_history(self, chathistory: list[HumanMessage | AIMessage], allnames: set[str]) -> set[str]:
#         all_content_from_messages: str = ""
#         for chat in chathistory:
#             if isinstance(chat, HumanMessage):
#                 all_content_from_messages += str(chat.content)
#             elif isinstance(chat, AIMessage):
#                 all_content_from_messages += str(chat.content)

#         result: set[str] = set()
#         for name in allnames:
#             if name in all_content_from_messages:
#                 result.add(name)
#         return result
###############################################################################################################################################
    def add_known_stage_file(self, filesowner: str, allnames: set[str]) -> None:
        file_system = self.context.file_system
        for stagename in allnames:
            if filesowner == stagename:
                #logger.warning(f"where == stagename: {filesowner} == {stagename}") ## 自己就不要添加了，自己认识自己？
                continue
            file = KnownStageFile(stagename, filesowner, stagename)
            file_system.add_known_stage_file(file)
###############################################################################################################################################
    def add_known_npc_file(self, filesowner: str, allnames: set[str]) -> None:
        file_system = self.context.file_system
        for npcname in allnames:
            if filesowner == npcname:
                #logger.warning(f"who == npcname: {filesowner} == {npcname}") ## 自己就不要添加了，自己认识自己？
                continue
            file = KnownNPCFile(npcname, filesowner, npcname)
            file_system.add_known_npc_file(file)
###############################################################################################################################################