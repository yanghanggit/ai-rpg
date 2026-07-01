from typing import final, override, Dict, List
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import AnnounceAction, AnnounceEvent, HomeComponent
from ..game.dbg_game import DBGGame


####################################################################################################################################
def _format_local_announce(announcer_name: str, content: str) -> str:
    """公告者所在场景内的公告提示词格式。"""
    return f"# {announcer_name} 发布公告\n{content}"


####################################################################################################################################
def _format_remote_announce(source_stage_name: str, content: str) -> str:
    """其他场景收到的远端公告提示词格式。"""
    return f"# 来自「{source_stage_name}」的公告\n{content}"


####################################################################################################################################


@final
class AnnounceActionSystem(ReactiveProcessor):
    """角色公告动作系统。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: DBGGame = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(AnnounceAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(AnnounceAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        for entity in entities:
            self._process_announce_action(entity)

    ####################################################################################################################################
    def _process_announce_action(self, entity: Entity) -> None:
        """处理实体的公告动作。"""
        # 获取当前场景实体
        current_stage_entity = self._game.resolve_stage_entity(entity)
        assert (
            current_stage_entity is not None
        ), "无法解析实体所在的场景，无法处理公告动作。"

        assert current_stage_entity.has(
            HomeComponent
        ), "目前仅支持在家园场景发布公告，其他场景类型暂不处理"
        if not current_stage_entity.has(HomeComponent):
            return  # 目前仅支持在家园场景发布公告，其他场景类型暂不处理

        # 广播事件
        announce_action = entity.get(AnnounceAction)
        assert (
            announce_action is not None
        ), "实体缺少 AnnounceAction 组件，无法处理公告动作。"

        # 获取所有家园场景实体
        home_stage_entities = self._game.get_group(
            Matcher(
                all_of=[
                    HomeComponent,
                ],
            )
        ).entities.copy()

        # 广播公告事件给所有家园场景的玩家
        for stage_entity in home_stage_entities:
            is_local = stage_entity is current_stage_entity
            if is_local:
                # 公告者所在场景：显示角色名 + 公告内容
                formatted_message = _format_local_announce(
                    entity.name, announce_action.message
                )
            else:
                # 其他场景：显示公告来源场景名 + 公告内容
                formatted_message = _format_remote_announce(
                    current_stage_entity.name, announce_action.message
                )

            self._game.broadcast_to_stage(
                stage_entity,
                AnnounceEvent(
                    message=formatted_message,
                    actor=entity.name,
                    stage=stage_entity.name,
                    content=announce_action.message,
                ),
            )

    ####################################################################################################################################
