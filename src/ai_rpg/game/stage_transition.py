"""场景转换核心逻辑模块。

提供场景转换的完整流程函数，包括前置条件验证、离开/进入通知广播和角色归属更新。
作为模块级函数供 systems 和 services 层直接调用。
"""

from typing import Set
from loguru import logger
from ..entitas import Entity
from ..models import (
    ActorComponent,
    AgentEvent,
    PlayerComponent,
    PlayerOnlyStageComponent,
    TransStageEvent,
)
from .rpg_game import RPGGame


#################################################################################################################################################
def _format_stage_departure_message(actor_name: str, stage_name: str) -> str:
    """生成角色离开场景的通知消息"""
    return f"# {actor_name} 离开了场景: {stage_name}"


#################################################################################################################################################
def _format_stage_arrival_message(actor_name: str, stage_name: str) -> str:
    """生成角色进入场景的通知消息"""
    return f"# {actor_name} 进入了 场景: {stage_name}"


#################################################################################################################################################
def _format_stage_transition_message(from_stage_name: str, to_stage_name: str) -> str:
    """生成角色自身场景转换的通知消息"""
    return f"# 你从 场景: {from_stage_name} 离开，然后进入了 场景: {to_stage_name}"


#################################################################################################################################################
def _validate_stage_transition_prerequisites(
    game: RPGGame, actors: Set[Entity], stage_destination: Entity
) -> Set[Entity]:
    """验证场景传送的前置条件并过滤有效的角色

    Args:
        game: RPG 游戏实例
        actors: 需要传送的角色集合
        stage_destination: 目标场景

    Returns:
        Set[Entity]: 需要实际传送的角色集合（排除已在目标场景的角色）
    """
    # 验证所有角色都有ActorComponent
    for actor in actors:
        assert actor.has(ActorComponent), f"角色 {actor.name} 缺少 ActorComponent"

    # 过滤掉已经在目标场景的角色
    actors_to_transfer: Set[Entity] = set()
    for actor_entity in actors:
        current_stage = game.resolve_stage_entity(actor_entity)
        assert current_stage is not None, f"角色 {actor_entity.name} 没有当前场景"

        if current_stage == stage_destination:
            logger.warning(f"{actor_entity.name} 已经存在于 {stage_destination.name}")
            continue

        actors_to_transfer.add(actor_entity)

    return actors_to_transfer


#################################################################################################################################################
def _broadcast_departure_notifications(game: RPGGame, actors: Set[Entity]) -> None:
    """处理角色离开场景的通知

    Args:
        game: RPG 游戏实例
        actors: 要离开的角色集合
    """
    for actor_entity in actors:
        current_stage = game.resolve_stage_entity(actor_entity)
        assert current_stage is not None

        # 向所在场景及所在场景内除自身外的其他人宣布，这货要离开了
        game.broadcast_to_stage(
            entity=current_stage,
            agent_event=AgentEvent(
                message=_format_stage_departure_message(
                    actor_entity.name, current_stage.name
                ),
            ),
            exclude_entities={actor_entity},
        )


#################################################################################################################################################
def _update_actors_stage_membership(
    game: RPGGame, actors: Set[Entity], stage_destination: Entity
) -> None:
    """执行角色的场景传送，包括更新场景归属和行动队列

    Args:
        game: RPG 游戏实例
        actors: 要传送的角色集合
        stage_destination: 目标场景
    """
    for actor_entity in actors:
        current_stage = game.resolve_stage_entity(actor_entity)
        assert current_stage is not None, "角色没有当前场景"
        assert current_stage != stage_destination, "不应该传送到当前场景"

        actor_comp = actor_entity.get(ActorComponent)
        assert actor_comp is not None, "actor_comp is None"

        # 更改所处场景的标识
        actor_entity.replace(
            ActorComponent,
            actor_comp.name,
            actor_comp.character_sheet_name,
            stage_destination.name,
        )

        # 通知角色自身的传送过程
        game.notify_entities(
            entities={actor_entity},
            agent_event=TransStageEvent(
                message=_format_stage_transition_message(
                    current_stage.name, stage_destination.name
                ),
                actor=actor_entity.name,
                from_stage=current_stage.name,
                to_stage=stage_destination.name,
            ),
        )


#################################################################################################################################################
def _broadcast_arrival_notifications(
    game: RPGGame, actors: Set[Entity], stage_destination: Entity
) -> None:
    """处理角色进入场景的通知

    Args:
        game: RPG 游戏实例
        actors: 进入的角色集合
        stage_destination: 目标场景
    """
    for actor_entity in actors:
        # 向所在场景及所在场景内除自身外的其他人宣布，这货到了
        game.broadcast_to_stage(
            entity=stage_destination,
            agent_event=AgentEvent(
                message=_format_stage_arrival_message(
                    actor_entity.name, stage_destination.name
                ),
            ),
            exclude_entities={actor_entity},
        )


#################################################################################################################################################
def stage_transition(
    game: RPGGame, actors: Set[Entity], stage_destination: Entity
) -> None:
    """处理角色在场景间的转换，包括访问控制、通知广播

    Args:
        game: RPG 游戏实例
        actors: 需要传送的角色集合
        stage_destination: 目标场景
    """
    # 0. 访问控制：PlayerOnlyStage 只允许玩家进入
    if stage_destination.has(PlayerOnlyStageComponent):
        for actor in actors:
            assert actor.has(PlayerComponent), (
                f"角色 {actor.name} 试图进入仅玩家场景 {stage_destination.name}，"
                "但该角色不是玩家！这是程序逻辑错误。"
            )

    # 1. 验证前置条件并过滤有效角色
    actors_to_transfer = _validate_stage_transition_prerequisites(
        game, actors, stage_destination
    )

    # 如果没有角色需要传送，直接返回
    if not actors_to_transfer:
        return

    # 2. 处理角色离开场景
    _broadcast_departure_notifications(game, actors_to_transfer)

    # 3. 执行场景传送
    _update_actors_stage_membership(game, actors_to_transfer, stage_destination)

    # 4. 处理角色进入场景
    _broadcast_arrival_notifications(game, actors_to_transfer, stage_destination)


#################################################################################################################################################
