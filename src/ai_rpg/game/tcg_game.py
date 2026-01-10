import random
from typing import Final, Optional
from loguru import logger
from .rpg_game_pipeline_manager import RPGGameProcessPipeline
from .rpg_game import RPGGame
from ..game.tcg_game_process_pipeline import (
    create_npc_home_pipeline,
    create_player_home_pipeline,
    create_dungeon_combat_pipeline,
)
from ..models import (
    Dungeon,
    DungeonComponent,
    CombatSequence,
    World,
    Round,
    HandComponent,
    StageType,
    ActorType,
)
from .player_session import PlayerSession
from ..entitas import Matcher


#################################################################################################################################################
class TCGGame(RPGGame):
    """
    交易卡牌游戏（Trading Card Game）

    TCGGame 是融合了卡牌战斗机制的 RPG 游戏实现，继承自 RPGGame 基类。
    该游戏包含家园场景和地下城战斗两大核心玩法，通过流程管道系统管理不同场景下的游戏逻辑。

    主要特性：
    - 多场景流程管理：NPC家园、玩家家园、地下城战斗
    - 回合制卡牌战斗系统：抽卡、出牌、裁决机制
    - 地下城实体生命周期管理：动态创建和销毁敌人与场景
    - 战斗序列管理：回合制战斗流程控制

    流程管道：
    - npc_home_pipeline: NPC在家园场景中的AI规划和行为
    - player_home_pipeline: 玩家在家园场景中的社交互动
    - combat_pipeline: 地下城中的卡牌战斗流程

    Attributes:
        _npc_home_pipeline: NPC家园场景流程管道
        _player_home_pipeline: 玩家家园场景流程管道
        _combat_pipeline: 地下城战斗流程管道

    继承自:
        RPGGame: 提供基础的RPG游戏功能和实体管理
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
        self._combat_pipeline: Final[RPGGameProcessPipeline] = (
            create_dungeon_combat_pipeline(self)
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
    def is_player_in_home_stage(self) -> bool:
        """
        检查玩家是否在家园场景中

        Returns:
            bool: 如果玩家当前在家园场景中返回 True，否则返回 False
        """
        player_entity = self.get_player_entity()
        assert player_entity is not None, "player_entity is None"
        if player_entity is None:
            return False

        return self.is_actor_in_home_stage(player_entity)

    ###############################################################################################################################################
    @property
    def is_player_in_dungeon_stage(self) -> bool:
        """
        检查玩家是否在地下城场景中

        Returns:
            bool: 如果玩家当前在地下城场景中返回 True，否则返回 False
        """
        player_entity = self.get_player_entity()
        assert player_entity is not None, "player_entity is None"
        if player_entity is None:
            return False

        return self.is_actor_in_dungeon_stage(player_entity)

    #######################################################################################################################################
    def setup_dungeon_entities(self, dungeon_model: Dungeon) -> None:
        """
        根据地下城模型初始化并创建所有相关游戏实体

        该方法会基于提供的地下城模型创建游戏中的实体对象，包括敌人角色和地下城场景。
        在创建前会进行验证检查，确保这些实体不存在（避免重复创建）。

        创建顺序：
        1. 验证所有角色实体不存在且类型为敌人
        2. 验证所有场景实体不存在且类型为地下城
        3. 创建所有角色实体（敌人）
        4. 创建所有场景实体（地下城场景）

        Args:
            dungeon_model: 地下城数据模型，包含角色和场景的配置信息

        Raises:
            AssertionError: 如果实体已存在或类型不匹配

        Note:
            此方法应与 teardown_dungeon_entities 成对使用，分别用于地下城的初始化和清理
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
        """
        根据地下城模型清理并销毁所有相关游戏实体

        该方法会基于提供的地下城模型销毁游戏中对应的实体对象，包括敌人角色和地下城场景。
        这是地下城生命周期管理的清理阶段，确保资源正确释放。

        清理顺序：
        1. 销毁所有角色实体（敌人）
        2. 销毁所有场景实体（地下城场景）

        Args:
            dungeon_model: 地下城数据模型，包含需要清理的角色和场景信息

        Note:
            - 此方法应与 setup_dungeon_entities 成对使用
            - 如果实体已被销毁，会安全跳过（不会抛出异常）
            - 通常在地下城战斗结束或玩家离开地下城时调用
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

    #######################################################################################################################################
    def create_next_round(self) -> Optional[Round]:
        """创建并初始化下一个战斗回合。

        该方法会创建一个新的战斗回合,随机打乱角色行动顺序,并将回合添加到当前战斗序列中。
        只有在满足以下条件时才会创建新回合:
        1. 当前存在进行中的战斗
        2. 没有未完成的回合

        Returns:
            Optional[Round]: 成功创建的回合对象,如果无法创建则返回 None。

        Note:
            - 该方法会随机打乱所有存活角色的行动顺序
            - 回合标签格式为 "round_{回合编号}"
            - 只能在地下城场景中调用
        """
        if not self.current_combat_sequence.is_ongoing:
            logger.warning("当前没有进行中的战斗，不能设置回合。")
            return None

        if (
            len(self.current_combat_sequence.current_rounds) > 0
            and not self.current_combat_sequence.latest_round.is_completed
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
        stage_entity = self.resolve_stage_entity(player_entity)
        assert stage_entity is not None, "stage_entity is None"
        assert stage_entity.has(DungeonComponent), "stage_entity 没有 DungeonComponent"

        # TODO 随机打乱角色行动顺序
        shuffled_reactive_entities = list(actors_on_stage)
        random.shuffle(shuffled_reactive_entities)

        # 设置回合的环境描写
        action_order = [entity.name for entity in shuffled_reactive_entities]
        round = Round(
            tag=f"round_{len(self.current_combat_sequence.current_rounds) + 1}",
            action_order=action_order,
        )
        self.current_combat_sequence.current_combat.rounds.append(round)
        logger.debug(
            f"新的回合开始 = {len(self.current_combat_sequence.current_rounds)}"
        )
        return round

    ################################################################################################################
    def clear_hands(self) -> None:
        """
        清除所有角色实体的手牌组件。

        在新回合开始前调用，移除所有角色的HandComponent，
        为生成新的手牌做准备。这是每回合卡牌抽取流程的第一步。
        """
        actor_entities = self.get_group(Matcher(HandComponent)).entities.copy()
        for entity in actor_entities:
            logger.debug(f"clear hands: {entity.name}")
            entity.remove(HandComponent)

    ################################################################################################################
