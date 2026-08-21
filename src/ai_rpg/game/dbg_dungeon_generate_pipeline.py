"""副本生成流程管道工厂模块。"""

from typing import cast
from .game_session import GameSession
from .rpg_game_pipeline_manager import RPGGameProcessPipeline


def create_dungeon_generate_pipeline(
    game: GameSession,
) -> RPGGameProcessPipeline:
    """创建副本生成流程管道（LLM 文本生成 + 图片生成）"""

    ### 不这样就循环引用
    from .dbg_game import DBGGame
    from ..systems.generate_dungeon_directive_system import (
        GenerateDungeonDirectiveSystem,
    )
    from ..systems.generate_dungeon_profile_system import GenerateDungeonProfileSystem
    from ..systems.generate_dungeon_rooms_system import GenerateDungeonRoomsSystem
    from ..systems.generate_dungeon_actors_system import GenerateDungeonActorsSystem
    from ..systems.assemble_dungeon_system import AssembleDungeonSystem

    # from ..systems.illustrate_dungeon_action_system import IllustrateDungeonActionSystem
    from ..systems.epilogue_system import EpilogueSystem
    from ..systems.prologue_system import PrologueSystem
    from ..systems.action_cleanup_system import ActionCleanupSystem
    from ..systems.destroy_entity_system import DestroyEntitySystem

    dbg_game = cast(DBGGame, game)
    processors = RPGGameProcessPipeline()

    # 起始系统
    processors.add(PrologueSystem(dbg_game))

    # 副本生成流程（Steps 0-4，在同一次 pipeline.process() 内顺序触发）
    processors.add(GenerateDungeonDirectiveSystem(dbg_game))  # Step 0: 世界导演创作指令
    processors.add(GenerateDungeonProfileSystem(dbg_game))  # Step 1: 副本设定生成
    processors.add(GenerateDungeonRoomsSystem(dbg_game))  # Step 2: 房间批量生成
    processors.add(GenerateDungeonActorsSystem(dbg_game))  # Step 3: 怪物并发生成
    processors.add(AssembleDungeonSystem(dbg_game))  # Step 4: 实体树组装

    # 副本图片生成系统（Step 5）
    # processors.add(IllustrateDungeonActionSystem(dbg_game))

    # 清除动作相关的临时状态、标记等，准备下一轮输入
    processors.add(ActionCleanupSystem(dbg_game))

    # 动作处理后，可能清理。
    processors.add(DestroyEntitySystem(dbg_game))

    # 收尾系统
    processors.add(EpilogueSystem(dbg_game))

    return processors
