"""
HomeAutoPlanSystem - 家中盟友自动计划生成系统

该系统负责为在家(HomeComponent)的盟友角色自动生成初始行动计划。
系统会筛选符合条件的角色并为其创建 PlanAction，等待后续系统填充具体内容。

工作流程:
1. 检查游戏中是否已存在 PlanAction，避免重复生成
2. 筛选符合条件的盟友角色（必须有 AllyComponent + KickOffDoneComponent，且无 PlayerComponent）
3. 验证角色所在场景是否带有 HomeComponent
4. 为符合所有条件的角色创建空的 PlanAction
"""

from typing import final
from loguru import logger
from overrides import override
from ..entitas import ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from ..models import (
    ActorComponent,
    AllyComponent,
    PlayerComponent,
    PlanAction,
    KickOffDoneComponent,
    HomeComponent,
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
        """
        执行系统的主要逻辑。

        功能说明:
        - 检查游戏中是否已有 PlanAction，如有则跳过生成（避免重复）
        - 获取所有符合条件的盟友角色（AllyComponent + KickOffDoneComponent - PlayerComponent）
        - 遍历这些角色，验证其是否位于带有 HomeComponent 的场景中
        - 为满足所有条件的角色创建空白 PlanAction，等待后续系统填充具体行动内容

        Returns:
            None
        """

        # 检查是否已经存在PlanAction
        existing_plan_actions = self._game.get_group(
            Matcher(all_of=[PlanAction])
        ).entities.copy()

        if len(existing_plan_actions) > 0:
            # 已经存在PlanAction，不需要重复生成
            logger.debug("已有PlanAction，跳过自动生成")
            return

        # 获取所有需要进行角色规划的角色
        planning_actors = self._game.get_group(
            Matcher(
                all_of=[ActorComponent, AllyComponent, KickOffDoneComponent],
                none_of=[PlayerComponent],
            )
        ).entities.copy()

        # 测试：所有的没有plan的actor都执行一次。
        for actor in planning_actors:

            stage_entity = self._game.safe_get_stage_entity(actor)
            assert stage_entity is not None, "角色必须在某个场景中！"
            if not stage_entity.has(HomeComponent):
                # 仅处理在家的角色
                continue

            logger.debug(f"为角色 {actor.name} 生成 PlanAction")
            # 直接创建一个空的PlanAction，等待后续系统填充具体内容
            actor.replace(PlanAction, actor.name)

    ###############################################################################################################################################
