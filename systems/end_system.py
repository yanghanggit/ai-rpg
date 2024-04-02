
from entitas import ExecuteProcessor, Matcher #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.components import (StageComponent, 
                        NPCComponent)
   
class EndSystem(ExecuteProcessor):
############################################################################################################
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  EndSystem  >>>>>>>>>>>>>>>>>")

        # 打印一下所有的场景信息
        infomap = self.information_about_all_stages_and_npcs()
        logger.debug(f"/showstages: \n{infomap}")

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