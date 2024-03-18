from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity, Group
from extended_context import ExtendedContext
from components import SearchActionComponent, UniquePropComponent, NPCComponent, BagComponent, StageComponent
from actor_action import ActorAction
from actor_agent import ActorAgent

class SearchPropsSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext):
        super().__init__(context)
        self.context = context

    def get_trigger(self):
        return { Matcher(SearchActionComponent): GroupEvent.ADDED }
    
    def filter(self, entity: Entity):
        return entity.has(SearchActionComponent)
    
    def react(self, entities: list[Entity]):
        print("<<<<<<<<<<<<<  SearchPropsSystem  >>>>>>>>>>>>>>>>>")
        for npc_entity in entities:
            npc_search_action_component: SearchActionComponent = npc_entity.get(SearchActionComponent)
            npc_search_action: ActorAction = npc_search_action_component.action    

            unique_props_group: Group = self.context.get_group(Matcher(UniquePropComponent))
            unique_props_entities: set[Entity] = unique_props_group.entities

            for npc_search_target in npc_search_action.values:
                for unique_prop_entity in unique_props_entities:
                    unique_props_comp: UniquePropComponent = unique_prop_entity.get(UniquePropComponent)
                    # 判断道具无主 and 道具是NPC要找的道具
                    if unique_props_comp.owner == "None" and unique_props_comp.name == npc_search_target:
                        if npc_entity.has(NPCComponent):
                            npc_comp: NPCComponent = npc_entity.get(NPCComponent)
                            npc_agent: ActorAgent = npc_comp.agent
                            unique_prop_entity.replace(UniquePropComponent, npc_search_target, npc_agent.name)
                            npc_bag_comp: BagComponent = npc_entity.get(BagComponent)
                            npc_bag_content: set = npc_bag_comp.name_items
                            npc_bag_content.add(npc_search_target)
                            npc_stage: StageComponent = self.context.get_stagecomponent_by_uncertain_entity(npc_entity)
                            # 导演剧本加入成功找到道具的消息
                            npc_stage.directorscripts.append(f"{npc_agent.name}找到了{npc_search_target},{npc_search_target}只存在唯一一份，其他人无法再搜到了。")
                            print(f"{npc_agent.name}成功找到了{npc_search_target}。")
                        else:
                            print(f"{npc_entity}有SearchActionComponent，但不是NPC，该情况不合理，请检查配置。")
                    else:
                        print(f"道具Owner：{unique_props_comp.owner}，道具Name：{unique_props_comp.name}，NPC要找的道具：{npc_search_target}，不符合条件。")
                            



