from typing import Final, final, override
from loguru import logger
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    WorldComponent,
    DungeonGenerationComponent,
    SetupDungeonAction,
)
from ..game.tcg_game import TCGGame


####################################################################################################################################
@final
class DungeonGenerationSystem(ReactiveProcessor):
    """地下城图片生成系统。

    反应式处理器，监听实体上 SetupDungeonAction 的添加事件，
    执行地下城的完整创建流程（文生图、数据初始化等）。

    工作流程：
        1. 监听实体上 SetupDungeonAction 动作组件的添加事件
        2. 获取地下城生成世界系统实体（包含 DungeonGenerationComponent）
        3. 依次执行地下城创建子任务（文生图、数据初始化等）
        4. 由 ActionCleanupSystem 自动清除 SetupDungeonAction

    Attributes:
        _game: 游戏实例引用

    Note:
        - SetupDungeonAction 由 home_actions.activate_setup_dungeon() 在家园状态下添加
        - 具体创建逻辑待后续填充，当前为骨架占位
    """

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        # 监听 SetupDungeonAction 的添加事件
        return {
            Matcher(SetupDungeonAction): GroupEvent.ADDED,
        }

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(SetupDungeonAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:

        # 获取地下城生成世界系统实体
        world_system_entities = self._game.get_group(
            Matcher(all_of=[WorldComponent, DungeonGenerationComponent])
        ).entities.copy()

        if not world_system_entities:
            logger.error("未找到地下城生成系统实体，无法执行地下城创建流程")
            return

        assert len(world_system_entities) == 1, "存在多个地下城生成系统实体，数据异常"
        world_system_entity = next(iter(world_system_entities))

        for entity in entities:
            await self._setup_dungeon(entity, world_system_entity)

    ####################################################################################################################################
    async def _setup_dungeon(self, entity: Entity, world_system_entity: Entity) -> None:
        """执行地下城创建流程。

        Args:
            entity: 携带 SetupDungeonAction 的实体（玩家实体）
            world_system_entity: 地下城生成世界系统实体

        Note:
            TODO: 实现地下城创建逻辑
                1. 从 current_dungeon 提取地下城/房间描述
                2. 通过 world_system_entity 的 AI 上下文将描述转化为英文图片提示词
                3. 调用 image_client 文生图 API 生成封面及各房间图片
                4. 将生成结果写入 Dungeon/DungeonRoom 的 GeneratedImage 字段
                5. 执行其他地下城初始化子任务（如有）
                6. SetupDungeonAction 由 ActionCleanupSystem 自动清除
        """
        logger.info(
            f"[DungeonGenerationSystem] 收到地下城创建请求: entity={entity.name}, "
            f"world_system={world_system_entity.name} — TODO: 地下城创建逻辑待实现"
        )

    ####################################################################################################################################
