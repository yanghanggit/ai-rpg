from typing import Final, Set, final
from loguru import logger
from overrides import override
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from ..models import (
    ActorComponent,
    AppearanceComponent,
    # EnemyComponent,
)


#######################################################################################################################################
def _format_appearance_init_notification(appearance: str) -> str:
    """格式化外观初始化通知消息。

    Args:
        appearance: 完整的外观描述

    Returns:
        格式化后的通知消息字符串
    """
    return f"""# 你的外观信息已经初始化: 

{appearance}"""


#######################################################################################################################################
@final
class ActorAppearanceInitSystem(ExecuteProcessor):
    """角色外观初始化系统（Init 语义）。

    在每帧执行时，将 base_body 赋值给 appearance，作为初始外观。
    仅处理 base_body 不为空且 appearance 为空的角色实体，天然幂等。

    后续可在此系统之后接入 LLM 生成系统，将 base_body + 装备信息合成
    更完整的 appearance 描述，覆盖此处的初始值。

    Attributes:
        _game: TCG游戏上下文，用于访问实体和游戏状态
    """

    def __init__(self, game: TCGGame) -> None:
        self._game: Final[TCGGame] = game

    #######################################################################################################################################
    @override
    async def execute(self) -> None:

        # 这里就刷新一遍。
        self._initialize_appearances()

    #######################################################################################################################################
    def _initialize_appearances(self) -> None:
        """将 base_body 赋值给 appearance，作为初始外观。

        筛选条件：base_body 不为空 且 appearance 为空。

        Args:
            actor_entities: 所有角色实体的集合
        """
        actor_entities = self._game.get_group(
            Matcher(all_of=[ActorComponent, AppearanceComponent])
        ).entities.copy()

        for actor_entity in actor_entities:

            appearance_comp = actor_entity.get(AppearanceComponent)
            assert (
                appearance_comp.base_body != ""
            ), f"角色 {actor_entity.name} 的 base_body 不能为空"

            if appearance_comp.appearance != "":
                continue

            actor_entity.replace(
                AppearanceComponent,
                appearance_comp.name,
                appearance_comp.base_body,
                appearance_comp.base_body,  # appearance 初始值 = base_body
            )

            self._game.add_human_message(
                actor_entity,
                _format_appearance_init_notification(appearance_comp.base_body),
            )

            logger.info(
                f"✅ 角色 {actor_entity.name} 外观已初始化（base_body → appearance）"
            )

    #######################################################################################################################################
