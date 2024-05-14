from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from auxiliary.components import StageComponent, NPCComponent, PlayerComponent
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.director_component import StageDirectorComponent
from auxiliary.player_proxy import add_player_client_message


class DirectorSystem(ExecuteProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        self.context = context
###################################################################################################################
    def execute(self) -> None:
        self.handle()
        self.directorclear()
###################################################################################################################
    def handle(self) -> None:
        entities = self.context.get_group(Matcher(all_of=[StageComponent, StageDirectorComponent])).entities
        for entity in entities:
            self.handlestage(entity)
            self.handle_npcs_in_this_stage(entity)
###################################################################################################################   
    def directorclear(self) -> None:
        entities = self.context.get_group(Matcher(all_of=[StageComponent, StageDirectorComponent])).entities
        for entity in entities:
            directorcomp: StageDirectorComponent = entity.get(StageDirectorComponent)
            directorcomp.clear()
###################################################################################################################
    def handlestage(self, entitystage: Entity) -> None:
        assert entitystage.has(StageComponent)
        stagecomp: StageComponent = entitystage.get(StageComponent)
        directorcomp: StageDirectorComponent = entitystage.get(StageDirectorComponent)
        events2stage = directorcomp.tostage(stagecomp.name, self.context)  
        for event in events2stage:
            #logger.debug(f"{stagecomp.name} => {event}")
            self.context.safe_add_human_message_to_entity(entitystage, event)       
###################################################################################################################
    def handle_npcs_in_this_stage(self, entitystage: Entity) -> None:
        assert entitystage.has(StageComponent)
        stagecomp: StageComponent = entitystage.get(StageComponent)
        allnpcsinthestage = self.context.npcs_in_this_stage(stagecomp.name)
        directorcomp: StageDirectorComponent = entitystage.get(StageDirectorComponent)
        for npcentity in allnpcsinthestage:
            npccomp: NPCComponent = npcentity.get(NPCComponent)

            
            #
            events2npc = directorcomp.tonpc(npccomp.name, self.context)     
            #
            if len(events2npc) > 0:
                self.context.safe_add_human_message_to_entity(npcentity, f"""# 如下是{stagecomp.name}场景内发生的事件。""")

            #
            for event in events2npc:
                logger.debug(f"{npccomp.name} => {event}")
                self.context.safe_add_human_message_to_entity(npcentity, event)

            #
            if len(events2npc) > 0:
                self.context.safe_add_human_message_to_entity(npcentity, f"""# 以上是{stagecomp.name}场景内近期发生的事件。请注意。""")

            #
            if npcentity.has(PlayerComponent):
                events2player = directorcomp.player_client_message(npccomp.name, self.context)
                for event in events2player:
                    add_player_client_message(npcentity, event)
###################################################################################################################
    