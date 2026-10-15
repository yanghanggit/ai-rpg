"""场景环境叙事读取模块。

环境叙事（EnvironmentComponent.narrative）由 EnvironmentInitializationSystem 尽力生成，
对下游只是「便于决策的补充信息」。上游生成失败时，下游应当降级继续，而不应硬依赖或崩溃——
本模块把「缺失」这一情况收敛成一处安全读取与统一占位文案。
"""

from typing import Final

from ..entitas import Entity
from ..models import EnvironmentComponent

###############################################################################################################################################
# 场景尚未生成环境叙事时使用的占位文案
MISSING_ENVIRONMENT_NARRATIVE: Final[str] = "（暂无环境描述）"


###############################################################################################################################################
def get_stage_environment(stage_entity: Entity) -> str:
    """安全读取场景的环境叙事。

    场景已生成环境叙事时返回其内容；尚未生成（上游失败或未运行）时返回
    MISSING_ENVIRONMENT_NARRATIVE 占位文案。调用方无需要求该组件存在。
    """
    if stage_entity.has(EnvironmentComponent):
        return stage_entity.get(EnvironmentComponent).narrative
    return MISSING_ENVIRONMENT_NARRATIVE


###############################################################################################################################################
