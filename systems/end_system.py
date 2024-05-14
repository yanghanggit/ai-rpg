
from entitas import ExecuteProcessor, Matcher, InitializeProcessor #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.components import (StageComponent, 
                        NPCComponent,
                        WorldComponent)
import json
from typing import Dict
   
class EndSystem(InitializeProcessor, ExecuteProcessor):
############################################################################################################
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    def initialize(self) -> None:
        pass
############################################################################################################
    def execute(self) -> None:
        # 打印所有的世界信息
        self.showworld()
        # 打印一下所有的场景信息
        self.showstages()
        # 打印一下所有的agent信息
        self.make_agent_chat_history_dump()
        # 打印所有的道具归属
        self.make_prop_files_dump()
        # 打印所有的实体信息
        #self.print_all_entities()
############################################################################################################
    def showworld(self) -> None:
        worldentities = self.context.get_group(Matcher(WorldComponent)).entities
        for entity in worldentities:
            worldcomp: WorldComponent = entity.get(WorldComponent)
            logger.debug(f"/showworld: {worldcomp.name}")
############################################################################################################
    def showstages(self) -> None:
        infomap = self.information_about_all_stages_and_npcs()
        if len(infomap.keys()) > 0:
            logger.debug(f"/showstages: \n{infomap}")
        else:
            logger.debug("/showstages: No stages and npcs now")
############################################################################################################
    def make_agent_chat_history_dump(self) -> None:
        self.context.agent_connect_system.dump_all_agents_chat_history()
############################################################################################################
    def information_about_all_stages_and_npcs(self) -> dict[str, list[str]]:
        stagesentities = self.context.get_group(Matcher(StageComponent)).entities
        npcsentities = self.context.get_group(Matcher(NPCComponent)).entities
        map: dict[str, list[str]] = {}
        for entity in stagesentities:
            stagecomp: StageComponent = entity.get(StageComponent)
            ls = map.get(stagecomp.name, [])
            map[stagecomp.name] = ls

            for entity in npcsentities:
                npccomp: NPCComponent = entity.get(NPCComponent)
                if npccomp.current_stage == stagecomp.name:
                    ls.append(npccomp.name)
        return map
############################################################################################################
    def make_prop_files_dump(self) -> None:
        file_system = self.context.file_system
        propfiles = file_system.propfiles

        dumpdict: Dict[str, str] = {}
        for ownername, propfilelist in propfiles.items():
            liststr = ",".join([str(propfile) for propfile in propfilelist])
            dumpdict[ownername] = liststr

        logger.debug(f"{json.dumps(dumpdict, ensure_ascii = False)}")
############################################################################################################
    def print_all_entities(self) -> None:
        context = self.context
        allentities = context.entities
        logger.debug(f"{'=' * 100}")
        for entity in allentities:
            logger.debug(f"{entity}")
############################################################################################################