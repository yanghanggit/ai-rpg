from entitas import Matcher, Entity  # type: ignore
from typing import List, Optional, Set
from overrides import override
from loguru import logger
from components.components import (
    WorldSystemComponent,
    StageComponent,
    ActorComponent,
    PlayerComponent,
    AttributesComponent,
    FinalAppearanceComponent,
    BaseFormComponent,
    GUIDComponent,
    WeaponComponent,
    ClothesComponent,
    StageGraphComponent,
    KickOffContentComponent,
    RoundEventsRecordComponent,
    KickOffFlagComponent,
    StageSpawnerComponent,
    StageEnvironmentComponent,
    StageStaticFlagComponent,
)
from game.rpg_game_context import RPGGameContext
from game.rpg_game_resource import RPGGameResource
from extended_systems.prop_file import PropFile
from game.base_game import BaseGame
import rpg_game_systems.file_system_utils
from game.rpg_game_processors import RPGGameProcessors
from models.entity_models import (
    ActorInstanceModel,
    StageInstanceModel,
    ActorModel,
    StageModel,
    WorldSystemModel,
    WorldSystemInstanceModel,
)
from models.event_models import BaseEvent
from models.file_models import PropFileModel
from models.entity_models import Attributes
from player.player_proxy import PlayerProxy
import rpg_game_systems.prompt_utils
from format_string.complex_actor_name import ComplexActorName


