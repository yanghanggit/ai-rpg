"""神器实体初始化系统。"""

import uuid
from typing import Final, final

from loguru import logger
from overrides import override

from ..entitas import ExecuteProcessor, Matcher
from ..game.dbg_game import DBGGame
from ..models import (
    ArtifactComponent,
    IdentityComponent,
    ReliquaryComponent,
    SystemMessage,
    resolve_component_type,
)


#######################################################################################################################################
@final
class ArtifactInitializationSystem(ExecuteProcessor):
    """同步神器实体与其持有者声明（幂等，零 LLM）。

    把各持有者（Stage/Actor）`ReliquaryComponent` 中声明的神器物化为独立实体
    （`ArtifactComponent` 承载神器完整定义与持有者 + 运行点组件 + 人设），
    使后续仲裁系统能够像对待普通 agent 一样检索并驱动神器。

    幂等：已物化（或从快照还原）的神器会被跳过，可安全地在每帧执行。
    孤立神器的回收不在此处：战斗结束由 `CombatArtifactCleanupSystem` 处理，
    副本销毁由 `teardown_dungeon` 处理。
    """

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    #######################################################################################################################################
    @override
    async def execute(self) -> None:
        self._create_artifact_entities()

    #######################################################################################################################################
    def _create_artifact_entities(self) -> None:
        """把 ReliquaryComponent 中声明的神器物化为独立实体（已存在则跳过）。"""

        # 扫描所有携带 ReliquaryComponent 的实体（Stage / Actor）
        holder_entities = self._game.get_group(
            Matcher(all_of=[ReliquaryComponent])
        ).entities

        for holder_entity in holder_entities:
            reliquary = holder_entity.get(ReliquaryComponent)
            for artifact in reliquary.artifacts:

                # 幂等：已物化的神器（或从快照还原）跳过
                if self._game.get_entity_by_name(artifact.name) is not None:
                    continue

                # 创建实体
                artifact_entity = self._game._create_entity(artifact.name)
                assert artifact_entity is not None, f"创建神器实体失败: {artifact.name}"

                # 必要组件：identifier
                self._game._world.entity_counter += 1
                artifact_entity.add(
                    IdentityComponent,
                    artifact.name,
                    self._game._world.entity_counter,
                    str(uuid.uuid4()),
                )

                # 必要组件：标记为神器，记录持有者，并承载神器完整定义
                artifact_entity.add(
                    ArtifactComponent, artifact.name, holder_entity.name, artifact
                )

                # 必要组件：系统消息（神器人设即其 agent 的设定）
                assert (
                    artifact.name in artifact.system_message
                ), f"artifact.system_message 缺少 {artifact.name} 的系统消息"
                self._game.add_system_message(
                    artifact_entity,
                    SystemMessage(content=artifact.system_message),
                )

                # 特殊组件，根据 artifact.components 数据驱动动态添加
                for comp_serialization in artifact.components:
                    comp_class = resolve_component_type(
                        comp_serialization.name, comp_serialization.data
                    )
                    restore_comp = comp_class(**comp_serialization.data)
                    logger.debug(
                        f"为 Artifact 实体 {artifact_entity.name} 添加 {comp_serialization.name}"
                    )
                    artifact_entity.set(comp_class, restore_comp)
