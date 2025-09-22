from typing import final
from loguru import logger
from overrides import override
from ..entitas import ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from ..models import (
    ActorComponent,
    HeroComponent,
    PlayerComponent,
    PlanAction,
    HomeComponent,
    MindVoiceAction,
)


###############################################################################################################################################
@final
class HomeAutoPlanSystem(ExecuteProcessor):

    ###############################################################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:

        self._assert_hero_stage_is_home()

        action_entities = self._game.get_group(
            Matcher(all_of=[PlanAction])
        ).entities.copy()
        if len(action_entities) > 0:
            # 已经存在PlanAction，不需要重复生成
            logger.debug("已有PlanAction，跳过自动生成")
            return

        # 获取所有需要进行角色规划的角色
        actor_entities = self._game.get_group(
            Matcher(
                all_of=[ActorComponent, HeroComponent],
                none_of=[PlayerComponent],
            )
        ).entities.copy()

        # 没有需要处理的角色
        if len(actor_entities) == 0:
            return

        # 测试：所有的没有plan的actor都执行一次。
        for actor in actor_entities:
            logger.debug(f"为角色 {actor.name} 生成 PlanAction")
            # 直接创建一个空的PlanAction，等待后续系统填充具体内容
            actor.replace(PlanAction, actor.name)

    ###############################################################################################################################################
    def _assert_hero_stage_is_home(self) -> None:
        actor_entities = self._game.get_group(
            Matcher(
                all_of=[ActorComponent, HeroComponent],
            )
        ).entities.copy()
        for actor_entity in actor_entities:

            # 测试：运行到此处，所有的hero的场景都必须是home！！！
            current_stage_entity = self._game.safe_get_stage_entity(actor_entity)
            assert current_stage_entity is not None
            assert current_stage_entity.has(
                HomeComponent
            ), f"{actor_entity.name} 的场景不是 Home！"

            # 测试：如果角色在家里，且没有心灵语音，则添加一个心灵语音，表示安心修养
            actor_entity.replace(MindVoiceAction, actor_entity.name, "艾尔法尼亚?")

    ###############################################################################################################################################