class RPGGame(BaseGame):

    def __init__(self, name: str, context: RPGGameContext) -> None:
        # 必须实现父
        super().__init__(name)

        ## 尽量不要再加东西了，Game就只管上下文，创建世界的数据，和Processors。其中上下文可以做运行中的全局数据管理者
        self._entitas_context: RPGGameContext = context
        self._entitas_context._game = self

        self._game_resource: Optional[RPGGameResource] = None
        self._processors: RPGGameProcessors = RPGGameProcessors.create(self, context)
        self._players: List[PlayerProxy] = []
        self._runtime_round: int = 0

    ###############################################################################################################################################
    @property
    def context(self) -> RPGGameContext:
        return self._entitas_context

    ###############################################################################################################################################
    @property
    def current_round(self) -> int:
        return self._runtime_round

    ###############################################################################################################################################
    @property
    def players(self) -> List[PlayerProxy]:
        return self._players

    ###############################################################################################################################################
    @property
    def epoch_script(self) -> str:
        if self._game_resource is None:
            return ""
        return self._game_resource.epoch_script

    ###############################################################################################################################################
    def build(self, game_resource: RPGGameResource) -> "RPGGame":

        # 混沌系统，准备测试
        self.context.chaos_engineering_system.initialize(self)
        self.context.chaos_engineering_system.on_pre_create_game()

        ## 第1步，设置根路径
        self._game_resource = game_resource
        ##
        self.context.agent_system.set_runtime_dir(game_resource._runtime_dir)
        self.context.file_system.set_runtime_dir(game_resource._runtime_dir)

        ## 第2步 创建管理员类型的角色，全局的AI
        self._create_world_system_entities(game_resource)

        ## 第3步，创建actor，player是特殊的actor
        player_entities = self._create_player_entities(
            game_resource, game_resource.player_instances
        )
        actor_entities = self._create_actor_entities(
            game_resource, game_resource.actor_instances
        )

        ## 第4步，创建stage
        self._create_stage_entities(game_resource)

        ## 第5步，最后处理因为需要上一阶段的注册流程
        self._initialize_actor_stage_links(set(player_entities + actor_entities))

        ## 第6步，如果是载入的文件，就需要直接修改一些值
        if game_resource.is_load:
            self._load_game(self.context, game_resource)

        ## 最后！混沌系统，准备测试
        self.context.chaos_engineering_system.on_post_create_game()

        return self

    ###############################################################################################################################################
    @override
    def execute(self) -> None:

        # 顺序不要动
        current_processors = self._processors
        if not current_processors._initialized:
            current_processors._initialized = True
            current_processors.activate_reactive_processors()
            current_processors.initialize()

        current_processors.execute()
        current_processors.cleanup()

    ###############################################################################################################################################
    @override
    async def a_execute(self) -> None:

        # 顺序不要动
        current_processors = self._processors
        if not current_processors._initialized:
            current_processors._initialized = True
            current_processors.activate_reactive_processors()
            current_processors.initialize()

        await current_processors.a_execute()
        current_processors.cleanup()

    ###############################################################################################################################################
    @override
    def exit(self) -> None:

        all = [self._processors]
        for processor in all:
            processor.tear_down()
            processor.clear_reactive_processors()

        logger.info(f"{self._name}, game over!!!!!!!!!!!!!!!!!!!!")

    ###############################################################################################################################################
    def _create_world_system_entities(
        self, game_resource: RPGGameResource
    ) -> List[Entity]:

        assert game_resource is not None
        assert game_resource.data_base is not None

        ret: List[Entity] = []

        for world_system_instance in game_resource.world_system_instances:

            world_system_model = game_resource.data_base.get_world_system(
                world_system_instance.name
            )
            assert world_system_model is not None

            world_system_entity = self._create_world_system_entity(
                world_system_instance, world_system_model, self.context
            )
            assert world_system_entity is not None

            ret.append(world_system_entity)

        return ret

    ###############################################################################################################################################
    def _create_world_system_entity(
        self,
        world_system_instance: WorldSystemInstanceModel,
        world_system_model: WorldSystemModel,
        context: RPGGameContext,
    ) -> Entity:

        # 创建实体
        world_system_entity = context.create_entity()
        assert world_system_entity is not None

        # 必要组件
        world_system_entity.add(
            GUIDComponent, world_system_model.name, world_system_instance.guid
        )
        world_system_entity.add(WorldSystemComponent, world_system_model.name)
        world_system_entity.add(KickOffContentComponent, world_system_model.name, "")
        world_system_entity.add(RoundEventsRecordComponent, world_system_model.name, [])

        # 添加扩展子系统的功能: Agent
        context.agent_system.register_agent(
            world_system_model.name, world_system_model.url
        )

        # 添加扩展子系统的功能: CodeName
        code_name_component_class = (
            context.query_component_system.register_query_component_class(
                instance_name=world_system_model.name,
                data_base_code_name=world_system_model.codename,
                guid=world_system_instance.guid,
            )
        )
        assert code_name_component_class is not None
        world_system_entity.add(code_name_component_class, world_system_instance.name)

        return world_system_entity

    ###############################################################################################################################################
    def _create_player_entities(
        self, game_resource: RPGGameResource, actors_instances: List[ActorInstanceModel]
    ) -> List[Entity]:

        assert game_resource is not None

        # 创建player 本质就是创建Actor
        actor_entities = self._create_actor_entities(game_resource, actors_instances)

        # 为Actor添加PlayerComponent
        for actor_entity in actor_entities:

            assert actor_entity is not None
            assert actor_entity.has(ActorComponent)
            assert not actor_entity.has(PlayerComponent)
            actor_entity.add(PlayerComponent, "")

        return actor_entities

    ###############################################################################################################################################
    def _retrieve_actors_with_stage_presence(
        self, game_resource: RPGGameResource, actors_instances: List[ActorInstanceModel]
    ) -> List[ActorInstanceModel]:

        unique_actor_names = set()

        stages_instances = game_resource.stages_instances
        for stage_instance in stages_instances:
            for actor_instance1 in stage_instance.actors:
                unique_actor_names.add(actor_instance1["name"])

        ret: List[ActorInstanceModel] = []
        for actor_instance2 in actors_instances:
            if actor_instance2.name in unique_actor_names:
                ret.append(actor_instance2)

        assert len(actors_instances) <= len(unique_actor_names)
        return ret

    ###############################################################################################################################################
    def _create_actor_entities(
        self, game_resource: RPGGameResource, actor_instances: List[ActorInstanceModel]
    ) -> List[Entity]:

        assert game_resource is not None
        assert game_resource.data_base is not None

        actors_with_stage_presence = self._retrieve_actors_with_stage_presence(
            game_resource, actor_instances
        )

        ret: List[Entity] = []

        for actor_instance in actors_with_stage_presence:

            actor_model = game_resource.data_base.get_actor(actor_instance.name)
            assert actor_model is not None

            entity = self._create_actor_entity(
                actor_instance, actor_model, self.context
            )
            assert entity is not None

            ret.append(entity)

        return ret

    ###############################################################################################################################################
    def _create_actor_entity(
        self,
        actor_instance: ActorInstanceModel,
        actor_model: ActorModel,
        context: RPGGameContext,
    ) -> Entity:

        if actor_instance.name != actor_model.name:
            assert actor_instance.name == ComplexActorName.format_name_with_guid(
                actor_model.name, actor_instance.guid
            ), """注意！你做了批量生成的actor但是生成出现了错误！"""

        # 创建实体
        actor_entity = context.create_entity()

        # 必要组件
        actor_entity.add(GUIDComponent, actor_instance.name, actor_instance.guid)

        actor_entity.add(ActorComponent, actor_instance.name, "")

        actor_entity.add(
            AttributesComponent,
            actor_instance.name,
            actor_model.attributes[Attributes.MAX_HP],
            actor_model.attributes[Attributes.CUR_HP],
            actor_model.attributes[Attributes.DAMAGE],
            actor_model.attributes[Attributes.DEFENSE],
            actor_model.attributes[Attributes.HEAL],
        )

        assert actor_model.base_form != ""
        actor_entity.add(BaseFormComponent, actor_instance.name, actor_model.base_form)
        actor_entity.add(
            FinalAppearanceComponent,
            actor_instance.name,
            "",
        )

        actor_entity.add(
            KickOffContentComponent, actor_instance.name, actor_model.kick_off_message
        )

        actor_entity.add(RoundEventsRecordComponent, actor_instance.name, [])

        # 添加扩展子系统: Agent
        context.agent_system.register_agent(actor_instance.name, actor_model.url)

        # 添加扩展子系统: CodeName
        code_name_component_class = (
            context.query_component_system.register_query_component_class(
                instance_name=actor_instance.name,
                data_base_code_name=actor_model.codename,
                guid=actor_instance.guid,
            )
        )
        assert code_name_component_class is not None
        actor_entity.add(code_name_component_class, actor_instance.name)

        # 文件系统：添加道具
        for prop_instance in actor_instance.props:
            ## 重构
            assert self._game_resource is not None
            prop_model = self._game_resource.data_base.get_prop(prop_instance.name)
            if prop_model is None:
                logger.error(f"没有从数据库找到道具：{prop_instance.name}")
                continue

            new_prop_file = PropFile(
                PropFileModel(
                    owner=actor_instance.name,
                    prop_model=prop_model,
                    prop_instance_model=prop_instance,
                )
            )
            context.file_system.add_file(new_prop_file)
            context.file_system.write_file(new_prop_file)

        # 文件系统：添加档案
        rpg_game_systems.file_system_utils.register_actor_archives(
            context.file_system, actor_instance.name, set(actor_model.actor_archives)
        )

        rpg_game_systems.file_system_utils.register_stage_archives(
            context.file_system, actor_instance.name, set(actor_model.stage_archives)
        )

        # 文件系统准备好之后，设置当前使用的道具
        weapon_prop_file: Optional[PropFile] = None
        clothes_prop_file: Optional[PropFile] = None
        for prop_name in actor_instance.actor_equipped_props:

            find_prop_file_weapon_or_clothes = context.file_system.get_file(
                PropFile, actor_instance.name, prop_name
            )
            if find_prop_file_weapon_or_clothes is None:
                logger.error(f"没有找到道具文件：{prop_name}")
                continue

            if find_prop_file_weapon_or_clothes.is_weapon and weapon_prop_file is None:
                weapon_prop_file = find_prop_file_weapon_or_clothes
            elif (
                find_prop_file_weapon_or_clothes.is_clothes
                and clothes_prop_file is None
            ):
                clothes_prop_file = find_prop_file_weapon_or_clothes

        if weapon_prop_file is not None and not actor_entity.has(WeaponComponent):
            actor_entity.add(
                WeaponComponent, actor_instance.name, weapon_prop_file.name
            )

        if clothes_prop_file is not None and not actor_entity.has(ClothesComponent):
            actor_entity.add(
                ClothesComponent, actor_instance.name, clothes_prop_file.name
            )

        return actor_entity

    ###############################################################################################################################################
    def _create_stage_entities(self, game_resource: RPGGameResource) -> List[Entity]:

        assert game_resource is not None

        ret: List[Entity] = []

        for stage_instance in game_resource.stages_instances:

            stage_model = game_resource.data_base.get_stage(stage_instance.name)
            assert stage_model is not None

            stage_entity = self._create_stage_entity(
                stage_instance, stage_model, self.context
            )
            assert stage_entity is not None

            ret.append(stage_entity)

        return ret

    ###############################################################################################################################################
    def _create_stage_entity(
        self,
        stage_instance: StageInstanceModel,
        stage_model: StageModel,
        context: RPGGameContext,
    ) -> Entity:

        assert stage_instance is not None
        assert stage_model is not None
        assert stage_instance.name == stage_model.name
        assert context is not None

        # 创建实体
        stage_entity = context.create_entity()

        # 必要组件
        stage_entity.add(GUIDComponent, stage_model.name, stage_instance.guid)
        stage_entity.add(StageComponent, stage_model.name)

        # 记录属性
        stage_entity.add(
            AttributesComponent,
            stage_model.name,
            stage_model.attributes[Attributes.MAX_HP],
            stage_model.attributes[Attributes.CUR_HP],
            stage_model.attributes[Attributes.DAMAGE],
            stage_model.attributes[Attributes.DEFENSE],
            stage_model.attributes[Attributes.HEAL],
        )

        # 记录用
        stage_entity.add(
            KickOffContentComponent, stage_model.name, stage_model.kick_off_message
        )

        # 记录用
        stage_entity.add(RoundEventsRecordComponent, stage_model.name, [])

        # 添加场景可以连接的场景
        stage_entity.add(StageGraphComponent, stage_model.name, stage_model.stage_graph)

        # 添加spawners
        stage_entity.add(
            StageSpawnerComponent, stage_model.name, stage_instance.spawners
        )

        ## 添加场景环境信息。
        stage_entity.add(StageEnvironmentComponent, stage_model.name, "")

        ## todo 全部静态场景，除了第一次kick off，后续全部不做环境变化
        stage_entity.add(StageStaticFlagComponent, stage_model.name)

        ## 重新设置Actor和stage的关系
        for actor_instance in stage_instance.actors:

            actor_name = actor_instance["name"]
            actor_entity: Optional[Entity] = context.get_actor_entity(actor_name)
            assert actor_entity is not None

            actor_entity.replace(ActorComponent, actor_name, stage_model.name)

        # 添加子系统：Agent
        context.agent_system.register_agent(stage_model.name, stage_model.url)

        # 添加子系统：CodeName
        code_name_component_class = (
            context.query_component_system.register_query_component_class(
                instance_name=stage_instance.name,
                data_base_code_name=stage_model.codename,
                guid=stage_instance.guid,
            )
        )
        assert code_name_component_class is not None
        stage_entity.add(code_name_component_class, stage_instance.name)

        # 添加子系统：StageTag
        context.query_component_system.register_stage_tag_component_class(
            stage_model.name, f"""{stage_model.codename}{stage_instance.guid}"""
        )

        return stage_entity

    ###############################################################################################################################################
    def _initialize_actor_stage_links(self, actor_entities: Set[Entity]) -> None:
        # 只有初始化级别的调用，才能使用这个函数
        for actor_entity in actor_entities:
            actor_comp = actor_entity.get(ActorComponent)
            assert actor_comp.current_stage != ""
            self.context.update_stage_tag_component(
                actor_entity, "", actor_comp.current_stage
            )

    ###############################################################################################################################################
    def add_player(self, player_proxy: PlayerProxy) -> None:
        assert player_proxy not in self._players
        if player_proxy not in self._players:
            self._players.append(player_proxy)

    ###############################################################################################################################################
    def get_player(self, player_name: str) -> Optional[PlayerProxy]:
        for player in self._players:
            if player.player_name == player_name:
                return player
        return None

    ###############################################################################################################################################
    def _load_game(
        self, context: RPGGameContext, game_resource: RPGGameResource
    ) -> None:

        # 存储的局数拿回来
        self._runtime_round = game_resource.save_round

        # 重新加载相关的对像
        self._load_entities(context, game_resource)
        self._load_agents(context, game_resource)
        self._load_archives(context, game_resource)
        self._load_players(context, game_resource)  # 必须在最后！

    ###############################################################################################################################################
    def _load_entities(
        self, context: RPGGameContext, game_resource: RPGGameResource
    ) -> None:

        assert game_resource.is_load

        load_entities = context.get_group(
            Matcher(
                any_of=[
                    AttributesComponent,
                    FinalAppearanceComponent,
                    PlayerComponent,
                    KickOffFlagComponent,
                    BaseFormComponent,
                    StageEnvironmentComponent,
                ]
            )
        ).entities

        for load_entity in load_entities:

            safe_name = context.safe_get_entity_name(load_entity)
            if safe_name == "":
                continue

            model = game_resource.get_entity_profile(safe_name)
            if model is None:
                continue

            assert model.name == safe_name

            for comp in model.components:

                # 只有这些组件需要处理
                match (comp.name):

                    case AttributesComponent.__name__:
                        rpg_attr_comp = AttributesComponent(**comp.data)
                        load_entity.replace(
                            AttributesComponent,
                            rpg_attr_comp.name,
                            rpg_attr_comp.max_hp,
                            rpg_attr_comp.cur_hp,
                            rpg_attr_comp.damage,
                            rpg_attr_comp.defense,
                            rpg_attr_comp.heal,
                        )

                    case FinalAppearanceComponent.__name__:
                        appearance_comp = FinalAppearanceComponent(**comp.data)
                        load_entity.replace(
                            FinalAppearanceComponent,
                            appearance_comp.name,
                            appearance_comp.final_appearance,
                        )

                    case PlayerComponent.__name__:
                        player_comp = PlayerComponent(**comp.data)
                        load_entity.replace(PlayerComponent, player_comp.name)

                    case KickOffFlagComponent.__name__:
                        kick_off_flag_comp = KickOffFlagComponent(**comp.data)
                        load_entity.replace(
                            KickOffFlagComponent, kick_off_flag_comp.name
                        )

                    case BaseFormComponent.__name__:
                        base_form_comp = BaseFormComponent(**comp.data)
                        load_entity.replace(
                            BaseFormComponent,
                            base_form_comp.name,
                            base_form_comp.base_form,
                        )

                    case StageEnvironmentComponent.__name__:
                        stage_env_comp = StageEnvironmentComponent(**comp.data)
                        load_entity.replace(
                            StageEnvironmentComponent,
                            stage_env_comp.name,
                            stage_env_comp.narrate,
                        )

                    case _:
                        pass

    ###############################################################################################################################################
    def _load_agents(
        self, context: RPGGameContext, game_resource: RPGGameResource
    ) -> None:

        assert game_resource.is_load

        load_entities = context.get_group(
            Matcher(any_of=[ActorComponent, StageComponent])
        ).entities

        for load_entity in load_entities:
            safe_name = context.safe_get_entity_name(load_entity)
            if safe_name == "":
                continue

            chat_history = game_resource.get_chat_history(safe_name)
            if chat_history is None:
                continue

            context.agent_system.initialize_chat_history(safe_name, chat_history)

    ###############################################################################################################################################
    def _load_archives(
        self, context: RPGGameContext, game_resource: RPGGameResource
    ) -> None:

        assert game_resource.is_load

        load_entities = context.get_group(
            Matcher(any_of=[ActorComponent, StageComponent])
        ).entities

        for load_entity in load_entities:
            safe_name = context.safe_get_entity_name(load_entity)
            if safe_name == "":
                continue

            actor_archives = game_resource.retrieve_actor_archives(safe_name)
            rpg_game_systems.file_system_utils.load_actor_archives(
                context.file_system, safe_name, actor_archives
            )

            stage_archives = game_resource.retrieve_stage_archives(safe_name)
            rpg_game_systems.file_system_utils.load_stage_archives(
                context.file_system, safe_name, stage_archives
            )

    ###############################################################################################################################################
    def _load_players(
        self, context: RPGGameContext, game_resource: RPGGameResource
    ) -> None:

        assert game_resource.is_load
        player_entities = context.get_group(Matcher(any_of=[PlayerComponent])).entities

        for player_entity in player_entities:

            player_comp = player_entity.get(PlayerComponent)
            player_proxy_model = game_resource.get_player_proxy(player_comp.name)
            if player_proxy_model is None:
                continue

            player_proxy = PlayerProxy(player_proxy_model)
            self.add_player(player_proxy)
            player_proxy.on_load()

    ###############################################################################################################################################
    @override
    def send_event(self, player_proxy_names: Set[str], send_event: BaseEvent) -> None:

        for player_proxy_name in player_proxy_names:
            player_proxy = self.get_player(player_proxy_name)
            if player_proxy is None:
                assert False, f"没有找到玩家：{player_proxy_name}"
                continue

            assert player_proxy.actor_name != ""
            send_event.message = rpg_game_systems.prompt_utils.replace_with_you(
                send_event.message,
                player_proxy.actor_name,
            )

            player_proxy.add_actor_message(player_proxy.actor_name, send_event)

    ###############################################################################################################################################
    def create_actor_entity_at_runtime(
        self,
        actor_instance: ActorInstanceModel,
        actor_model: ActorModel,
        stage_entity: Entity,
    ) -> Optional[Entity]:

        logger.warning(
            f"runtime_create_actor_entity: {actor_instance.name}, !!!!!!!!!!!!!!!!!!!!!"
        )

        assert stage_entity.has(StageComponent)
        actor_entity = self._create_actor_entity(
            actor_instance, actor_model, self.context
        )
        if actor_entity is None:
            return None

        actor_comp = actor_entity.get(ActorComponent)
        assert actor_comp.current_stage == ""

        # 重新设置值
        stage_comp = stage_entity.get(StageComponent)
        actor_entity.replace(ActorComponent, actor_comp.name, stage_comp.name)

        # 必须使用这个更新
        self._initialize_actor_stage_links(set({actor_entity}))

        return actor_entity

    ###############################################################################################################################################
