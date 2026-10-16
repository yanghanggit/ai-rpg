"""副本生成流程管道工厂模块。"""

from typing import cast

from .base_game import BaseGame
from .rpg_game_pipeline_manager import RPGGameProcessPipeline


def create_dungeon_generate_pipeline(
    game: BaseGame,
) -> RPGGameProcessPipeline:
    """创建副本生成流程管道（LLM 文本生成 + 图片生成）"""

    ### 不这样就循环引用
    from ..systems.action_cleanup_system import ActionCleanupSystem
    from ..systems.assemble_dungeon_deck_system import AssembleDungeonDeckSystem
    from ..systems.assemble_dungeon_system import AssembleDungeonSystem
    from ..systems.context_compaction_system import ContextCompactionSystem
    from ..systems.destroy_entity_system import DestroyEntitySystem
    from ..systems.dungeon_generation_cleanup_system import (
        DungeonGenerationCleanupSystem,
    )
    from ..systems.epilogue_system import EpilogueSystem
    from ..systems.generate_dungeon_actors_system import GenerateDungeonActorsSystem
    from ..systems.generate_dungeon_directive_system import (
        GenerateDungeonDirectiveSystem,
    )
    from ..systems.generate_dungeon_profile_system import GenerateDungeonProfileSystem
    from ..systems.generate_dungeon_rooms_system import GenerateDungeonRoomsSystem
    from ..systems.illustrate_dungeon_system import IllustrateDungeonSystem
    from ..systems.prologue_system import PrologueSystem
    from .dbg_game import DBGGame

    dbg_game = cast(DBGGame, game)
    processors = RPGGameProcessPipeline()

    processors.add(PrologueSystem(dbg_game))

    processors.add(GenerateDungeonDirectiveSystem(dbg_game))
    processors.add(GenerateDungeonProfileSystem(dbg_game))
    processors.add(GenerateDungeonRoomsSystem(dbg_game))
    processors.add(GenerateDungeonActorsSystem(dbg_game))
    processors.add(AssembleDungeonSystem(dbg_game))
    processors.add(AssembleDungeonDeckSystem(dbg_game))
    processors.add(IllustrateDungeonSystem(dbg_game))

    processors.add(DungeonGenerationCleanupSystem(dbg_game))

    processors.add(ActionCleanupSystem(dbg_game))
    processors.add(DestroyEntitySystem(dbg_game))
    processors.add(ContextCompactionSystem(dbg_game))
    processors.add(EpilogueSystem(dbg_game))

    return processors
