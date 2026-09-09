"""战斗初始化系统（场景侧）：为战斗场景注入战斗专用规则，将战斗状态转换为进行中。"""

from typing import Final, List, final, override

from loguru import logger

from ..entitas import ExecuteProcessor
from ..game.dbg_game import DBGGame
from ..game.dbg_combat_processor import (
    get_alive_monsters_in_stage,
    get_alive_party_members_in_stage,
)
from ..models import StageDescriptionComponent
from ..models.messages import AIMessage, HumanMessage
from ..utils import prompt_builder


###################################################################################################################################################################
@prompt_builder
def _build_stage_combat_state_prompt(
    stage_description: str,
    party_names: List[str],
    monster_names: List[str],
) -> str:
    """生成场景视角的战斗状态提示词（含当前存活角色的阵营信息）。"""
    party = "、".join(party_names) if party_names else "无"
    monsters = "、".join(monster_names) if monster_names else "无"
    return f"""# 战斗场景状态

## 场景环境

{stage_description}

## 场上阵营

- 友方（队伍成员）：{party}
- 敌方（怪物）：{monsters}

（仲裁时凡提到「友方/玩家方」，均指上方友方阵营全体存活角色。）"""


###################################################################################################################################################################
@final
class CombatInitStageSystem(ExecuteProcessor):
    """战斗初始化系统（场景侧）：注入战斗专用规则、转换战斗状态为进行中。"""

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ###################################################################################################################################################################
    @override
    async def execute(self) -> None:

        if not self._game.current_dungeon_combat_room.combat.is_initializing:
            logger.debug("当前战斗状态非 initializing，跳过战斗初始化（场景侧）")
            return

        logger.info("战斗初始化（场景侧）开始，正在注入战斗规则并转换战斗状态...")

        # 获取玩家实体，player 所在场景即战斗场景
        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "无法找到玩家实体！"

        # 获取当前场景实体
        current_stage_entity = self._game.resolve_stage_entity(player_entity)
        assert current_stage_entity is not None, "无法找到当前场景实体！"
        assert current_stage_entity.has(
            StageDescriptionComponent
        ), "当前场景实体缺少 StageDescriptionComponent 组件！"

        # 向场景实体注入当前战斗场景状态（谁在场上、阵营分别是什么），供后续仲裁阶段作为上下文
        stage_description_comp = current_stage_entity.get(StageDescriptionComponent)
        party_members = get_alive_party_members_in_stage(
            current_stage_entity, self._game
        )
        monsters = get_alive_monsters_in_stage(current_stage_entity, self._game)

        self._game.add_human_message(
            current_stage_entity,
            HumanMessage(
                content=_build_stage_combat_state_prompt(
                    stage_description=stage_description_comp.narrative,
                    party_names=[e.name for e in party_members],
                    monster_names=[e.name for e in monsters],
                )
            ),
        )
        self._game.add_ai_message(
            current_stage_entity,
            AIMessage(content="已感知当前战斗场景状态。"),
        )

        # 设置战斗为进行中（第一回合将由 DrawCardsAction 触发的 CombatRoundStartSystem 创建）
        self._game.current_dungeon_combat_room.combat.transition_to_ongoing()
        assert (
            self._game.current_dungeon_combat_room.combat.is_ongoing
        ), "战斗状态转换失败，当前状态非 ONGOING！"


###################################################################################################################################################################
