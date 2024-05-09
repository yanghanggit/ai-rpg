from entitas import Entity, Matcher, ReactiveProcessor # type: ignore
from typing import Optional
from loguru import logger
from auxiliary.actor_action import ActorAction
from auxiliary.components import UseItemActionComponent
from auxiliary.dialogue_rule import parse_target_and_message
from auxiliary.extended_context import ExtendedContext
from auxiliary.file_def import UseItemFile
from auxiliary.director_component import notify_stage_director
from entitas.group import GroupEvent
from auxiliary.director_event import NPCUseItemEvent

class UseItemActionSystem(ReactiveProcessor):
    def __init__(self, context: ExtendedContext):
        super().__init__(context)
        self.context = context

    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return { Matcher(UseItemActionComponent): GroupEvent.ADDED }
    
    def filter(self, entity: Entity) -> bool:
        return entity.has(UseItemActionComponent)
    
    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  UseItemActionSystem  >>>>>>>>>>>>>>>>>")
        for entity in entities:
            self.useitem(entity)

    def useitem(self, entity: Entity) -> None:
        use_item_comp: UseItemActionComponent = entity.get(UseItemActionComponent)
        use_item_action: ActorAction = use_item_comp.action
        for value in use_item_action.values:
            parse = parse_target_and_message(value)
            target_name: Optional[str] = parse[0]
            assert target_name is not None
            item_name: Optional[str] = parse[1]
            assert item_name is not None
            if self._use_item_(entity, target_name, item_name): 
                logger.debug(f"UseItemActionSystem: {target_name} is using {item_name}")
                user_name = self.context.safe_get_entity_name(entity)
                notify_stage_director(self.context, entity, NPCUseItemEvent(user_name, target_name, item_name))

    def _use_item_(self, entity: Entity, target_name: str, item_name: str) -> bool:
        filesystem = self.context.file_system
        user_name = self.context.safe_get_entity_name(entity)

        if not filesystem.has_prop_file(user_name, item_name):
            logger.error(f"{user_name}身上没有{item_name}，请检查。")
            return False
        
        use_item_result = self.check_target_with_item(target_name, item_name)
        if use_item_result is None:
            logger.warning(f"{target_name}与{item_name}之间的关系未定义，请检查。")
            return False
        
        if not filesystem.has_item_to_target_file(user_name, use_item_result):
            createitemfile = UseItemFile(user_name, target_name, use_item_result)
            filesystem.add_use_item_to_target_file(createitemfile)
        else:
            logger.error(f"{user_name}已经达成{use_item_result},请检查结果是否正确。")
            return False

        return True
        
    
    def check_target_with_item(self, target_name: str, item_name: str) -> Optional[str]:
        # 暂时在这里对于道具和作用对象的产物进行定义
        target_with_item = { "禁言者之棺": ["腐朽的匕首"] }
        target_prompts = { "禁言者之棺": "的棺材盖" }
        item_prompts = { "腐朽的匕首": "撬开" }

        for target, items in target_with_item.items():
            if target == target_name:
                for item in items:
                    if item == item_name:
                        return item_prompts[item] + target_prompts[target]
        return None

        