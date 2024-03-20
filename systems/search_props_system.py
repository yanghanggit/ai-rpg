from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity, Group #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import (SearchActionComponent, 
                        UniquePropComponent, 
                        NPCComponent, 
                        StageComponent, 
                        DestroyComponent)
from auxiliary.actor_action import ActorAction
from auxiliary.prompt_maker import unique_prop_taken_away
from auxiliary.print_in_color import Color
from typing import Optional
from loguru import logger

class SearchPropsSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext):
        super().__init__(context)
        self.context = context

    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return { Matcher(SearchActionComponent): GroupEvent.ADDED }
    
    def filter(self, entity: Entity) -> bool:
        return entity.has(SearchActionComponent)
    
    
    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  SearchPropsSystem  >>>>>>>>>>>>>>>>>")
        unique_props_names: set[str] = self.context.get_all_unique_props_names()

        for npc_entity in entities:
            npc_search_action: Optional[ActorAction] = self.context.get_search_action_by_entity(npc_entity)
            if npc_search_action is None:
                logger.warning(f"{Color.WARNING}{npc_entity.get(NPCComponent).name}没有找到搜索动作。{Color.ENDC}")
                continue
            npc_search_targes: set[str] = set(npc_search_action.values)
            unique_prop_match_success: set[str] = unique_props_names & npc_search_targes

            if len(unique_prop_match_success) == 0:
                logger.warning(f"{Color.WARNING}{npc_entity.get(NPCComponent).name}没有找到符合的道具。{Color.ENDC}")
                continue
            else:
                for unique_prop_name in unique_prop_match_success:
                    unique_prop_entity: Optional[Entity] = self.context.get_unique_prop_entity_by_name(unique_prop_name)
                    if unique_prop_entity is None:
                        logger.info(f"{Color.WARNING}没有找到{unique_prop_name}。{Color.ENDC}")
                        continue
                    if not unique_prop_entity.has(DestroyComponent) and npc_entity.has(NPCComponent):
                        
                        if npc_entity.has(SearchActionComponent):
                            npc_entity.remove(SearchActionComponent)

                        self.context.put_unique_prop_into_backpack(npc_entity, unique_prop_name)

                        self.context.add_content_to_director_script_by_entity(npc_entity, unique_prop_taken_away(npc_entity, unique_prop_name))

                        unique_prop_entity.add(DestroyComponent, f"{unique_prop_name}被获取.")

                        logger.info(f"{Color.GREEN}{npc_entity.get(NPCComponent).name}找到了{unique_prop_name}。{Color.ENDC}")
