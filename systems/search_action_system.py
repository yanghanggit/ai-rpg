from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import (SearchActionComponent, 
                        NPCComponent, 
                        StageComponent)
from auxiliary.actor_action import ActorAction
from auxiliary.print_in_color import Color
from loguru import logger
from auxiliary.director_component import DirectorComponent
from auxiliary.director_event import NPCSearchFailedEvent
from typing import List
from auxiliary.file_def import PropFile

class SearchActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext):
        super().__init__(context)
        self.context = context
###################################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return { Matcher(SearchActionComponent): GroupEvent.ADDED }
###################################################################################################################
    def filter(self, entity: Entity) -> bool:
        return entity.has(SearchActionComponent)    
###################################################################################################################
    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  SearchPropsSystem  >>>>>>>>>>>>>>>>>")

        ## 开始行动
        for whosearchentity in entities:
            self.search(whosearchentity)
###################################################################################################################
    ## 重构的添加导演的类
    def add_event_to_director(self, entity: Entity, propname: str) -> None:
        if entity is None or not entity.has(NPCComponent):
            ##写死，只有NPC才能搜寻失败
            return
        ##添加导演事件
        stageentity = self.context.safe_get_stage_entity(entity)
        if stageentity is None or not stageentity.has(DirectorComponent):
            return
        #
        npccomp: NPCComponent = entity.get(NPCComponent)
        npcname: str = npccomp.name
        directorcomp: DirectorComponent = stageentity.get(DirectorComponent)
        searchfailedevent = NPCSearchFailedEvent(npcname, propname)
        directorcomp.addevent(searchfailedevent)
###################################################################################################################
    def search(self, whosearchentity: Entity) -> None:
        if not whosearchentity.has(NPCComponent):
            # 写死目前只有NPC能搜寻
            return
        
        stageentity = self.context.safe_get_stage_entity(whosearchentity)
        if stageentity is None:
            ## 没有场景的不能搜索
            return
        
        stagecomp: StageComponent = stageentity.get(StageComponent)
        # 在本场景搜索
        file_system = self.context.file_system
        # 场景有这些道具文件
        propfiles = file_system.get_prop_files(stagecomp.name)
        ###
        npccomp: NPCComponent = whosearchentity.get(NPCComponent)
        searchactioncomp: SearchActionComponent = whosearchentity.get(SearchActionComponent)
        action: ActorAction = searchactioncomp.action
        searchtargets: set[str] = set(action.values)
        ###
        for targetpropname in searchtargets:
            
            ## 不在同一个场景就不能被搜寻，这个场景不具备这个道具，就无法搜寻
            if not self.check_stage_has_the_prop(targetpropname, propfiles):
                logger.info(f"{Color.WARNING}{targetpropname}不在NPC, {npccomp.name}所在场景{stagecomp.name}，是不能搜寻的。{Color.ENDC}")
                continue
            
            # 交换文件，即交换道具文件即可
            self.stage_exchanges_prop_to_npc(stagecomp.name, npccomp.name, targetpropname)

            ## 事件记录的体系
            #self.context.legacy_add_content_to_director_script_by_entity(whosearchentity, unique_prop_taken_away(whosearchentity, targetpropname))
            self.add_event_to_director(whosearchentity, targetpropname)
            ## 打印一下
            logger.info(f"{Color.GREEN}{npccomp.name}找到了{targetpropname}。{Color.ENDC}")

###################################################################################################################
    def check_stage_has_the_prop(self, targetname: str, curstagepropfiles: List[PropFile]) -> bool:
        for propfile in curstagepropfiles:
            if propfile.name == targetname:
                return True
        return False
###################################################################################################################
    def stage_exchanges_prop_to_npc(self, stagename: str, npcname: str, propfilename: str) -> None:
        filesystem = self.context.file_system
        filesystem.exchange_prop_file(stagename, npcname, propfilename)
###################################################################################################################