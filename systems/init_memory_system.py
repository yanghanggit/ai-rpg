from entitas import Entity, Matcher, InitializeProcessor # type: ignore
from auxiliary.components import WorldComponent, StageComponent, NPCComponent
from auxiliary.cn_builtin_prompt import (init_memory_system_prompt)
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from systems.update_archive_helper import UpdareArchiveHelper


###############################################################################################################################################
class InitMemorySystem(InitializeProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
###############################################################################################################################################
    def initialize(self) -> None:
        self.initmemory()
###############################################################################################################################################
    def initmemory(self) -> None:
        #
        context = self.context
        helper = UpdareArchiveHelper(context)
        helper.prepare()
        #分段处理
        self.handleworld(helper)
        self.handlestages(helper)
        self.handlenpcs(helper)
        ##最后并发执行
        context.agent_connect_system.run_async_requet_tasks()
###############################################################################################################################################
    def handleworld(self, helper: UpdareArchiveHelper) -> None:
        context = self.context
        memory_system = context.memory_system
        agent_connect_system = context.agent_connect_system
        worlds: set[Entity] = context.get_group(Matcher(WorldComponent)).entities
        for world in worlds:
            worldcomp: WorldComponent = world.get(WorldComponent)
            worldmemory = memory_system.getmemory(worldcomp.name)
            if worldmemory == "":
                logger.error(f"worldmemory is empty: {worldcomp.name}")
                continue
            readarchprompt = init_memory_system_prompt(worldmemory)
            agent_connect_system.add_async_requet_task(worldcomp.name, readarchprompt)
###############################################################################################################################################
    def handlestages(self, helper: UpdareArchiveHelper) -> None:
        context = self.context
        memory_system = context.memory_system
        agent_connect_system = context.agent_connect_system
        stages: set[Entity] = context.get_group(Matcher(StageComponent)).entities
        for stage in stages:
            stagecomp: StageComponent = stage.get(StageComponent)
            stagememory = memory_system.getmemory(stagecomp.name)
            if stagememory == "":
                logger.error(f"stagememory is empty: {stagecomp.name}")
                continue
            readarchprompt = init_memory_system_prompt(stagememory)
            agent_connect_system.add_async_requet_task(stagecomp.name, readarchprompt)
###############################################################################################################################################
    def handlenpcs(self, helper: UpdareArchiveHelper) -> None:
        #
        context = self.context
        memory_system = context.memory_system
        agent_connect_system = context.agent_connect_system
        npcs: set[Entity] = context.get_group(Matcher(all_of=[NPCComponent])).entities
        for npcentity in npcs:
            npccomp: NPCComponent = npcentity.get(NPCComponent)
            npcname: str = npccomp.name
            str_init_memory = memory_system.getmemory(npcname)
            if str_init_memory == "":
                logger.error(f"npcmemory is empty: {npcname}")
                continue
            prompt = init_memory_system_prompt(str_init_memory)
            agent_connect_system.add_async_requet_task(npcname, prompt)
###############################################################################################################################################
