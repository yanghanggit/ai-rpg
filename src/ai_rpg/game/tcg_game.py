import random
from typing import Final, Optional
from loguru import logger
from .rpg_game_pipeline_manager import RPGGameProcessPipeline
from .rpg_game import RPGGame
from ..game.tcg_game_process_pipeline import (
    create_npc_home_pipline,
    create_player_home_pipline,
    create_dungeon_combat_state_pipeline,
)
from ..models import (
    Dungeon,
    DungeonComponent,
    CombatSequence,
    EnvironmentComponent,
    World,
    Round,
)
from .player_session import PlayerSession


#################################################################################################################################################
class TCGGame(RPGGame):
    """Trading Card Game"""

    def __init__(
        self,
        name: str,
        player_session: PlayerSession,
        world: World,
    ) -> None:

        # 必须按着此顺序实现父类
        RPGGame.__init__(self, name, player_session, world)

        # 常规home 的流程
        self._npc_home_pipeline: Final[RPGGameProcessPipeline] = (
            create_npc_home_pipline(self)
        )

        # 仅处理player的home流程
        self._player_home_pipeline: Final[RPGGameProcessPipeline] = (
            create_player_home_pipline(self)
        )

        # 地下城战斗流程
        self._combat_pipeline: Final[RPGGameProcessPipeline] = (
            create_dungeon_combat_state_pipeline(self)
        )

        # 注册所有管道到管道管理器
        self.register_pipeline(self._npc_home_pipeline)
        self.register_pipeline(self._player_home_pipeline)
        self.register_pipeline(self._combat_pipeline)

    ###############################################################################################################################################
    @property
    def current_dungeon(self) -> Dungeon:
        return self.world.dungeon

    ###############################################################################################################################################
    @property
    def current_combat_sequence(self) -> CombatSequence:
        return self.current_dungeon.combat_sequence

    ###############################################################################################################################################
    @property
    def npc_home_pipeline(self) -> RPGGameProcessPipeline:
        return self._npc_home_pipeline

    ###############################################################################################################################################
    @property
    def player_home_pipeline(self) -> RPGGameProcessPipeline:
        return self._player_home_pipeline

    ###############################################################################################################################################
    @property
    def combat_pipeline(self) -> RPGGameProcessPipeline:
        return self._combat_pipeline

        ###############################################################################################################################################

    @property
    def is_player_at_home(self) -> bool:
        player_entity = self.get_player_entity()
        assert player_entity is not None, "player_entity is None"
        if player_entity is None:
            return False

        return self.is_actor_at_home(player_entity)

    ###############################################################################################################################################
    @property
    def is_player_in_dungeon(self) -> bool:
        player_entity = self.get_player_entity()
        assert player_entity is not None, "player_entity is None"
        if player_entity is None:
            return False

        return self.is_actor_in_dungeon(player_entity)

    #######################################################################################################################################
    def create_dungeon_entities(self, dungeon_model: Dungeon) -> None:

        # 加一步测试: 不可以存在！如果存在说明没有清空。
        for actor in dungeon_model.actors:
            actor_entity = self.get_actor_entity(actor.name)
            assert actor_entity is None, "actor_entity is not None"

        # 加一步测试: 不可以存在！如果存在说明没有清空。
        for stage in dungeon_model.stages:
            stage_entity = self.get_stage_entity(stage.name)
            assert stage_entity is None, "stage_entity is not None"

        # 正式创建。。。。。。。。。。
        # 创建地下城的怪物。
        self._create_actor_entities(dungeon_model.actors)
        ## 创建地下城的场景
        self._create_stage_entities(dungeon_model.stages)

    #######################################################################################################################################
    def destroy_dungeon_entities(self, dungeon_model: Dungeon) -> None:
        # 清空地下城的怪物。
        for actor in dungeon_model.actors:
            destroy_actor_entity = self.get_actor_entity(actor.name)
            if destroy_actor_entity is not None:
                self.destroy_entity(destroy_actor_entity)

        # 清空地下城的场景
        for stage in dungeon_model.stages:
            destroy_stage_entity = self.get_stage_entity(stage.name)
            if destroy_stage_entity is not None:
                self.destroy_entity(destroy_stage_entity)

    #######################################################################################################################################
    def start_new_round(self) -> Optional[Round]:

        if not self.current_combat_sequence.is_ongoing:
            logger.warning("当前没有进行中的战斗，不能设置回合。")
            return None

        if (
            len(self.current_combat_sequence.current_rounds) > 0
            and not self.current_combat_sequence.latest_round.has_ended
        ):
            # 有回合正在进行中，所以不能添加新的回合。
            logger.warning("有回合正在进行中，所以不能添加新的回合。")
            return None

        # 玩家角色
        player_entity = self.get_player_entity()
        assert player_entity is not None, "player_entity is None"

        # 所有角色
        actors_on_stage = self.get_alive_actors_on_stage(player_entity)
        assert len(actors_on_stage) > 0, "actors_on_stage is empty"

        # 当前舞台(必然是地下城！)
        stage_entity = self.safe_get_stage_entity(player_entity)
        assert stage_entity is not None, "stage_entity is None"
        assert stage_entity.has(DungeonComponent), "stage_entity 没有 DungeonComponent"

        # 随机打乱角色行动顺序
        shuffled_reactive_entities = list(actors_on_stage)
        random.shuffle(shuffled_reactive_entities)

        # 创建新的回合
        # new_round = self.current_combat_sequence.create_new_round(
        #     action_order=[entity.name for entity in shuffled_reactive_entities]
        # )

        # 设置回合的环境描写
        # new_round.environment = stage_entity.get(EnvironmentComponent).description
        # logger.debug(f"new_round:\n{new_round.model_dump_json(indent=2)}")
        return self.current_combat_sequence.create_new_round(
            action_order=[entity.name for entity in shuffled_reactive_entities]
        )
