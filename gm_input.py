from rpg_game import RPGGame
import os
from typing import List, Optional, Union
from entitas import Processors #type: ignore
from loguru import logger
import datetime
from auxiliary.components import (
    BroadcastActionComponent, 
    SpeakActionComponent, 
    WorldComponent,
    StageComponent, 
    NPCComponent, 
    FightActionComponent, 
    PlayerComponent, 
    SimpleRPGRoleComponent, 
    LeaveForActionComponent, 
    HumanInterferenceComponent,
    UniquePropComponent,
    BackpackComponent,
    StageEntryConditionComponent,
    StageExitConditionComponent,
    WhisperActionComponent,
    SearchActionComponent)
from auxiliary.actor_action import ActorAction
from auxiliary.actor_agent import ActorAgent
from auxiliary.extended_context import ExtendedContext
from auxiliary.dialogue_rule import parse_command, parse_target_and_message_by_symbol
from auxiliary.world_data_builder import WorldDataBuilder, AdminNpcBuilder, StageBuilder, PlayerNpcBuilder, NpcBuilder
from entitas.entity import Entity
from systems.init_system import InitSystem
from systems.stage_plan_system import StagePlanSystem
from systems.npc_plan_system import NPCPlanSystem
from systems.speak_action_system import SpeakActionSystem
from systems.fight_action_system import FightActionSystem
from systems.leave_for_action_system import LeaveForActionSystem
from systems.director_system import DirectorSystem
from systems.dead_action_system import DeadActionSystem
from systems.destroy_system import DestroySystem
from systems.tag_action_system import TagActionSystem
from systems.data_save_system import DataSaveSystem
from systems.broadcast_action_system import BroadcastActionSystem  
from systems.whisper_action_system import WhisperActionSystem 
from systems.search_props_system import SearchPropsSystem
from systems.mind_voice_action_system import MindVoiceActionSystem


class GMInput:

    def __init__(self, name: str, game: RPGGame) -> None:
        self.name: str = name
        self.game: RPGGame = game


class GMCommandPush(GMInput):

    def __init__(self, name: str, game: RPGGame, targetname: str, content: str) -> None:
        super().__init__(name, game)
        self.targetname = targetname
        self.content = content

    def execute(self) -> Union[None, NPCComponent, StageComponent, WorldComponent]:
        context = self.game.extendedcontext
        name = self.targetname
        content = self.content
        
        npc_entity: Optional[Entity] = context.getnpc(name)
        if npc_entity is not None:
            npc_comp: NPCComponent = npc_entity.get(NPCComponent)
            npc_request: Optional[str] = npc_comp.agent.request(content)
            if npc_request is not None:
                npc_comp.agent.chat_history.pop()
            return npc_comp
        
        stage_entity: Optional[Entity] = context.getstage(name)
        if stage_entity is not None:
            stage_comp: StageComponent = stage_entity.get(StageComponent)
            stage_request: Optional[str] = stage_comp.agent.request(content)
            if stage_request is not None:
                stage_comp.agent.chat_history.pop()
            return stage_comp
        
        world_entity: Optional[Entity] = context.getworld()
        if world_entity is not None:
            world_comp: WorldComponent = world_entity.get(WorldComponent)
            request: Optional[str] = world_comp.agent.request(content)
            if request is not None:
                world_comp.agent.chat_history.pop()
            return world_comp

        return None        


class GMCommandAsk(GMInput):

    def __init__(self, name: str, game: RPGGame, targetname: str, content: str) -> None:
        super().__init__(name, game)
        self.targetname = targetname
        self.content = content

    def execute(self) -> None:
        gmcommandpush = GMCommandPush(self.name, self.game, self.targetname, self.content)
        pushed_comp = gmcommandpush.execute()
        if pushed_comp is None:
            logger.warning(f"debug_ask: {self.targetname} not found.")
            return
        pushed_agent: ActorAgent = pushed_comp.agent
        pushed_agent.chat_history.pop()
   
    


