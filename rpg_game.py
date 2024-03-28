from typing import List, Optional
from entitas import Processors #type: ignore
from loguru import logger
from auxiliary.components import (
    WorldComponent,
    StageComponent, 
    NPCComponent, 
    PlayerComponent, 
    SimpleRPGRoleComponent, 
    UniquePropComponent,
    BackpackComponent,
    StageEntryConditionComponent,
    StageExitConditionComponent,
    DirectorComponent)
from auxiliary.actor_agent import ActorAgent
from auxiliary.extended_context import ExtendedContext
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
from director import Director

class RPGGame:

    def __init__(self, name: str) -> None:
        self.name = name
        self.extendedcontext: ExtendedContext = ExtendedContext()
        self.processors: Processors = Processors()
        self.started: bool = False
        self.inited: bool = False
        ### 做一些初始化
        self.createprocessors()
###############################################################################################################################################
    def createprocessors(self) -> None:
        processors = self.processors
        context = self.extendedcontext

        #初始化系统########################
        processors.add(InitSystem(context))
        #规划逻辑########################
        processors.add(StagePlanSystem(context))
        processors.add(NPCPlanSystem(context))
        #行动逻辑########################
        processors.add(TagActionSystem(context))
        processors.add(MindVoiceActionSystem(context))
        processors.add(WhisperActionSystem(context))
        processors.add(BroadcastActionSystem(context))
        processors.add(SpeakActionSystem(context))
        #死亡必须是战斗之后，因为如果死了就不能离开###############
        processors.add(FightActionSystem(context))
        processors.add(DeadActionSystem(context)) 
        #########################################
        # 处理搜寻道具行为
        processors.add(SearchPropsSystem(context))
        # 处理离开并去往的行为
        processors.add(LeaveForActionSystem(context))
        #行动结束后导演
        processors.add(DirectorSystem(context))
        #########################################
        ###必须最后
        processors.add(DestroySystem(context))
        processors.add(DataSaveSystem(context))
###############################################################################################################################################
    def createworld(self, world_data_builder: WorldDataBuilder) -> None:
        if world_data_builder is None or world_data_builder.data is None:
            logger.error("没有WorldBuilder数据，请检查World.json配置。")
            return
        adminnpcs = self.create_admin_npc_entities(world_data_builder.admin_npc_builder)
        playernpcs = self.create_player_npc_entities(world_data_builder.player_npc_builder)
        npcs = self.create_npc_entities(world_data_builder.npc_buidler)
        stages = self.create_stage_entities(world_data_builder.stage_builder)
###############################################################################################################################################
    def execute(self) -> None:
        #顺序不要动！！！！！！！！！
        if not self.inited:
            self.inited = True
            self.processors.activate_reactive_processors()
            self.processors.initialize()
        
        self.processors.execute()
        self.processors.cleanup()
        self.started = True
###############################################################################################################################################
    def exit(self) -> None:
        self.processors.clear_reactive_processors()
        self.processors.tear_down()
        logger.info(f"{self.name}, game over")
###############################################################################################################################################
    def create_admin_npc_entities(self, admin_npc_builder: AdminNpcBuilder) -> List[Entity]:
        context = self.extendedcontext
        res: List[Entity] = []
        if context is None or admin_npc_builder.data is None:
            logger.error("没有AdminNpcBuilder数据，请检查World.json配置。")
            return res
        
        for admin_npc in admin_npc_builder.npcs:
            admin_npc_entity = context.create_entity()
            res.append(admin_npc_entity)

            admin_npc_agent = ActorAgent(admin_npc.name, admin_npc.url, admin_npc.memory)
            admin_npc_entity.add(WorldComponent, admin_npc_agent.name, admin_npc_agent)
            logger.debug(f"创建Admin npc：{admin_npc.name}")
            
        return res
###############################################################################################################################################
    def create_player_npc_entities(self, player_npc_builder: PlayerNpcBuilder) -> List[Entity]:
        context = self.extendedcontext
        res: List[Entity] = []

        if player_npc_builder.data is None:
            logger.error("没有PlayerNpcBuilder数据，请检查World.json配置。")
            return res
        
        for player_npc in player_npc_builder.npcs:
            player_npc_entity = context.create_entity()
            res.append(player_npc_entity)

            player_npc_agent = ActorAgent(player_npc.name, player_npc.url, player_npc.memory)
            player_npc_entity.add(PlayerComponent, player_npc.name)
            player_npc_entity.add(SimpleRPGRoleComponent, player_npc.name, 10000, 10000, 10, "")
            player_npc_entity.add(NPCComponent, player_npc.name, player_npc_agent, "")
            player_npc_entity.add(BackpackComponent, player_npc.name)
            context.file_system.init_backpack_component(player_npc_entity.get(BackpackComponent))
            logger.debug(f"创建Player npc：{player_npc.name}")
            if len(player_npc.props) > 0:
                for prop in player_npc.props:
                    context.file_system.add_content_into_backpack(player_npc_entity.get(BackpackComponent), prop.name)
                    logger.debug(f"{player_npc.name}的背包中有：{prop.name}")

        return res
