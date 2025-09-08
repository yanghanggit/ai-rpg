from typing import List, Set, Tuple, final

from loguru import logger
from overrides import override

from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from ..models import (
    AgentEvent,
    DirectorAction,
    FeedbackAction,
    HandComponent,
    PlayCardsAction,
    Round,
    RPGCharacterProfileComponent,
    StatusEffect,
    TurnAction,
)


#######################################################################################################################################
@final
class CombatResolutionSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    #######################################################################################################################################
    @override
    async def execute(self) -> None:
        self._manage_combat_sequence()

    #######################################################################################################################################
    def _manage_combat_sequence(self) -> None:
        if not self._game.current_engagement.is_on_going_phase:
            return  # 不是本阶段就直接返回

        logger.debug(
            f"Current combat rounds: {len(self._game.current_engagement.rounds)}"
        )

        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        stage_entity = self._game.safe_get_stage_entity(player_entity)
        assert stage_entity is not None

        actors_on_stage = self._game.retrieve_actors_on_stage(stage_entity)

        available_skill_entities = self._game.get_group(
            Matcher(
                all_of=[
                    HandComponent,
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
        play_cards_then_feedback_action_actors = self._game.get_group(
            Matcher(
                all_of=[
                    PlayCardsAction,
                    FeedbackAction,
                ],
            )
        ).entities

        if len(turn_action_actors) == 0:
            logger.info(f"没有角色出手。什么都没有发生。")
            return

        if len(play_cards_then_feedback_action_actors) != len(turn_action_actors):
            logger.error(
                f"出手的角色数量和选择技能的角色数量不一致。可能是request有问题。"
            )
            return

        # 所有的角色，理论上都出手了。
        if len(turn_action_actors) != len(actors_on_stage):
            logger.error(
                f"出手的角色数量和场景中的角色数量不一致。可能是request有问题。"
            )
            return

        assert len(play_cards_then_feedback_action_actors) == len(actors_on_stage)
        assert len(available_skill_entities) == len(actors_on_stage)

        # 场景的也需要做检查！！！
        if not stage_entity.has(DirectorAction):
            logger.error(f"{stage_entity._name} 没有进行战斗演出，应该是出错了。")
            return

        stage_director_action = stage_entity.get(DirectorAction)
        assert stage_director_action is not None
        if (
            stage_director_action.calculation == ""
            or stage_director_action.performance == ""
        ):
            logger.error(f"战斗演出没有计算和表演。!!!!!")
            return

        last_round = self._game.current_engagement.last_round

        # 看一看出手顺序。
        first_turn_actor = next(iter(turn_action_actors))
        first_turn_action = first_turn_actor.get(TurnAction)
        logger.debug(
            f"First turn actor: {first_turn_action.rounds}, {first_turn_action.round_turns}"
        )
        # 记录
        last_round.round_turns = first_turn_action.round_turns

        # 第一步，通知回合开始！！！提示! 添加一个记忆！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！
        self._process_turn_action(turn_action_actors)

        # 第二步，添加决定使用什么技能 ！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！
        self._process_play_cards_action(
            play_cards_then_feedback_action_actors, last_round
        )

        # 第三步，场景广播 ！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！
        self._game.broadcast_event(
            entity=stage_entity,
            agent_event=AgentEvent(
                message=f"# 发生事件！战斗回合:\n{stage_director_action.performance}",
            ),
        )
        # 记录
        last_round.stage_director_calculation = stage_director_action.calculation
        last_round.stage_director_performance = stage_director_action.performance

        # 第四步，处理技能效果
        self._process_feedback_action(
            play_cards_then_feedback_action_actors, last_round
        )

    #######################################################################################################################################
    def _process_turn_action(self, actor_entities: Set[Entity]) -> None:

        for actor_entity in actor_entities:

            turn_action = actor_entity.get(TurnAction)
            assert turn_action is not None

            self._game.append_human_message(
                entity=actor_entity,
                chat=f"# 提示！战斗回合开始，第 {turn_action.rounds} 回合！",
            )

    #######################################################################################################################################
    def _process_play_cards_action(
        self, actor_entities: Set[Entity], round: Round
    ) -> None:
        for actor_entity2 in actor_entities:
            play_cards_action = actor_entity2.get(PlayCardsAction)
            assert play_cards_action is not None

            assert play_cards_action.skill.name != ""
            message = f""" # 发生事件！经过思考后，你决定行动！
## 使用技能 = {play_cards_action.skill.name}
## 目标 = {play_cards_action.targets}
## 原因 = {play_cards_action.reason}
## 技能数据
{play_cards_action.skill.model_dump_json()}"""

            self._game.append_human_message(actor_entity2, message)

            round.select_report[actor_entity2._name] = message

    #######################################################################################################################################
    def _process_feedback_action(
        self, actor_entities: Set[Entity], round: Round
    ) -> None:

        for actor_entity3 in actor_entities:

            feedback_action = actor_entity3.get(FeedbackAction)
            assert feedback_action.calculation != ""
            assert feedback_action.performance != ""
            #            assert feedback_action.description != ""

            #
            self._update_combat_health(
                actor_entity3,
                feedback_action.update_hp,
                feedback_action.update_max_hp,
            )

            # 效果更新
            self._game.append_status_effects(actor_entity3, feedback_action.effects)

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
生命值：{feedback_action.update_hp}/{feedback_action.update_max_hp}
持续效果：
{remaining_effects_prompt}
失效效果：
{removed_effects_prompt}"""

            self._game.append_human_message(actor_entity3, message)

            round.feedback_report[actor_entity3._name] = message

    #######################################################################################################################################
    # 状态效果扣除。
    def _update_combat_remaining_effects(
        self, entity: Entity
    ) -> Tuple[List[StatusEffect], List[StatusEffect]]:

        # 效果更新
        assert entity.has(RPGCharacterProfileComponent)
        character_profile_component = entity.get(RPGCharacterProfileComponent)
        assert character_profile_component is not None

        remaining_effects = []
        removed_effects = []

        for status_effect in character_profile_component.status_effects:
            # 效果回合数扣除
            status_effect.rounds -= 1
            status_effect.rounds = max(0, status_effect.rounds)

            # status_effect持续回合数大于0，继续保留，否则移除
            if status_effect.rounds > 0:
                remaining_effects.append(status_effect)
            else:
                # 添加移除
                removed_effects.append(status_effect)

        # 需要从总的 character_profile_component.status_effects 内移除所有rounds <= 0的数据。
        character_profile_component.status_effects = remaining_effects

        # 外部返回
        return remaining_effects, removed_effects

    ###############################################################################################################################################
    def _update_combat_health(
        self,
        entity: Entity,
        update_hp: float,
        update_max_hp: float,
    ) -> None:

        character_profile_component = entity.get(RPGCharacterProfileComponent)
        assert character_profile_component is not None
        character_profile_component.rpg_character_profile.hp = int(update_hp)

    ###############################################################################################################################################
