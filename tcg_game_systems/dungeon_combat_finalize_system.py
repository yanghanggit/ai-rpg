from loguru import logger
from entitas import Matcher, Entity, Matcher, ExecuteProcessor  # type: ignore
from components.components_v_0_0_1 import (
    SkillCandidateQueueComponent,
    CombatEffectsComponent,
    CombatAttributesComponent,
)
from overrides import override
from typing import List, Set, Tuple, final
from game.tcg_game import TCGGame
from components.actions_v_0_0_1 import (
    TurnAction,
    StageDirectorAction,
    SelectAction,
    FeedbackAction,
)
from models.v_0_0_1 import Effect

from models.event_models import AgentEvent


#######################################################################################################################################
@final
class DungeonCombatFinalizeSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    #######################################################################################################################################
    @override
    def execute(self) -> None:
        if not self._game.combat_system.is_on_going_phase:
            return  # 不是本阶段就直接返回

        logger.info("DungeonCombatFinalizeSystem is executing...")
        logger.info(f"Current combat rounds: {len(self._game.combat_system.rounds)}")

        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        stage_entity = self._game.safe_get_stage_entity(player_entity)
        assert stage_entity is not None

        skill_candidate_entities = self._game.get_group(
            Matcher(
                all_of=[
                    SkillCandidateQueueComponent,
                ],
            )
        ).entities

        # 出手的角色
        turn_action_actors = self._game.get_group(
            Matcher(
                all_of=[
                    TurnAction,
                ],
            )
        ).entities

        # 出手的角色
        select_then_feedback_action_actors = self._game.get_group(
            Matcher(
                all_of=[
                    SelectAction,
                    FeedbackAction,
                ],
            )
        ).entities

        # 所有的角色，理论上都出手了。
        actors_on_stage = self._game.retrieve_actors_on_stage(stage_entity)
        assert len(turn_action_actors) == len(actors_on_stage)
        assert len(select_then_feedback_action_actors) == len(actors_on_stage)
        assert len(skill_candidate_entities) == len(actors_on_stage)

        assert len(turn_action_actors) > 0
        if len(turn_action_actors) == 0:
            logger.error(f"没有角色出手。???!!!!!")
            return

        if len(select_then_feedback_action_actors) != len(turn_action_actors):
            logger.error(
                f"出手的角色数量和选择技能的角色数量不一致。可能是request有问题。"
            )
            return

        # 场景的也需要做检查！！！
        if not stage_entity.has(StageDirectorAction):
            logger.error(f"{stage_entity._name} 没有进行战斗演绎，应该是出错了。")
            return

        stage_director_action = stage_entity.get(StageDirectorAction)
        assert stage_director_action is not None
        if (
            stage_director_action.calculation == ""
            or stage_director_action.performance == ""
        ):
            logger.error(f"战斗演绎没有计算和表演。!!!!!")
            return

        # 看一看出手顺序。
        first_turn_actor = next(iter(turn_action_actors))
        first_turn_action = first_turn_actor.get(TurnAction)
        logger.info(
            f"First turn actor: {first_turn_action.rounds}, {first_turn_action.round_turns}"
        )

        # 第一步，通知回合开始！！！提示! 添加一个记忆！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！
        self._process_turn_action(turn_action_actors)

        # 第二步，添加决定使用什么技能 ！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！
        self._process_select_action(select_then_feedback_action_actors)

        # 第三步，场景广播 ！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！
        self._game.broadcast_event(
            entity=stage_entity,
            agent_event=AgentEvent(
                message=f"# 发生事件！战斗回合:\n{stage_director_action.performance}",
            ),
        )

        # 第四步，处理技能效果
        self._process_feedback_action(select_then_feedback_action_actors)

    #######################################################################################################################################
    def _process_turn_action(self, actor_entities: Set[Entity]) -> None:
        for actor_entity1 in actor_entities:
            turn_action = actor_entity1.get(TurnAction)
            assert turn_action is not None

            self._game.append_human_message(
                entity=actor_entity1,
                chat=f"# 提示！战斗回合开始，第 {turn_action.rounds} 回合！",
                combat_rounds=f"{turn_action.rounds}",
            )

    #######################################################################################################################################
    def _process_select_action(self, actor_entities: Set[Entity]) -> None:
        for actor_entity2 in actor_entities:
            select_action = actor_entity2.get(SelectAction)
            assert select_action is not None

            assert select_action.skill.name != ""
            message = f""" # 发生事件！经过思考后，你决定行动！
## 使用技能 = {select_action.skill.name}
## 目标 = {select_action.targets}
## 原因 = {select_action.reason}
## 技能数据
{select_action.skill.model_dump_json()}"""

            self._game.append_human_message(actor_entity2, message)

    #######################################################################################################################################
    def _process_feedback_action(self, actor_entities: Set[Entity]) -> None:

        for actor_entity3 in actor_entities:

            feedback_action = actor_entity3.get(FeedbackAction)
            assert feedback_action.calculation != ""
            assert feedback_action.performance != ""
            assert feedback_action.description != ""

            # 血量更新
            self._update_combat_health(
                actor_entity3, feedback_action.hp, feedback_action.max_hp
            )

            # 效果更新
            self._game.update_combat_effects(actor_entity3, feedback_action.effects)

            # 效果扣除
            remaining_effects, removed_effects = self._update_combat_remaining_effects(
                actor_entity3
            )

            remaining_effects_prompt = "无"
            if len(remaining_effects) > 0:
                remaining_effects_prompt = "\n".join(
                    [e.model_dump_json() for e in remaining_effects]
                )

            removed_effects_prompt = "无"
            if len(removed_effects) > 0:
                removed_effects_prompt = "\n".join(
                    [e.model_dump_json() for e in removed_effects]
                )

            # 添加记忆
            message = f"""# 你的状态更新，请注意！
{feedback_action.description}
生命值：{feedback_action.hp}/{feedback_action.max_hp}
持续效果：
{remaining_effects_prompt}
失效效果：
{removed_effects_prompt}"""

            self._game.append_human_message(actor_entity3, message)

    #######################################################################################################################################
    # 状态效果扣除。
    def _update_combat_remaining_effects(
        self, entity: Entity
    ) -> Tuple[List[Effect], List[Effect]]:

        # 效果更新
        assert entity.has(CombatEffectsComponent)
        combat_effects_comp = entity.get(CombatEffectsComponent)
        assert combat_effects_comp is not None

        current_effects = combat_effects_comp.effects.copy()
        remaining_effects = []
        removed_effects = []
        for i, e in enumerate(current_effects):
            current_effects[i].rounds -= 1
            current_effects[i].rounds = max(0, current_effects[i].rounds)

            if current_effects[i].rounds > 0:
                remaining_effects.append(current_effects[i])
            else:
                removed_effects.append(current_effects[i])

        entity.replace(
            CombatEffectsComponent, combat_effects_comp.name, remaining_effects
        )

        return remaining_effects, removed_effects

    ###############################################################################################################################################
    def _update_combat_health(self, entity: Entity, hp: float, max_hp: float) -> None:

        combat_attributes_comp = entity.get(CombatAttributesComponent)
        assert combat_attributes_comp is not None

        entity.replace(
            CombatAttributesComponent,
            combat_attributes_comp.name,
            hp,
            max_hp,
            combat_attributes_comp.physical_attack,
            combat_attributes_comp.physical_defense,
            combat_attributes_comp.magic_attack,
            combat_attributes_comp.magic_defense,
        )

    #######################################################################################################################################