###############################################################################################################################################
    def create_npc_entities(self, npc_builder: NpcBuilder) -> List[Entity]:
        context = self.extendedcontext
        res: List[Entity] = []

        if npc_builder.data is None:
            logger.error("没有NpcBuilder数据，请检查World.json配置。")
            return res
        
        for npc_in_builder in npc_builder.npcs:
            npc_entity_in_builder = context.create_entity()
            res.append(npc_entity_in_builder)

            npc_agent = ActorAgent(npc_in_builder.name, npc_in_builder.url, npc_in_builder.memory)
            npc_entity_in_builder.add(NPCComponent, npc_agent.name, npc_agent, "")
            npc_entity_in_builder.add(SimpleRPGRoleComponent, npc_agent.name, 100, 100, 10, "")
            npc_entity_in_builder.add(BackpackComponent, npc_agent.name)
            context.file_system.init_backpack_component(npc_entity_in_builder.get(BackpackComponent))
            logger.debug(f"创建npc：{npc_agent.name}")
            if len(npc_in_builder.props) > 0:
                for prop in npc_in_builder.props:
                    context.file_system.add_content_into_backpack(npc_entity_in_builder.get(BackpackComponent), prop.name)
                    logger.debug(f"{npc_agent.name}的背包中有：{prop.name}")
        
        return res
###############################################################################################################################################
    def create_stage_entities(self, stage_builder: StageBuilder) -> List[Entity]:
        context = self.extendedcontext
        res: List[Entity] = []

        if stage_builder.data is None:
            logger.error("没有StageBuilder数据，请检查World.json配置。")
            return res
        
        # 创建stage相关配置
        for stage in stage_builder.stages:
            stage_agent = ActorAgent(stage.name, stage.url, stage.memory)
            stage_entity = context.create_entity()
            stage_entity.add(StageComponent, stage_agent.name, stage_agent, [])
            stage_entity.add(DirectorComponent, stage_agent.name, Director(stage_agent.name)) ###
            stage_entity.add(SimpleRPGRoleComponent, stage_agent.name, 10000, 10000, 1, "")
            logger.debug(f"创建Stage：{stage.name}")

            ## 重新设置npc和stage的关系
            for npc in stage.npcs:
                if isinstance(npc, dict):
                    npc_name = npc.get("name", "")
                    npc_url = npc.get("url", "")
                    npc_memory = npc.get("memory", "")
                    npc_agent = ActorAgent(npc_name, npc_url, npc_memory)
                    npc_entity_in_builder: Optional[Entity] = context.getnpc(npc_name)
                    if npc_entity_in_builder is None:
                        continue
                    if npc_entity_in_builder.has(NPCComponent):
                        npc_entity_in_builder.replace(NPCComponent, npc_name, npc_agent, stage_agent.name)
                        logger.debug(f"重新设置npc：{npc_name}的stage为：{stage.name}")

            # 创建道具
            for unique_prop in stage.props:
                prop_entity = context.create_entity()
                if isinstance(unique_prop, dict):
                    prop_entity.add(UniquePropComponent, unique_prop.get("name"))
                    logger.debug(f'创建道具：{unique_prop.get("name")}')
                else:
                    logger.error(f"道具配置错误：{unique_prop}")

            ## 创建入口条件和出口条件
            enter_condition_set = set()
            for enter_condition in stage.entry_conditions:
                enter_condition_set.add(enter_condition.name)
            if len(enter_condition_set) > 0:
                stage_entity.add(StageEntryConditionComponent, enter_condition_set)
                logger.debug(f"{stage_agent.name}的入口条件为：{enter_condition_set}")

            exit_condition_set = set()
            for exit_condition in stage.exit_conditions:
                exit_condition_set.add(exit_condition.name)
            if len(exit_condition_set) > 0:
                stage_entity.add(StageExitConditionComponent, set(exit_condition_set))
                logger.debug(f"{stage_agent.name}的出口条件为：{exit_condition_set}")

        return res
###############################################################################################################################################

