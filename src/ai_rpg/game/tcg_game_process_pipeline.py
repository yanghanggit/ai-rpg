from typing import Final, cast

from ..entitas import Processors
from ..game.base_game import BaseGame


def create_npc_home_pipline(game: BaseGame) -> "TCGGameProcessPipeline":

    ### 不这样就循环引用
    from ..game.tcg_game import TCGGame
    from ..game_systems.announce_action_system import AnnounceActionSystem
    from ..game_systems.destroy_entity_system import DestroyEntitySystem
    from ..game_systems.home_actor_system import (
        HomeActorSystem,
    )
    from ..game_systems.home_stage_system import (
        HomeStageSystem,
    )
    from ..game_systems.kick_off_system import KickOffSystem
    from ..game_systems.mind_voice_action_system import (
        MindVoiceActionSystem,
    )
    from ..game_systems.query_action_system import (
        QueryActionSystem,
    )
    from ..game_systems.action_cleanup_system import ActionCleanupSystem
    from ..game_systems.save_system import SaveSystem
    from ..game_systems.speak_action_system import SpeakActionSystem
    from ..game_systems.whisper_action_system import WhisperActionSystem
    from ..game_systems.home_auto_plan_system import HomeAutoPlanSystem
    from ..game_systems.trans_stage_action_system import (
        TransStageActionSystem,
    )

    ##
    tcg_game = cast(TCGGame, game)
    processors = TCGGameProcessPipeline("Home State Pipeline 1")

    # 启动agent的提示词。启动阶段
    processors.add(KickOffSystem(tcg_game, True))

    # 规划逻辑
    ######## 在所有规划之前!##############################################################
    processors.add(HomeAutoPlanSystem(tcg_game))
    processors.add(HomeStageSystem(tcg_game))
    processors.add(HomeActorSystem(tcg_game))
    ####### 在所有规划之后! ##############################################################

    # 动作处理相关的系统 ##################################################################
    ####################################################################################
    processors.add(MindVoiceActionSystem(tcg_game))
    processors.add(QueryActionSystem(tcg_game))
    processors.add(SpeakActionSystem(tcg_game))
    processors.add(WhisperActionSystem(tcg_game))
    processors.add(AnnounceActionSystem(tcg_game))
    processors.add(TransStageActionSystem(tcg_game))
    processors.add(ActionCleanupSystem(tcg_game))
    ####################################################################################
    ####################################################################################

    # 动作处理后，可能清理。
    processors.add(DestroyEntitySystem(tcg_game))

    # 存储系统。
    processors.add(SaveSystem(tcg_game))

    return processors


def create_player_home_pipline(game: BaseGame) -> "TCGGameProcessPipeline":

    ### 不这样就循环引用
    from ..game.tcg_game import TCGGame
    from ..game_systems.announce_action_system import AnnounceActionSystem
    from ..game_systems.destroy_entity_system import DestroyEntitySystem
    from ..game_systems.kick_off_system import KickOffSystem
    from ..game_systems.action_cleanup_system import ActionCleanupSystem
    from ..game_systems.save_system import SaveSystem
    from ..game_systems.speak_action_system import SpeakActionSystem
    from ..game_systems.whisper_action_system import WhisperActionSystem
    from ..game_systems.trans_stage_action_system import (
        TransStageActionSystem,
    )

    ##
    tcg_game = cast(TCGGame, game)
    processors = TCGGameProcessPipeline("Home State Pipeline 2")

    # 启动agent的提示词。启动阶段
    processors.add(KickOffSystem(tcg_game, True))

    # 动作处理相关的系统 ##################################################################
    ####################################################################################
    processors.add(SpeakActionSystem(tcg_game))
    processors.add(WhisperActionSystem(tcg_game))
    processors.add(AnnounceActionSystem(tcg_game))
    processors.add(TransStageActionSystem(tcg_game))
    processors.add(ActionCleanupSystem(tcg_game))
    ####################################################################################
    ####################################################################################

    # 动作处理后，可能清理。
    processors.add(DestroyEntitySystem(tcg_game))

    # 存储系统。
    processors.add(SaveSystem(tcg_game))

    return processors


