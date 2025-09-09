from typing import final, override
from loguru import logger
from ..entitas import ExecuteProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    EnvironmentComponent,
    RPGCharacterProfileComponent,
)


###################################################################################################################################################################
@final
class CombatKickOffSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###################################################################################################################################################################
    @override
    async def execute(self) -> None:

        # 分析阶段
        if not self._game.current_engagement.is_kickoff_phase:
            return

        assert (
            len(self._game.current_engagement.rounds) == 0
        ), "战斗触发阶段不允许有回合数！"

        # 参与战斗的人
        player_entity = self._game.get_player_entity()
        assert player_entity is not None
        actor_entities = self._game.retrieve_actors_on_stage(player_entity)
        assert len(actor_entities) > 0, "不可能出现没人参与战斗的情况！"

        # 取场景
        current_stage_entity = self._game.safe_get_stage_entity(player_entity)
        assert current_stage_entity is not None

        # 取场景内所有角色的外观
        actors_apperances_mapping = (
            self._game.retrieve_actor_appearance_on_stage_mapping(current_stage_entity)
        )

        # 取场景描述
        current_stage_narrate = current_stage_entity.get(EnvironmentComponent).narrate

        for actor_entity in actor_entities:

            rpg_character_profile_component = actor_entity.get(
                RPGCharacterProfileComponent
            )
            assert rpg_character_profile_component is not None

            # 复制一份角色外观映射，并且去掉自己的外观
            copy_actors_apperances_mapping = actors_apperances_mapping.copy()
            copy_actors_apperances_mapping.pop(actor_entity._name, None)

            # 生成提示词, 就是添加上下文，标记战斗初始化。
            gen_prompt = f"""# 发生事件！战斗触发！这是本次战斗你的初始化信息。
## 场景信息
{current_stage_entity._name} ｜ {current_stage_narrate}
## （场景内）角色信息
{str(copy_actors_apperances_mapping)}
## 你的属性 (仅在战斗中使用)
{rpg_character_profile_component.attrs_prompt}
## 你的状态 (仅在战斗中使用)
{rpg_character_profile_component.status_effects_prompt}。"""

            self._game.append_human_message(
                actor_entity,
                gen_prompt,
                combat_kickoff_tag=current_stage_entity._name,
            )

        # final 开始战斗，最后一步，转换到战斗阶段。!!!
        self._game.current_engagement.combat_ongoing()

        logger.info(
            f"{current_stage_entity._name}, 战斗触发阶段完成，进入战斗进行阶段。"
        )

        if not self._game.setup_round():
            logger.error(f"not web_game.setup_round()")


###################################################################################################################################################################
