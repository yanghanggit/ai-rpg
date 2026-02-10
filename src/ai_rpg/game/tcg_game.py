"""
TCG 游戏核心实现

融合交易卡牌战斗机制的 RPG 游戏，包含地下城探险、战斗系统和流程管道管理。
"""

from typing import Final
from loguru import logger
from .rpg_game_pipeline_manager import RPGGameProcessPipeline
from .rpg_game import RPGGame
from ..game.tcg_game_process_pipeline import (
    create_npc_home_pipeline,
    create_player_home_pipeline,
    create_combat_execution_pipeline,
    create_combat_archive_pipeline,
    create_combat_status_evaluation_pipeline,
)
from ..models import (
    Dungeon,
    CombatSequence,
    World,
    HandComponent,
    StageType,
    ActorType,
)
from .player_session import PlayerSession
from ..entitas import Matcher


#################################################################################################################################################
class TCGGame(RPGGame):
    """
    交易卡牌游戏，融合卡牌战斗机制的RPG游戏实现

    Attributes:
        _npc_home_pipeline: NPC家园场景流程管道
        _player_home_pipeline: 玩家家园场景流程管道
        _combat_execution_pipeline: 地下城战斗执行流程管道
        _combat_archive_pipeline: 地下城战斗归档流程管道
        _combat_status_evaluation_pipeline: 战斗状态效果评估流程管道
    """

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
            create_npc_home_pipeline(self)
        )

        # 仅处理player的home流程
        self._player_home_pipeline: Final[RPGGameProcessPipeline] = (
            create_player_home_pipeline(self)
        )

        # 地下城战斗流程
        self._combat_execution_pipeline: Final[RPGGameProcessPipeline] = (
            create_combat_execution_pipeline(self)
        )

        # 地下城归档流程管道
        self._combat_archive_pipeline: Final[RPGGameProcessPipeline] = (
            create_combat_archive_pipeline(self)
        )

        # 战斗状态效果评估流程管道
        self._combat_status_evaluation_pipeline: Final[RPGGameProcessPipeline] = (
            create_combat_status_evaluation_pipeline(self)
        )

        # 注册所有管道到管道管理器
        self.register_pipeline(self._npc_home_pipeline)
        self.register_pipeline(self._player_home_pipeline)
        self.register_pipeline(self._combat_execution_pipeline)
        self.register_pipeline(self._combat_archive_pipeline)
        self.register_pipeline(self._combat_status_evaluation_pipeline)

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
    def combat_execution_pipeline(self) -> RPGGameProcessPipeline:
        return self._combat_execution_pipeline

    ###############################################################################################################################################
    @property
    def combat_archive_pipeline(self) -> RPGGameProcessPipeline:
        return self._combat_archive_pipeline

    ###############################################################################################################################################
    @property
    def combat_status_evaluation_pipeline(self) -> RPGGameProcessPipeline:
        return self._combat_status_evaluation_pipeline

    ###############################################################################################################################################

    @property
    def is_player_in_home_stage(self) -> bool:
        """检查玩家是否在家园场景中"""
        player_entity = self.get_player_entity()
        assert player_entity is not None, "player_entity is None"
        if player_entity is None:
            return False

        return self.is_actor_in_home_stage(player_entity)

    ###############################################################################################################################################
    @property
    def is_player_in_dungeon_stage(self) -> bool:
        """检查玩家是否在地下城场景中"""
        player_entity = self.get_player_entity()
        assert player_entity is not None, "player_entity is None"
        if player_entity is None:
            return False

        return self.is_actor_in_dungeon_stage(player_entity)

    #######################################################################################################################################
    def setup_dungeon_entities(self, dungeon_model: Dungeon) -> None:
        """根据地下城模型初始化并创建相关游戏实体（敌人和场景）

        Args:
            dungeon_model: 地下城数据模型
        """

        # 加一步测试: 不可以存在！如果存在说明没有清空。
        for actor in dungeon_model.actors:
            actor_entity = self.get_actor_entity(actor.name)
            assert actor_entity is None, "actor_entity is not None"
            assert (
                actor.character_sheet.type == ActorType.ENEMY
            ), "actor_entity is not enemy type"

        # 加一步测试: 不可以存在！如果存在说明没有清空。
        for stage in dungeon_model.stages:
            stage_entity = self.get_stage_entity(stage.name)
            assert stage_entity is None, "stage_entity is not None"
            assert (
                stage.stage_profile.type == StageType.DUNGEON
            ), "stage_entity is not dungeon type"

        # 正式创建。。。。。。。。。。
        # 创建地下城的怪物。
        self._create_actor_entities(dungeon_model.actors)
        ## 创建地下城的场景
        self._create_stage_entities(dungeon_model.stages)

    #######################################################################################################################################
    def teardown_dungeon_entities(self, dungeon_model: Dungeon) -> None:
        """根据地下城模型清理并销毁相关游戏实体（敌人和场景）

        Args:
            dungeon_model: 地下城数据模型
        """
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

    ################################################################################################################
    def clear_hands(self) -> None:
        """清除所有角色实体的手牌组件"""
        actor_entities = self.get_group(Matcher(HandComponent)).entities.copy()
        for entity in actor_entities:
            logger.debug(f"clear hands: {entity.name}")
            entity.remove(HandComponent)

    ################################################################################################################