def create_dungeon_combat_state_pipeline(
    game: BaseGame,
) -> "TCGGameProcessPipeline":

    ### 不这样就循环引用
    from ..game.tcg_game import TCGGame
    from ..game_systems.combat_outcome_system import CombatOutcomeSystem
    from ..game_systems.combat_initialization_system import (
        CombatInitializationSystem,
    )
    from ..game_systems.destroy_entity_system import DestroyEntitySystem
    from ..game_systems.draw_cards_action_system import (
        DrawCardsActionSystem,
    )
    from ..game_systems.play_cards_action_system import (
        PlayCardsActionSystem,
    )
    from ..game_systems.combat_post_processing_system import (
        CombatPostProcessingSystem,
    )
    from ..game_systems.kick_off_system import KickOffSystem
    from ..game_systems.action_cleanup_system import ActionCleanupSystem
    from ..game_systems.save_system import SaveSystem
    from ..game_systems.arbitration_action_system import ArbitrationActionSystem

    ##
    tcg_game = cast(TCGGame, game)
    processors = TCGGameProcessPipeline("Dungeon Combat State Pipeline")

    # 启动agent的提示词。启动阶段
    processors.add(KickOffSystem(tcg_game, True))
    processors.add(CombatInitializationSystem(tcg_game))

    # 抽卡。
    ######动作开始！！！！！################################################################################################
    processors.add(DrawCardsActionSystem(tcg_game))
    processors.add(PlayCardsActionSystem(tcg_game))
    processors.add(ArbitrationActionSystem(tcg_game))
    processors.add(ActionCleanupSystem(tcg_game))
    ###### 动作结束！！！！！################################################################################################

    # 检查死亡
    processors.add(CombatOutcomeSystem(tcg_game))
    processors.add(CombatPostProcessingSystem(tcg_game))

    # 核心系统，检查需要删除的实体。
    processors.add(DestroyEntitySystem(tcg_game))

    # 核心系统，存储系统。
    processors.add(SaveSystem(tcg_game))

    return processors


def create_werewolf_game_kickoff_pipline(game: BaseGame) -> "TCGGameProcessPipeline":
    ### 不这样就循环引用
    from ..game.tcg_game import TCGGame
    from ..game_systems.destroy_entity_system import DestroyEntitySystem
    from ..game_systems.action_cleanup_system import ActionCleanupSystem
    from ..game_systems.save_system import SaveSystem
    from ..game_systems.werewolf_game_initialization_system import (
        WerewolfGameInitializationSystem,
    )
    from ..game_systems.kick_off_system import KickOffSystem
    from ..game_systems.discussion_action_system import DiscussionActionSystem
    from ..game_systems.mind_voice_action_system import MindVoiceActionSystem

    ##
    tcg_game = cast(TCGGame, game)
    processors = TCGGameProcessPipeline("Social Deduction Kickoff Pipeline")

    # 启动agent的提示词。启动阶段
    processors.add(KickOffSystem(tcg_game, False))

    # 社交推理游戏的启动系统，一些必要的上下文同步！
    processors.add(WerewolfGameInitializationSystem(tcg_game))

    # 行为执行阶段
    processors.add(MindVoiceActionSystem(tcg_game))
    processors.add(DiscussionActionSystem(tcg_game))
    processors.add(ActionCleanupSystem(tcg_game))

    # 动作处理后，可能清理。
    processors.add(DestroyEntitySystem(tcg_game))

    # 存储系统。
    processors.add(SaveSystem(tcg_game))

    return processors


###################################################################################################################################################################
def create_werewolf_game_night_pipline(game: BaseGame) -> "TCGGameProcessPipeline":
    ### 不这样就循环引用
    from ..game.tcg_game import TCGGame
    from ..game_systems.destroy_entity_system import DestroyEntitySystem
    from ..game_systems.action_cleanup_system import ActionCleanupSystem
    from ..game_systems.save_system import SaveSystem
    from ..game_systems.night_werewolf_plan_system import (
        NightWerewolfPlanSystem,
    )
    from ..game_systems.night_seer_plan_system import (
        NightSeerPlanSystem,
    )
    from ..game_systems.night_witch_plan_system import (
        NightWitchPlanSystem,
    )
    from ..game_systems.werewolf_victory_condition_system import (
        WerewolfVictoryConditionSystem,
    )
    from ..game_systems.discussion_action_system import DiscussionActionSystem
    from ..game_systems.mind_voice_action_system import MindVoiceActionSystem
    from ..game_systems.night_auto_plan_system import (
        NightAutoPlanSystem,
    )
    from ..game_systems.seer_check_action_system import SeerCheckActionSystem
    from ..game_systems.witch_cure_action_system import WitchCureActionSystem
    from ..game_systems.witch_poison_action_system import WitchPoisonActionSystem

    # from ..game_systems.wolf_kill_action_system import WolfKillActionSystem

    ##
    tcg_game = cast(TCGGame, game)
    processors = TCGGameProcessPipeline("Social Deduction Night Pipeline")

    # 启动agent的提示词。启动阶段
    processors.add(NightAutoPlanSystem(tcg_game))

    # 狼人规划与行动 与 预言家可以进行规划。
    processors.add(NightWerewolfPlanSystem(tcg_game))
    processors.add(NightSeerPlanSystem(tcg_game))
    processors.add(NightWitchPlanSystem(tcg_game))

    # 女巫规划与行动
    processors.add(MindVoiceActionSystem(tcg_game))
    processors.add(DiscussionActionSystem(tcg_game))
    processors.add(SeerCheckActionSystem(tcg_game))
    # processors.add(WolfKillActionSystem(tcg_game))
    processors.add(WitchCureActionSystem(tcg_game))
    processors.add(WitchPoisonActionSystem(tcg_game))

    # 清理动作！必须清理。
    processors.add(ActionCleanupSystem(tcg_game))

    # 结算系统。
    processors.add(WerewolfVictoryConditionSystem(tcg_game))

    # 动作处理后，可能清理。
    processors.add(DestroyEntitySystem(tcg_game))

    # 存储系统。
    processors.add(SaveSystem(tcg_game))

    return processors


