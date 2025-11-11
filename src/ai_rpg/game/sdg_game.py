"""Social Deduction Game (狼人杀游戏)模块"""

from typing import Final, List
from loguru import logger
from overrides import override
from ..entitas import Entity, Matcher
from .rpg_game_pipeline_manager import RPGGameProcessPipeline
from .rpg_game import RPGGame
from .sdg_game_process_pipeline import (
    create_werewolf_game_kickoff_pipline,
    create_werewolf_game_night_pipline,
    create_werewolf_game_day_pipline,
    create_werewolf_game_vote_pipline,
    # create_werewolf_pass_turn_pipeline,
)
from ..models import (
    Actor,
    ActorComponent,
    World,
    WerewolfCharacterSheetName,
    ModeratorComponent,
    WerewolfComponent,
    SeerComponent,
    WitchComponent,
    VillagerComponent,
    HunterComponent,
)
from .player_session import PlayerSession
from ..entitas.components import Component


#################################################################################################################################################
class SDGGame(RPGGame):
    """
    Social Deduction Game (狼人杀游戏)
    专门处理狼人杀相关的游戏逻辑
    """

    def __init__(
        self,
        name: str,
        player_session: PlayerSession,
        world: World,
    ) -> None:
        # 调用父类初始化
        super().__init__(name, player_session, world)

        # 狼人杀的流程管道
        self._werewolf_game_kickoff_pipeline: Final[RPGGameProcessPipeline] = (
            create_werewolf_game_kickoff_pipline(self)
        )

        self._werewolf_game_night_pipeline: Final[RPGGameProcessPipeline] = (
            create_werewolf_game_night_pipline(self)
        )

        self._werewolf_game_day_pipeline: Final[RPGGameProcessPipeline] = (
            create_werewolf_game_day_pipline(self)
        )

        self._werewolf_game_vote_pipeline: Final[RPGGameProcessPipeline] = (
            create_werewolf_game_vote_pipline(self)
        )
        # self._werewolf_game_pass_turn_pipeline: Final[RPGGameProcessPipeline] = (
        #     create_werewolf_pass_turn_pipeline(self)
        # )

        # 注册狼人杀管道到管道管理器
        self.register_pipeline(self._werewolf_game_kickoff_pipeline)
        self.register_pipeline(self._werewolf_game_night_pipeline)
        self.register_pipeline(self._werewolf_game_day_pipeline)
        self.register_pipeline(self._werewolf_game_vote_pipeline)
        # self.register_pipeline(self._werewolf_game_pass_turn_pipeline)
        # 狼人杀专用：游戏回合计数器
        self._turn_counter: int = 0

        # 游戏是否启动?
        self._started: bool = False

    ###############################################################################################################################################
    @property
    def werewolf_game_kickoff_pipeline(self) -> RPGGameProcessPipeline:
        """获取狼人杀启动流程管道"""
        return self._werewolf_game_kickoff_pipeline

    ###############################################################################################################################################
    @property
    def werewolf_game_night_pipeline(self) -> RPGGameProcessPipeline:
        """获取狼人杀夜晚流程管道"""
        return self._werewolf_game_night_pipeline

    ###############################################################################################################################################
    @property
    def werewolf_game_day_pipeline(self) -> RPGGameProcessPipeline:
        """获取狼人杀白天流程管道"""
        return self._werewolf_game_day_pipeline

    ###############################################################################################################################################
    @property
    def werewolf_game_vote_pipeline(self) -> RPGGameProcessPipeline:
        """获取狼人杀投票流程管道"""
        return self._werewolf_game_vote_pipeline

    ###############################################################################################################################################
    # @property
    # def werewolf_game_pass_turn_pipeline(self) -> RPGGameProcessPipeline:
    #     """获取狼人杀过渡流程管道"""
    #     return self._werewolf_game_pass_turn_pipeline

    ###############################################################################################################################################
    @override
    def new_game(self) -> "SDGGame":
        """
        创建新的狼人杀游戏
        在父类的基础上增加狼人杀角色分配
        """
        # 调用父类的 new_game 方法
        super().new_game()

        # 第5步，狼人杀专用，分配角色
        self._assign_werewolf_roles_to_actors(self.world.boot.actors)

        return self

    ###############################################################################################################################################
    def _assign_werewolf_roles_to_actors(
        self, actor_models: List[Actor]
    ) -> List[Entity]:
        """
        为角色分配狼人杀专用的角色组件

        Args:
            actor_models: 角色模型列表

        Returns:
            List[Entity]: 分配了角色的实体列表
        """
        ret: List[Entity] = []
        for actor_model in actor_models:

            # 创建实体
            actor_entity = self.get_actor_entity(actor_model.name)
            assert actor_entity is not None, "actor_entity is not None"
            assert actor_entity.has(
                ActorComponent
            ), "actor_entity should have ActorComponent"

            # 狼人杀专用，根据角色表分配组件
            match actor_model.character_sheet.name:
                case WerewolfCharacterSheetName.MODERATOR:
                    actor_entity.replace(ModeratorComponent, actor_model.name)
                    logger.info(f"分配角色: {actor_model.name} -> Moderator")

                case WerewolfCharacterSheetName.WEREWOLF:
                    actor_entity.replace(WerewolfComponent, actor_model.name)
                    logger.info(f"分配角色: {actor_model.name} -> Werewolf")

                case WerewolfCharacterSheetName.SEER:
                    actor_entity.replace(SeerComponent, actor_model.name)
                    logger.info(f"分配角色: {actor_model.name} -> Seer")

                case WerewolfCharacterSheetName.WITCH:
                    actor_entity.replace(WitchComponent, actor_model.name)
                    logger.info(f"分配角色: {actor_model.name} -> Witch")

                case WerewolfCharacterSheetName.VILLAGER:
                    actor_entity.replace(VillagerComponent, actor_model.name)
                    logger.info(f"分配角色: {actor_model.name} -> Villager")

                case WerewolfCharacterSheetName.HUNTER:
                    actor_entity.replace(HunterComponent, actor_model.name)
                    logger.info(f"分配角色: {actor_model.name} -> Hunter")

                case _:
                    logger.debug(
                        f"应该不是狼人杀的角色: {actor_model.character_sheet.name}"
                    )
            # 添加到返回值
            ret.append(actor_entity)

        return ret

    ###############################################################################################################################################
    def cleanup_game_phase_markers(self, components: List[type[Component]]) -> None:
        assert len(components) > 0, "components should not be empty"
        if len(components) == 0:
            return

        # 清理夜晚阶段的计划标记组件
        # 获取所有带有夜晚计划标记的实体
        entities = self.get_group(
            Matcher(
                any_of=components,
            )
        ).entities.copy()

        # 移除所有夜晚计划标记,为新的一天做准备
        for entity in entities:
            for comp in components:
                if entity.has(comp):
                    # logger.debug(f"清理组件: {comp} from entity: {entity._name}")
                    entity.remove(comp)

    ###############################################################################################################################################
    def announce_to_players(self, message: str) -> None:
        # 获取所有角色玩家(狼人、预言家、女巫、村民)
        all_players = self.get_group(
            Matcher(
                any_of=[
                    WerewolfComponent,
                    SeerComponent,
                    WitchComponent,
                    VillagerComponent,
                    HunterComponent,
                ],
            )
        ).entities.copy()

        # 向所有玩家发送白天开始的消息
        for player in all_players:
            self.append_human_message(player, message)

    ###############################################################################################################################################
