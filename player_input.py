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
from player_proxy import PlayerProxy

class PlayerInput:

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy) -> None:
        self.name: str = name
        self.game: RPGGame = game
        self.playerproxy: PlayerProxy = playerproxy

class PlayerCommandBeWho(PlayerInput):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, targetname: str) -> None:
        super().__init__(name, game, playerproxy)
        self.targetname = targetname

    def execute(self) -> None:
        context = self.game.extendedcontext
        name = self.targetname
        playname = self.playerproxy.name

        playerentity = context.getplayer()
        if playerentity is not None:
            playercomp = playerentity.get(PlayerComponent)
            logger.debug(f"debug_be_who current player is : {playercomp.name}")
            playerentity.remove(PlayerComponent)

        entity = context.getnpc(name)
        if entity is not None:
            npccomp = entity.get(NPCComponent)
            logger.debug(f"debug_be_who => : {npccomp.name} is {playname}")
            entity.add(PlayerComponent, playname)
            return
        
        entity = context.getstage(name)
        if entity is not None:
            stagecomp = entity.get(StageComponent)
            logger.debug(f"debug_be_who => : {stagecomp.name} is {playname}")
            entity.add(PlayerComponent, playname)
            return
        