###################################################################################################################################################################
def create_werewolf_game_day_pipline(game: BaseGame) -> "TCGGameProcessPipeline":
    ### 不这样就循环引用
    from ..game.tcg_game import TCGGame
    from ..game_systems.destroy_entity_system import DestroyEntitySystem
    from ..game_systems.action_cleanup_system import ActionCleanupSystem
    from ..game_systems.save_system import SaveSystem
    from ..game_systems.werewolf_victory_condition_system import (
        WerewolfVictoryConditionSystem,
    )
    from ..game_systems.discussion_action_system import DiscussionActionSystem
    from ..game_systems.werewolf_day_discussion_system import (
        WerewolfDayDiscussionSystem,
    )
    from ..game_systems.mind_voice_action_system import MindVoiceActionSystem
    from ..game_systems.vote_action_system import VoteActionSystem

    ##
    tcg_game = cast(TCGGame, game)
    processors = TCGGameProcessPipeline("Social Deduction Day Pipeline")

    processors.add(WerewolfDayDiscussionSystem(tcg_game))
    # processors.add(WerewolfDayVoteSystem(tcg_game))

    # # 动作系统。
    processors.add(MindVoiceActionSystem(tcg_game))
    processors.add(DiscussionActionSystem(tcg_game))
    processors.add(VoteActionSystem(tcg_game))
    processors.add(ActionCleanupSystem(tcg_game))

    # 结算系统。
    processors.add(WerewolfVictoryConditionSystem(tcg_game))

    # 动作处理后，可能清理。
    processors.add(DestroyEntitySystem(tcg_game))

    # 存储系统。
    processors.add(SaveSystem(tcg_game))

    return processors


###################################################################################################################################################################
def create_werewolf_game_vote_pipline(game: BaseGame) -> "TCGGameProcessPipeline":
    ### 不这样就循环引用
    from ..game.tcg_game import TCGGame
    from ..game_systems.destroy_entity_system import DestroyEntitySystem
    from ..game_systems.action_cleanup_system import ActionCleanupSystem
    from ..game_systems.save_system import SaveSystem
    from ..game_systems.werewolf_victory_condition_system import (
        WerewolfVictoryConditionSystem,
    )
    from ..game_systems.discussion_action_system import DiscussionActionSystem
    from ..game_systems.werewolf_day_vote_system import (
        WerewolfDayVoteSystem,
    )
    from ..game_systems.mind_voice_action_system import MindVoiceActionSystem
    from ..game_systems.vote_action_system import VoteActionSystem

    ##
    tcg_game = cast(TCGGame, game)
    processors = TCGGameProcessPipeline("Social Deduction Day Pipeline")

    # 投票系统。
    processors.add(WerewolfDayVoteSystem(tcg_game))

    # # 动作系统。
    processors.add(MindVoiceActionSystem(tcg_game))
    processors.add(DiscussionActionSystem(tcg_game))
    processors.add(VoteActionSystem(tcg_game))
    processors.add(ActionCleanupSystem(tcg_game))

    # 结算系统。
    processors.add(WerewolfVictoryConditionSystem(tcg_game))

    # 动作处理后，可能清理。
    processors.add(DestroyEntitySystem(tcg_game))

    # 存储系统。
    processors.add(SaveSystem(tcg_game))

    return processors


###################################################################################################################################################################
class TCGGameProcessPipeline(Processors):

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name: Final[str] = name

    ###################################################################################################################################################################
    async def process(self) -> None:
        # 顺序不要动
        # logger.debug(
        #     f"================= {self._name} process pipeline process ================="
        # )
        await self.execute()
        self.cleanup()

    ###############################################################################################################################################
    def shutdown(self) -> None:
        # logger.debug(
        #     f"================= {self._name} process pipeline shutdown ================="
        # )
        self.tear_down()
        self.clear_reactive_processors()


###################################################################################################################################################################
