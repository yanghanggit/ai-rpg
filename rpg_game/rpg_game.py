from entitas import Matcher, Entity  # type: ignore
from typing import List, Optional, Set
from overrides import override
from loguru import logger
from gameplay_systems.components import (
    WorldComponent,
    StageComponent,
    ActorComponent,
    PlayerComponent,
    RPGAttributesComponent,
    AppearanceComponent,
    BodyComponent,
    GUIDComponent,
    RPGCurrentWeaponComponent,
    RPGCurrentClothesComponent,
    StageGraphComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from my_data.game_resource import GameResource
from extended_systems.files_def import PropFile
import shutil
from rpg_game.base_game import BaseGame
import extended_systems.file_system_helper
from rpg_game.rpg_entitas_processors import RPGEntitasProcessors
from my_data.model_def import (
    ActorProxyModel,
    StageProxyModel,
    ActorModel,
    StageModel,
    WorldSystemModel,
    WorldSystemProxyModel,
)
from my_data.model_def import AttributesIndex
from player.player_proxy import PlayerProxy


class RPGGame(BaseGame):
    """
    RPG 的测试类游戏
    """

    def __init__(self, name: str, context: RPGEntitasContext) -> None:
        # 必须实现父
        super().__init__(name)

        ## 尽量不要再加东西了，Game就只管上下文，创建世界的数据，和Processors。其中上下文可以做运行中的全局数据管理者
        self._entitas_context: RPGEntitasContext = context
        self._entitas_context._game = self

        self._game_resource: Optional[GameResource] = None
        self._processors: RPGEntitasProcessors = RPGEntitasProcessors.create(
            self, context
        )
        self._players: List[PlayerProxy] = []
        self._round: int = 0

    ###############################################################################################################################################
    def build(self, game_resource: GameResource) -> "RPGGame":

        context = self._entitas_context

        # 第0步，yh 目前用于测试!!!!!!!，直接删worlddata.name的文件夹，保证每次都是新的 删除runtime_dir_for_world的文件夹
        if game_resource._runtime_dir.exists():
            # todo
            logger.warning(
                f"删除文件夹：{game_resource._runtime_dir}, 这是为了测试，后续得改！！！"
            )
            shutil.rmtree(game_resource._runtime_dir)

        # 混沌系统，准备测试
        context._chaos_engineering_system.on_pre_create_game(context, game_resource)

        ## 第1步，设置根路径
        self._game_resource = game_resource
        context._langserve_agent_system.set_runtime_dir(game_resource._runtime_dir)
        context._kick_off_message_system.set_runtime_dir(game_resource._runtime_dir)
        context._file_system.set_runtime_dir(game_resource._runtime_dir)

        ## 第2步 创建管理员类型的角色，全局的AI
        self.create_world_system_entities(game_resource)

        ## 第3步，创建actor，player是特殊的actor
        self.create_player_entities(game_resource, game_resource.players_proxy)
        self.create_actor_entities(game_resource, game_resource.actors_proxy)
        self.add_code_name_component_to_world_and_actors()

        ## 第4步，创建stage
        self.create_stage_entities(game_resource)

        ## 第5步，最后处理因为需要上一阶段的注册流程
        self.add_code_name_component_to_stages()

        ## 最后！混沌系统，准备测试
        context._chaos_engineering_system.on_post_create_game(context, game_resource)

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
    def create_world_system_entities(self, game_resource: GameResource) -> List[Entity]:

        assert game_resource is not None
        assert game_resource._data_base is not None

        ret: List[Entity] = []

        for world_system_proxy in game_resource.world_systems_proxy:

            world_system_model = game_resource._data_base.get_world_system(
                world_system_proxy.name
            )
            assert world_system_model is not None

            world_system_entity = self.create_world_system_entity(
                world_system_proxy, world_system_model, self._entitas_context
            )
            assert world_system_entity is not None

            ret.append(world_system_entity)

        return ret

    ###############################################################################################################################################
    def create_world_system_entity(
        self,
        world_system_proxy: WorldSystemProxyModel,
        world_system_model: WorldSystemModel,
        context: RPGEntitasContext,
    ) -> Entity:

        # 创建实体
        world_system_entity = context.create_entity()
        assert world_system_entity is not None

        # 必要组件
        world_system_entity.add(
            GUIDComponent, world_system_model.name, world_system_proxy.guid
        )
        world_system_entity.add(WorldComponent, world_system_model.name)

        # 添加扩展子系统的功能
        context._langserve_agent_system.register_agent(
            world_system_model.name, world_system_model.url
        )
        context._codename_component_system.register_code_name_component_class(
            world_system_model.name, world_system_model.codename
        )

        return world_system_entity

    ###############################################################################################################################################
    def create_player_entities(
        self, game_resource: GameResource, actors_proxy: List[ActorProxyModel]
    ) -> List[Entity]:

        assert game_resource is not None

        # 创建player 本质就是创建Actor
        actor_entities = self.create_actor_entities(game_resource, actors_proxy)

        # 为Actor添加PlayerComponent
        for actor_entity in actor_entities:

            assert actor_entity is not None
            assert actor_entity.has(ActorComponent)
            assert not actor_entity.has(PlayerComponent)
            actor_entity.add(PlayerComponent, "")

        return actor_entities

    ###############################################################################################################################################
    def create_actor_entities(
        self, game_resource: GameResource, actors_proxy: List[ActorProxyModel]
    ) -> List[Entity]:

        assert game_resource is not None
        assert game_resource._data_base is not None

        ret: List[Entity] = []

        for actor_proxy in actors_proxy:

            actor_model = game_resource._data_base.get_actor(actor_proxy.name)
            assert actor_model is not None

            entity = self.create_actor_entity(
                actor_proxy, actor_model, self._entitas_context
            )  # context.create_entity()
            assert entity is not None

            ret.append(entity)

        return ret

    ###############################################################################################################################################
    def create_actor_entity(
        self,
        actor_proxy: ActorProxyModel,
        actor_model: ActorModel,
        context: RPGEntitasContext,
    ) -> Entity:

        # 创建实体
        actor_entity = context.create_entity()

        # 必要组件
        actor_entity.add(GUIDComponent, actor_model.name, actor_proxy.guid)

        assert actor_proxy.name == actor_model.name
        actor_entity.add(ActorComponent, actor_model.name, "")

        actor_entity.add(
            RPGAttributesComponent,
            actor_model.name,
            actor_model.attributes[AttributesIndex.MAX_HP.value],
            actor_model.attributes[AttributesIndex.CUR_HP.value],
            actor_model.attributes[AttributesIndex.DAMAGE.value],
            actor_model.attributes[AttributesIndex.DEFENSE.value],
        )

        hash_code = hash(actor_model.body)
        actor_entity.add(
            AppearanceComponent, actor_model.name, actor_model.body, hash_code
        )
        actor_entity.add(BodyComponent, actor_model.name, actor_model.body)

        # 添加扩展子系统的
        context._langserve_agent_system.register_agent(
            actor_model.name, actor_model.url
        )
        context._kick_off_message_system.add_message(
            actor_model.name, actor_model.kick_off_message
        )
        context._codename_component_system.register_code_name_component_class(
            actor_model.name, actor_model.codename
        )

        # 添加道具
        for prop_proxy in actor_proxy.props:
            ## 重构
            assert self._game_resource is not None
            prop_model = self._game_resource._data_base.get_prop(prop_proxy.name)
            if prop_model is None:
                logger.error(f"没有从数据库找到道具：{prop_proxy.name}")
                continue

            new_prop_file = PropFile(
                prop_proxy.guid,
                prop_model.name,
                actor_proxy.name,
                prop_model,
                prop_proxy.count,
            )
            context._file_system.add_file(new_prop_file)
            context._file_system.write_file(new_prop_file)
            context._codename_component_system.register_code_name_component_class(
                prop_model.name, prop_model.codename
            )

        extended_systems.file_system_helper.add_actor_archive_files(
            context._file_system, actor_model.name, set(actor_model.actor_archives)
        )

        extended_systems.file_system_helper.add_stage_archive_files(
            context._file_system, actor_model.name, set(actor_model.stage_archives)
        )

        weapon_prop_file: Optional[PropFile] = None
        clothes_prop_file: Optional[PropFile] = None
        for prop_name in actor_proxy.actor_current_using_prop:

            find_prop_file_weapon_or_clothes = context._file_system.get_file(
                PropFile, actor_model.name, prop_name
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

        if weapon_prop_file is not None and not actor_entity.has(
            RPGCurrentWeaponComponent
        ):
            actor_entity.add(
                RPGCurrentWeaponComponent, actor_model.name, weapon_prop_file.name
            )

        if clothes_prop_file is not None and not actor_entity.has(
            RPGCurrentClothesComponent
        ):
            actor_entity.add(
                RPGCurrentClothesComponent, actor_model.name, clothes_prop_file.name
            )

        return actor_entity

    ###############################################################################################################################################
    def create_stage_entities(self, game_resource: GameResource) -> List[Entity]:

        assert game_resource is not None

        ret: List[Entity] = []

        for stage_proxy in game_resource.stages_proxy:

            stage_model = game_resource._data_base.get_stage(stage_proxy.name)
            assert stage_model is not None

            stage_entity = self.create_stage_entity(
                stage_proxy, stage_model, self._entitas_context
            )
            assert stage_entity is not None

            ret.append(stage_entity)

        return ret

    ###############################################################################################################################################
    def create_stage_entity(
        self,
        stage_proxy: StageProxyModel,
        stage_model: StageModel,
        context: RPGEntitasContext,
    ) -> Entity:

        assert stage_proxy is not None
        assert stage_model is not None
        assert stage_proxy.name == stage_model.name
        assert context is not None

        # 创建实体
        stage_entity = context.create_entity()

        # 必要组件
        stage_entity.add(GUIDComponent, stage_model.name, stage_proxy.guid)
        stage_entity.add(StageComponent, stage_model.name)

        stage_entity.add(
            RPGAttributesComponent,
            stage_model.name,
            stage_model.attributes[AttributesIndex.MAX_HP.value],
            stage_model.attributes[AttributesIndex.CUR_HP.value],
            stage_model.attributes[AttributesIndex.DAMAGE.value],
            stage_model.attributes[AttributesIndex.DEFENSE.value],
        )

        ## 重新设置Actor和stage的关系
        for actor_proxy in stage_proxy.actors:

            actor_name = actor_proxy["name"]
            actor_entity: Optional[Entity] = context.get_actor_entity(actor_name)
            assert actor_entity is not None

            actor_entity.replace(ActorComponent, actor_name, stage_model.name)

        # 场景内添加道具
        for prop_proxy in stage_proxy.props:
            # 直接使用文件系统
            assert self._game_resource is not None
            prop_model = self._game_resource._data_base.get_prop(prop_proxy.name)
            if prop_model is None:
                logger.error(f"没有从数据库找到道具：{prop_proxy.name}")
                continue

            prop_file = PropFile(
                prop_proxy.guid,
                prop_proxy.name,
                stage_model.name,
                prop_model,
                prop_proxy.count,
            )
            context._file_system.add_file(prop_file)
            context._file_system.write_file(prop_file)
            context._codename_component_system.register_code_name_component_class(
                prop_model.name, prop_model.codename
            )

        # 场景图的设置
        if len(stage_model.stage_graph) > 0:
            logger.debug(
                f"场景：{stage_model.name}，可去往的场景：{stage_model.stage_graph}"
            )

        stage_entity.add(StageGraphComponent, stage_model.name, stage_model.stage_graph)

        # 添加子系统！
        context._langserve_agent_system.register_agent(
            stage_model.name, stage_model.url
        )
        context._kick_off_message_system.add_message(
            stage_model.name, stage_model.kick_off_message
        )
        context._codename_component_system.register_code_name_component_class(
            stage_model.name, stage_model.codename
        )
        context._codename_component_system.register_stage_tag_component_class(
            stage_model.name, stage_model.codename
        )

        return stage_entity

    ###############################################################################################################################################
    def add_code_name_component_to_world_and_actors(self) -> None:

        #
        world_entities = self._entitas_context.get_group(
            Matcher(WorldComponent)
        ).entities
        for world_entity in world_entities:
            world_comp = world_entity.get(WorldComponent)
            codecomp_class = self._entitas_context._codename_component_system.get_code_name_component_class(
                world_comp.name
            )
            if codecomp_class is not None:
                world_entity.add(codecomp_class, world_comp.name)

        #
        actor_entities = self._entitas_context.get_group(
            Matcher(ActorComponent)
        ).entities
        for actor_entity in actor_entities:
            actor_comp = actor_entity.get(ActorComponent)
            codecomp_class = self._entitas_context._codename_component_system.get_code_name_component_class(
                actor_comp.name
            )
            if codecomp_class is not None:
                actor_entity.add(codecomp_class, actor_comp.name)

    ###############################################################################################################################################
    def add_code_name_component_to_stages(self) -> None:

        ## 重新设置actor和stage的关系
        actor_entities = self._entitas_context.get_group(
            Matcher(ActorComponent)
        ).entities
        for actor_entity in actor_entities:
            actor_comp = actor_entity.get(ActorComponent)
            self._entitas_context.change_stage_tag_component(
                actor_entity, "", actor_comp.current_stage
            )

        ## 重新设置stage和stage的关系
        stage_entities = self._entitas_context.get_group(
            Matcher(StageComponent)
        ).entities
        for stage_entity in stage_entities:
            stage_comp = stage_entity.get(StageComponent)
            codecomp_class = self._entitas_context._codename_component_system.get_code_name_component_class(
                stage_comp.name
            )
            if codecomp_class is not None:
                stage_entity.add(codecomp_class, stage_comp.name)

    ###############################################################################################################################################
    @property
    def about_game(self) -> str:
        if self._game_resource is None:
            return ""
        return self._game_resource.about_game

    ###############################################################################################################################################
    def add_player(self, player_proxy: PlayerProxy) -> None:
        assert player_proxy not in self._players
        if player_proxy not in self._players:
            self._players.append(player_proxy)

    ###############################################################################################################################################
    @property
    def players(self) -> List[PlayerProxy]:
        return self._players

    ###############################################################################################################################################
    def get_player(self, player_name: str) -> Optional[PlayerProxy]:
        for player in self._players:
            if player._name == player_name:
                return player
        return None

    ###############################################################################################################################################
    @property
    def round(self) -> int:
        return self._round

    ###############################################################################################################################################
