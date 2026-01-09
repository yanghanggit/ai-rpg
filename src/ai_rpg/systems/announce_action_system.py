from typing import Set, final, override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import AnnounceAction, AnnounceEvent, HomeComponent, DungeonComponent
from ..game.tcg_game import TCGGame


####################################################################################################################################
def _format_announce_notification(
    announcer_name: str, announcement_message: str
) -> str:
    return f"""# 通知！{announcer_name} 发布公告: {announcement_message}"""


####################################################################################################################################


@final
class AnnounceActionSystem(ReactiveProcessor):
    """角色公告动作系统。

    响应式处理器，监听 AnnounceAction 组件触发，根据发起者所在场景类型
    将公告消息广播到所有同类型的场景（家园或地下城）。

    功能特点：
    - 自动识别发起者所在场景类型（HomeComponent 或 DungeonComponent）
    - 获取所有同类型的场景实体
    - 向每个同类型场景广播 AnnounceEvent
    - 确保消息传达到所有相关区域的角色

    广播范围：所有同类型场景内的所有角色（跨场景）

    广播规则：
    - 家园场景发起 → 广播到所有家园场景
    - 地下城场景发起 → 广播到所有地下城场景
    - 不支持跨场景类型的公告广播

    与其他交流系统的区别：
    - Speak: 当前场景所有角色（单场景公开）
    - Whisper: 发起者和目标双方（单场景私密）
    - Announce: 所有同类型场景的所有角色（跨场景公开）

    Attributes:
        _game: 游戏实例引用
    """

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: TCGGame = game_context

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(AnnounceAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(AnnounceAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_announce_action(entity)

    ####################################################################################################################################
    def _get_stage_entities_by_type(self, current_stage_entity: Entity) -> Set[Entity]:
        """根据当前场景类型获取所有同类型的场景实体。

        该方法根据当前场景的类型（家园或地下城），查询并返回所有相同类型的场景实体集合，
        用于确定公告的广播范围。

        Args:
            current_stage_entity: 当前场景实体，用于判断场景类型

        Returns:
            Set[Entity]: 所有同类型场景实体的集合

        Raises:
            AssertionError: 当场景类型未知（既不是家园也不是地下城）时抛出

        Note:
            - 家园场景：返回所有具有 HomeComponent 的场景实体
            - 地下城场景：返回所有具有 DungeonComponent 的场景实体
            - 这确保了公告只在相同类型的场景中广播
        """
        stage_entities: Set[Entity] = set()

        # 根据当前场景类型，选择相应的广播范围
        if current_stage_entity.has(HomeComponent):
            stage_entities = self._game.get_group(
                Matcher(
                    all_of=[
                        HomeComponent,
                    ],
                )
            ).entities.copy()

        elif current_stage_entity.has(DungeonComponent):
            stage_entities = self._game.get_group(
                Matcher(
                    all_of=[
                        DungeonComponent,
                    ],
                )
            ).entities.copy()
        else:
            assert False, "未知的场景类型，无法广播公告。"

        return stage_entities

    ####################################################################################################################################
    def _process_announce_action(self, entity: Entity) -> None:
        """处理实体的公告动作。

        该方法负责处理角色的公告动作，将公告消息广播到所有同类型的场景中。
        根据发起者当前所在场景的类型（家园或地下城），获取所有相同类型的场景实体，
        然后向每个场景广播公告事件，确保消息传达到所有相关区域。

        处理流程：
        1. 获取发起者当前所在的场景实体
        2. 根据场景类型获取所有同类型的场景实体集合
        3. 从实体中提取 AnnounceAction 组件
        4. 遍历所有同类型的场景实体
        5. 向每个场景广播 AnnounceEvent 事件

        Args:
            entity: 包含 AnnounceAction 组件的游戏实体，代表发起公告的角色

        Returns:
            None

        Raises:
            AssertionError: 当前场景实体为空或 AnnounceAction 组件为空时抛出

        Note:
            - 公告仅在同类型场景间广播（家园→家园，地下城→地下城）
            - 使用 broadcast_to_stage 确保场景内所有角色都能收到公告
            - 每个场景都会收到一个独立的 AnnounceEvent 实例
            - 公告消息通过 _format_announce_notification 格式化
            - 这是一个全场景广播机制，与单个场景的 SpeakAction 不同
        """
        # 获取当前场景实体
        current_stage_entity = self._game.resolve_stage_entity(entity)
        assert current_stage_entity is not None

        # 获取所有同类型的场景实体
        matching_stage_entities = self._get_stage_entities_by_type(current_stage_entity)

        # 广播事件
        announce_action = entity.get(AnnounceAction)
        assert announce_action is not None

        for stage_entity in matching_stage_entities:

            # 广播每个同类型的stage
            self._game.broadcast_to_stage(
                stage_entity,
                AnnounceEvent(
                    message=_format_announce_notification(
                        entity.name,
                        announce_action.message,
                    ),
                    actor=entity.name,
                    stage=stage_entity.name,
                    content=announce_action.message,
                ),
            )

    ####################################################################################################################################
