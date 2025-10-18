from typing import cast
from .game_session import GameSession
from .rpg_game_pipeline_manager import RPGGameProcessPipeline


def create_werewolf_game_kickoff_pipline(game: GameSession) -> "RPGGameProcessPipeline":
    ### 不这样就循环引用
    from ..game.sd_game import SDGame
    from ..game_systems.destroy_entity_system import DestroyEntitySystem
    from ..game_systems.action_cleanup_system import ActionCleanupSystem
    from ..game_systems.save_system import SaveSystem
    from ..game_systems.werewolf_game_initialization_system import (
        WerewolfGameInitializationSystem,
    )
    from ..game_systems.kick_off_system import KickOffSystem
    from ..game_systems.discussion_action_system import DiscussionActionSystem

    ##
    tcg_game = cast(SDGame, game)
    processors = RPGGameProcessPipeline("Social Deduction Kickoff Pipeline")

    # 启动agent的提示词。启动阶段
    processors.add(KickOffSystem(tcg_game, True))

    # 社交推理游戏的启动系统，一些必要的上下文同步！
    processors.add(WerewolfGameInitializationSystem(tcg_game))

    # 行为执行阶段
    processors.add(DiscussionActionSystem(tcg_game))
    processors.add(ActionCleanupSystem(tcg_game))

    # 动作处理后，可能清理。
    processors.add(DestroyEntitySystem(tcg_game))

    # 存储系统。
    processors.add(SaveSystem(tcg_game))

    return processors


###################################################################################################################################################################
def create_werewolf_game_night_pipline(game: GameSession) -> "RPGGameProcessPipeline":
    ### 不这样就循环引用
    from ..game.sd_game import SDGame
    from ..game_systems.destroy_entity_system import DestroyEntitySystem
    from ..game_systems.action_cleanup_system import ActionCleanupSystem
    from ..game_systems.save_system import SaveSystem
    from ..game_systems.night_werewolf_action_system import (
        NightWerewolfActionSystem,
    )
    from ..game_systems.night_seer_action_system import (
        NightSeerActionSystem,
    )
    from ..game_systems.night_witch_action_system import (
        NightWitchActionSystem,
    )
    from ..game_systems.werewolf_victory_condition_system import (
        WerewolfVictoryConditionSystem,
    )
    from ..game_systems.discussion_action_system import DiscussionActionSystem

    from ..game_systems.night_action_initialization_system import (
        NightActionInitializationSystem,
    )
    from ..game_systems.seer_check_action_system import SeerCheckActionSystem
    from ..game_systems.witch_cure_action_system import WitchCureActionSystem
    from ..game_systems.witch_poison_action_system import WitchPoisonActionSystem

    # from ..game_systems.wolf_kill_action_system import WolfKillActionSystem

    ##
    tcg_game = cast(SDGame, game)
    processors = RPGGameProcessPipeline("Social Deduction Night Pipeline")

    # 启动agent的提示词。启动阶段
    processors.add(NightActionInitializationSystem(tcg_game))

    # 狼人规划与行动 与 预言家可以进行规划。
    processors.add(NightWerewolfActionSystem(tcg_game))
    processors.add(NightSeerActionSystem(tcg_game))
    processors.add(NightWitchActionSystem(tcg_game))

    # 女巫规划与行动
    processors.add(DiscussionActionSystem(tcg_game))
    processors.add(SeerCheckActionSystem(tcg_game))
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
def create_werewolf_game_day_pipline(game: GameSession) -> "RPGGameProcessPipeline":
    ### 不这样就循环引用
    from ..game.sd_game import SDGame
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

    ##
    tcg_game = cast(SDGame, game)
    processors = RPGGameProcessPipeline("Social Deduction Day Pipeline")

    processors.add(WerewolfDayDiscussionSystem(tcg_game))

    # # 动作系统。
    processors.add(DiscussionActionSystem(tcg_game))
    processors.add(ActionCleanupSystem(tcg_game))

    # 结算系统。
    processors.add(WerewolfVictoryConditionSystem(tcg_game))

    # 动作处理后，可能清理。
    processors.add(DestroyEntitySystem(tcg_game))

    # 存储系统。
    processors.add(SaveSystem(tcg_game))

    return processors


###################################################################################################################################################################
def create_werewolf_game_vote_pipline(game: GameSession) -> "RPGGameProcessPipeline":
    ### 不这样就循环引用
    from ..game.sd_game import SDGame
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

    from ..game_systems.vote_action_system import VoteActionSystem

    ##
    tcg_game = cast(SDGame, game)
    processors = RPGGameProcessPipeline("Social Deduction Day Pipeline")

    # 投票系统。
    processors.add(WerewolfDayVoteSystem(tcg_game))

    # # 动作系统。
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
