"""实体销毁系统模块。

该模块实现了游戏中的实体销毁系统，负责在每个游戏循环中检测并销毁所有标记为待销毁的实体。
当实体被添加 DestroyComponent 组件时，该系统会在执行阶段自动将其从游戏世界中移除。

主要功能：
- 检测所有包含 DestroyComponent 的实体
- 按顺序销毁这些实体
- 记录销毁操作的日志信息
- 确保实体从游戏上下文中完全移除

销毁机制：
- 该系统作为 ExecuteProcessor 在每个游戏循环的执行阶段运行
- 使用 DestroyComponent 作为销毁标记
- 通过 game.destroy_entity() 执行实际的实体销毁操作
- 使用 pop() 方法逐个处理待销毁实体，确保销毁过程的安全性

使用场景：
- 角色死亡后的清理
- 临时对象的生命周期管理
- 场景切换时的实体清理
- 任何需要从游戏世界中移除实体的场景

Note:
    实体一旦被销毁，将无法恢复。销毁操作应该是游戏逻辑的最后步骤。
"""

from typing import final, override
from loguru import logger
from ..entitas import ExecuteProcessor, Matcher
from ..game.rpg_game import RPGGame
from ..models import DestroyComponent


@final
class DestroyEntitySystem(ExecuteProcessor):

    def __init__(self, game_context: RPGGame) -> None:
        self._game: RPGGame = game_context

    ####################################################################################################################################
    @override
    async def execute(self) -> None:
        """执行实体销毁操作。

        该方法在每个游戏循环中被调用，负责查找并销毁所有标记为待销毁的实体。
        它会获取所有包含 DestroyComponent 的实体，然后逐个从游戏上下文中移除这些实体。

        处理流程：
        1. 查询所有包含 DestroyComponent 的实体
        2. 复制实体集合以避免迭代过程中的修改冲突
        3. 使用 while 循环和 pop() 方法逐个处理实体
        4. 调用 game.destroy_entity() 执行实际的销毁操作
        5. 记录每个被销毁实体的调试日志

        Returns:
            None

        Note:
            - 使用 entities.copy() 创建实体集合的副本，避免在迭代中修改集合
            - 使用 pop() 方法可以在销毁过程中安全地修改集合
            - 销毁操作是不可逆的，实体一旦销毁将无法恢复
            - 日志级别为 debug，用于追踪实体的销毁过程
            - 该方法是异步的，允许在销毁过程中执行其他异步操作
        """
        destroyable_entities = self._game.get_group(
            Matcher(DestroyComponent)
        ).entities.copy()
        while len(destroyable_entities) > 0:
            destory_entity = destroyable_entities.pop()
            self._game.destroy_entity(destory_entity)
            logger.debug(f"Destroy entity: {destory_entity.name}")

    ####################################################################################################################################
