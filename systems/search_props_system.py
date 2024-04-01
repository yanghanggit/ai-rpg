from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import (SearchActionComponent, 
                        # UniquePropComponent, 
                        # PropComponent,
                        NPCComponent, 
                        StageComponent, 
                        DirectorComponent)
from auxiliary.actor_action import ActorAction
from auxiliary.prompt_maker import unique_prop_taken_away
from auxiliary.print_in_color import Color
#from typing import Optional
from loguru import logger
from director import Director, SearchFailedEvent
from typing import List
from auxiliary.file_system import PropFile

class SearchPropsSystem(ReactiveProcessor):

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
            self.handlesearch(whosearchentity)
    
        ## 一次行动结束
        for whosearchentity in entities:
            if whosearchentity.has(SearchActionComponent):
                whosearchentity.remove(SearchActionComponent)
        #return
        # unique_props_names: set[str] = self.context.get_all_unique_props_names()

        # for npc_entity in entities:
        #     npc_search_action: Optional[ActorAction] = self.context.get_search_action_by_entity(npc_entity)
        #     if npc_search_action is None:
        #         logger.warning(f"{Color.WARNING}{npc_entity.get(NPCComponent).name}没有找到搜索动作。{Color.ENDC}")
        #         continue
        #     npc_search_targes: set[str] = set(npc_search_action.values)
        #     unique_prop_match_success: set[str] = unique_props_names & npc_search_targes

        #     if len(unique_prop_match_success) == 0:
        #         logger.warning(f"{Color.WARNING}{npc_entity.get(NPCComponent).name}没有找到符合的道具。{Color.ENDC}")
        #         continue
        #     else:
        #         for unique_prop_name in unique_prop_match_success:
        #             unique_prop_entity: Optional[Entity] = self.context.get_unique_prop_entity_by_name(unique_prop_name)
        #             if unique_prop_entity is None:
        #                 logger.info(f"{Color.WARNING}没有找到{unique_prop_name}。{Color.ENDC}")
        #                 continue
        #             if not unique_prop_entity.has(DestroyComponent) and npc_entity.has(NPCComponent):
                        
        #                 if npc_entity.has(SearchActionComponent):
        #                     npc_entity.remove(SearchActionComponent)

        #                 self.context.put_unique_prop_into_backpack(npc_entity, unique_prop_name)

        #                 self.context.add_content_to_director_script_by_entity(npc_entity, unique_prop_taken_away(npc_entity, unique_prop_name))
        #                 self.add_event_to_director(npc_entity, unique_prop_name)

        #                 unique_prop_entity.add(DestroyComponent, f"{unique_prop_name}被获取.")

        #                 logger.info(f"{Color.GREEN}{npc_entity.get(NPCComponent).name}找到了{unique_prop_name}。{Color.ENDC}")

###################################################################################################################
    ## 重构的添加导演的类
    def add_event_to_director(self, entity: Entity, propname: str) -> None:
        if entity is None or not entity.has(NPCComponent):
            ##写死，只有NPC才能搜寻失败
            return
        ##添加导演事件
        stageentity = self.context.get_stage_entity_by_uncertain_entity(entity)
        if stageentity is None or not stageentity.has(DirectorComponent):
            return
        #
        npccomp: NPCComponent = entity.get(NPCComponent)
        npcname: str = npccomp.name
        #
        directorcomp: DirectorComponent = stageentity.get(DirectorComponent)
        director: Director = directorcomp.director
        #
        searchfailedevent = SearchFailedEvent(npcname, propname)
        director.addevent(searchfailedevent)
###################################################################################################################
    def handlesearch(self, whosearchentity: Entity) -> None:
        if not whosearchentity.has(NPCComponent):
            # 写死目前只有NPC能搜寻
            return
        
        stageentity = self.context.get_stage_entity_by_uncertain_entity(whosearchentity)
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
            self.context.legacy_add_content_to_director_script_by_entity(whosearchentity, unique_prop_taken_away(whosearchentity, targetpropname))
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
        filesystem.exchangefile(stagename, npcname, propfilename)
###################################################################################################################