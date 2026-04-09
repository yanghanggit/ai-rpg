"""
TCG 游戏核心实现

融合交易卡牌战斗机制的 RPG 游戏，包含地下城探险、战斗系统和流程管道管理。
"""

from typing import Final
from loguru import logger
from .rpg_game_pipeline_manager import RPGGameProcessPipeline
from .rpg_game import RPGGame
from ..game.tcg_game_process_pipeline import (
    create_home_pipeline,
    create_combat_pipeline,
    create_dungeon_generate_pipeline,
)
from ..models import (
    Dungeon,
    World,
    HandComponent,
    DeckComponent,
    BlockComponent,
    StageType,
    ActorType,
    StatusEffectsComponent,
)
from .player_session import PlayerSession
from ..entitas import Matcher


#################################################################################################################################################


#################################################################################################################################################
class TCGGame(RPGGame):
    """
    交易卡牌游戏，融合卡牌战斗机制的RPG游戏实现

    Attributes:
        _home_pipeline: 家园场景流程管道（NPC 与玩家共用）
        _combat_execution_pipeline: 地下城战斗执行流程管道
    """

    def __init__(
        self,
        name: str,
        player_session: PlayerSession,
        world: World,
    ) -> None:

        # 必须按着此顺序实现父类
        RPGGame.__init__(self, name, player_session, world)

        # 家园流程（NPC 与玩家共用）
        self._home_pipeline: Final[RPGGameProcessPipeline] = create_home_pipeline(self)

        # 地下城战斗流程
        self._combat_pipeline: Final[RPGGameProcessPipeline] = create_combat_pipeline(
            self
        )

        # 地下城生成流程（LLM 文本生成 + 图片生成）
        self._dungeon_generate_pipeline: Final[RPGGameProcessPipeline] = (
            create_dungeon_generate_pipeline(self)
        )

        # 注册所有管道到管道管理器
        self.register_pipeline(self._home_pipeline)
        self.register_pipeline(self._combat_pipeline)
        self.register_pipeline(self._dungeon_generate_pipeline)

    ###############################################################################################################################################
    @property
    def current_dungeon(self) -> Dungeon:
        return self._world.dungeon

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

        if dungeon_model.setup_entities:
            logger.warning(f"地下城实体已设置，跳过创建: {dungeon_model.name}")
            return

        # 加一步测试: 不可以存在！如果存在说明没有清空。
        for actor in dungeon_model.actors:
            actor_entity = self.get_actor_entity(actor.name)
            assert actor_entity is None, "actor_entity is not None"
            assert (
                actor.character_sheet.type == ActorType.ENEMY
            ), "actor_entity is not enemy type"

        # 加一步测试: 不可以存在！如果存在说明没有清空。
        for room in dungeon_model.rooms:
            stage_entity = self.get_stage_entity(room.stage.name)
            assert stage_entity is None, "stage_entity is not None"
            assert (
                room.stage.stage_profile.type == StageType.DUNGEON
            ), "stage_entity is not dungeon type"

        logger.debug(f"正在根据地下城模型创建实体: {dungeon_model.name}")

        # 创建地下城的怪物。
        self._create_actor_entities(dungeon_model.actors)

        # 创建地下城的场景
        self._create_stage_entities([room.stage for room in dungeon_model.rooms])

        # 设置标记，避免重复创建。
        dungeon_model.setup_entities = True

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
        for room in dungeon_model.rooms:
            destroy_stage_entity = self.get_stage_entity(room.stage.name)
            if destroy_stage_entity is not None:
                self.destroy_entity(destroy_stage_entity)

    ################################################################################################################
    def clear_round_state(self) -> None:
        """清除所有角色实体的每回合可变状态（手牌与格挡）"""
        for entity in self.get_group(Matcher(HandComponent)).entities.copy():
            hand_comp = entity.get(HandComponent)
            assert hand_comp is not None
            # 将剩余手牌全部归还牌组，再移除手牌组件
            if hand_comp.cards:
                deck_comp = entity.get(DeckComponent)
                assert deck_comp is not None, f"{entity.name} 缺少 DeckComponent"
                deck_comp.cards.extend(hand_comp.cards)
                logger.debug(
                    f"clear hands: {entity.name} 归还 {len(hand_comp.cards)} 张剩余手牌到牌组，牌组累计 {len(deck_comp.cards)} 张"
                )
            else:
                logger.debug(f"clear hands: {entity.name}")
            entity.remove(HandComponent)
        for entity in self.get_group(Matcher(BlockComponent)).entities.copy():
            logger.debug(f"clear blocks: {entity.name}")
            entity.remove(BlockComponent)

    ################################################################################################################
    def clear_status_effects(self) -> None:
        """清除所有角色实体的状态效果组件"""
        actor_entities = self.get_group(Matcher(StatusEffectsComponent)).entities.copy()
        for entity in actor_entities:
            logger.debug(f"clear status effects: {entity.name}")
            entity.remove(StatusEffectsComponent)

    ################################################################################################################
