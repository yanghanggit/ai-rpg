"""
战斗初始化系统
负责在战斗触发阶段为每个参战角色生成初始上下文提示词，包含场景叙事、其他角色外观、自身属性和状态效果。
执行后将战斗状态从 starting 转换为 ongoing，并启动第一回合。
"""
from typing import final, override
from loguru import logger
from ..entitas import ExecuteProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    EnvironmentComponent,
    CombatStatsComponent,
)
from ..utils import format_dict_as_markdown_list


###################################################################################################################################################################
def _generate_combat_kickoff_prompt(
    stage_name: str,
    stage_description: str,
    filtered_actor_appearances: dict[str, str],
    attrs_prompt: str,
    status_effects_prompt: str,
) -> str:
    return f"""# 通知！战斗触发！如下是当前场景的信息，请基于这些信息，准备好战斗！
            
## 场景叙事

{stage_name} ｜ {stage_description}

## 其余角色

{format_dict_as_markdown_list(filtered_actor_appearances)}

## 你的**属性**

{attrs_prompt}

## 你的**状态效果(status_effects)**

{status_effects_prompt}"""


###################################################################################################################################################################
@final
class CombatInitializationSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###################################################################################################################################################################
    @override
    async def execute(self) -> None:

        # 分析阶段
        if not self._game.current_combat_sequence.is_starting:
            # 非战斗触发阶段，直接返回
            return

        assert (
            len(self._game.current_combat_sequence.current_rounds) == 0
        ), "战斗触发阶段不允许有回合数！"

        # 获取玩家实体
        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        # 获取当前场景实体
        current_stage_entity = self._game.safe_get_stage_entity(player_entity)
        assert current_stage_entity is not None

        # 获取场景环境组件
        environment_comp = current_stage_entity.get(EnvironmentComponent)
        assert environment_comp is not None

        # 参与战斗的角色实体列表
        actor_entities = self._game.get_alive_actors_on_stage(player_entity)
        assert len(actor_entities) > 0, "不可能出现没人参与战斗的情况！"
        for actor_entity in actor_entities:

            # 获取角色属性组件
            combat_stats_comp = actor_entity.get(CombatStatsComponent)
            assert combat_stats_comp is not None

            # 获取场景内所有角色的外观，并且去掉自己的外观
            filtered_actor_appearances = self._game.get_stage_actor_appearances(
                current_stage_entity
            )
            filtered_actor_appearances.pop(actor_entity.name, None)

            # 生成提示词
            gen_prompt = _generate_combat_kickoff_prompt(
                stage_name=current_stage_entity.name,
                stage_description=environment_comp.description,
                filtered_actor_appearances=filtered_actor_appearances,
                attrs_prompt=combat_stats_comp.stats_prompt,
                status_effects_prompt=combat_stats_comp.status_effects_prompt,
            )

            # 追加提示词到角色对话中
            self._game.append_human_message(
                actor_entity,
                gen_prompt,
                combat_kickoff_tag=current_stage_entity.name,
            )

        # 设置战斗为进行中
        self._game.current_combat_sequence.transition_to_ongoing()

        # 设置第一回合
        if not self._game.start_new_round():
            logger.error(f"not web_game.setup_round()")


###################################################################################################################################################################
