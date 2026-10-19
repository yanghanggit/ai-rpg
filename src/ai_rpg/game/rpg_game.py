from typing import Final, Set

from loguru import logger
from overrides import override

from ..entitas import Entity
from ..models import (
    AnyAgentEvent,
    HumanMessage,
    PlayerSession,
    WorldState,
)
from .base_game import BaseGame
from .rpg_agent_memory import RPGAgentMemory
from .rpg_entity_manager import RPGEntityManager
from .rpg_game_pipeline_manager import RPGGamePipelineManager


#################################################################################################################################################
class RPGGame(BaseGame, RPGAgentMemory, RPGEntityManager, RPGGamePipelineManager):
    """
    RPG游戏核心类，基于ECS架构整合游戏会话管理、实体管理和LLM处理管道
    """

    def __init__(
        self,
        name: str,
        player_session: PlayerSession,
        world: WorldState,
    ) -> None:

        # 必须按着此顺序实现父类
        BaseGame.__init__(self, name)  # 需要传递 name
        RPGEntityManager.__init__(self)  # 继承 Context, 需要调用其 __init__
        RPGGamePipelineManager.__init__(self)  # 管道管理器初始化

        # 初始化player_session 和 world
        self._player_session: Final[PlayerSession] = player_session
        self._world: WorldState = world

        # 验证玩家信息
        assert self._player_session.name != "", "玩家名字不能为空"
        assert self._player_session.actor != "", "玩家角色不能为空"

    ###############################################################################################################################################
    @override
    def destroy_entity(self, entity: Entity) -> None:
        """销毁实体并清理其LLM记忆"""
        logger.debug(f"destroy_entity: {entity.name}")
        self.remove_agent_memory(entity)
        return super().destroy_entity(entity)

    ###############################################################################################################################################
    @override
    def exit(self) -> None:
        logger.debug("Exiting game, performing cleanup...")
        # 关闭所有管道
        self.shutdown_pipelines()

    ###############################################################################################################################################
    @override
    async def initialize(self) -> None:
        logger.debug("Initializing game, setting up pipelines and world state...")
        # 初始化所有管道
        await self.initialize_pipelines()

    ###############################################################################################################################################
    def restore_from_snapshot(self) -> "RPGGame":
        """从序列化数据中恢复游戏世界状态"""
        assert len(self._world.entities) > 0, "游戏中没有实体，不能恢复游戏"
        assert len(self._entities) == 0, "游戏中有实体，不能恢复游戏"
        if (len(self._world.entities) == 0) or (len(self._entities) > 0):
            logger.warning(
                f"游戏中没有实体，不能恢复游戏，entities = {self._world.entities}, entities = {self._entities}"
            )
            return self

        # 从序列化数据中恢复实体状态
        self.restore_context(self._world.entities)
        return self

    ###############################################################################################################################################
    def flush_entities(self) -> "RPGGame":
        """保存当前游戏世界状态到持久化存储，并生成调试快照"""
        # 生成快照
        assert len(self._entities) > 0, "游戏中没有实体，不能生成快照"
        self._world.entities = self.serialize_context()
        return self

    ###############################################################################################################################################
    def broadcast_to_stage(
        self,
        entity: Entity,
        agent_event: AnyAgentEvent,
        exclude_entities: Set[Entity] = set(),
    ) -> None:
        """向场景内所有角色与场景实体广播事件。

        actor 与 stage 不可分离，找不到场景是数据损坏，故断言而非降级。
        消息除内容外盖两个标记，供记忆审计区分“广播”与“私有说明”：
        `agent_event`（事件类型）、`broadcast_stage`（广播所属场景）。

        自我回显（exclude_entities）的统一口径：
        - 行动类广播：发起者另有更精确的自我记录时排除发起者；
        - 观察类广播：发起者对事件**没有**其他记录时保留（过牌、装备/消耗品物化、
          说话、外观更新、仲裁结果）——自己也是当事人，需要这条消息作为唯一凭据。
        """
        stage_entity = self.resolve_stage_entity(entity)
        assert stage_entity is not None, f"{entity.name} 无所在场景，无法广播"

        targets = (self.get_actors_in_stage(stage_entity) | {stage_entity}) - (
            exclude_entities
        )
        for target in targets:
            self.add_human_message(
                target,
                HumanMessage(
                    content=agent_event.message,
                    agent_event=agent_event.type,
                    broadcast_stage=stage_entity.name,
                ),
            )

        self._player_session.add_agent_event(agent_event=agent_event)

    ###############################################################################################################################################
    def notify_entities(
        self,
        entities: Set[Entity],
        agent_event: AnyAgentEvent,
    ) -> None:
        """向指定实体私发事件消息（只盖 `agent_event`，不盖广播范围），并同步到玩家客户端。"""

        for entity in entities:
            self.add_human_message(
                entity,
                HumanMessage(
                    content=agent_event.message,
                    agent_event=agent_event.type,
                ),
            )

        # 最后都要发给客户端。
        self._player_session.add_agent_event(agent_event=agent_event)

    #######################################################################################################################################
