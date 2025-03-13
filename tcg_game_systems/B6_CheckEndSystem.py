from overrides import override
from entitas import ExecuteProcessor, Matcher  # type: ignore
from game.tcg_game import TCGGame
from components.components import (
    AttributeCompoment,
    ActorComponent,
    HeroActorFlagComponent,
    MonsterActorFlagComponent,
    DestroyFlagComponent,
)
from components.actions import DeadAction
from tcg_game_systems.status_check_utils import StatusCheckUtils
from loguru import logger


class B6_CheckEndSystem(ExecuteProcessor):

    ######################################################################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ######################################################################################################################################################
    @override
    def execute(self) -> None:

        # step1: 先只根据血量判断死亡，加上DeadAction，做标记，这一步是是安全无影响的。
        self._evaluate_entity_deaths()

        # step2: 重构前的执行。
        self.execute1()

    ######################################################################################################################################################
    @override
    async def a_execute2(self) -> None:

        # debug 一下！
        active_entities = self._game.get_group(
            Matcher(
                all_of=[
                    ActorComponent,
                ],
                any_of=[
                    HeroActorFlagComponent,
                    MonsterActorFlagComponent,
                ],
                none_of=[
                    DeadAction,
                ],
            )
        ).entities

        # 用这个工具。
        status_check_utils = StatusCheckUtils(
            game_context=self._game,
            stage_entities=set(),
            actor_entities=active_entities,
        )
        await status_check_utils.a_execute()

    ######################################################################################################################################################
    # 任何情况下，只要有AttributeCompoment，而且血量<=0，就加上DeadAction。
    def _evaluate_entity_deaths(self) -> None:

        # 一次抓出来。
        active_entities = self._game.get_group(
            Matcher(
                all_of=[
                    ActorComponent,
                    AttributeCompoment,
                ],
                any_of=[
                    HeroActorFlagComponent,
                    MonsterActorFlagComponent,
                ],
                none_of=[
                    DeadAction,
                ],
            )
        ).entities.copy()

        # 检查死亡, 目前写死，血量见0就是死，其实可以复杂点。
        for entity in active_entities:
            attr_comp = entity.get(AttributeCompoment)
            if attr_comp.hp <= 0:
                assert not entity.has(DeadAction)
                entity.replace(DeadAction, attr_comp.name, [])

    ######################################################################################################################################################
    # 英雄全死了么？
    def _are_all_heroes_dead(self) -> bool:

        active_hero_entities = self._game.get_group(
            Matcher(
                all_of=[
                    ActorComponent,
                    HeroActorFlagComponent,
                ],
                none_of=[
                    DeadAction,
                ],
            )
        ).entities

        # 删掉不和player在同一个stage里的
        current_stage = self._game.get_current_stage_entity()
        assert current_stage is not None
        active_hero_entities = {
            actor
            for actor in active_hero_entities
            if actor.get(ActorComponent).current_stage == current_stage._name
        }

        return len(active_hero_entities) == 0

    ######################################################################################################################################################
    # 怪全死了么？
    def _are_all_enemies_dead(self) -> bool:

        active_enemy_entities = self._game.get_group(
            Matcher(
                all_of=[
                    ActorComponent,
                    MonsterActorFlagComponent,
                ],
                none_of=[
                    DeadAction,
                ],
            )
        ).entities

        # 删掉不和player在同一个stage里的
        current_stage = self._game.get_current_stage_entity()
        assert current_stage is not None
        active_enemy_entities = {
            actor
            for actor in active_enemy_entities
            if actor.get(ActorComponent).current_stage == current_stage._name
        }

        return len(active_enemy_entities) == 0

    ######################################################################################################################################################
    # 战斗结束前，准备跳出的一些写死的处理，这是临时的。
    def _process_battle_end_actions(self) -> None:

        # 因为可能是删除的，所以要浅拷贝。
        inactive_heros = self._game.get_group(
            Matcher(
                all_of=[
                    DeadAction,
                    HeroActorFlagComponent,
                ],
            )
        ).entities.copy()

        # TODO: 这里应该是英雄死亡的处理, 临时把死亡标记去掉，因为会强制飞。
        for actor in inactive_heros:
            actor.remove(DeadAction)

        # 怪物死亡的处理，直接加上销毁标记。走pipeline-DestroySystem进行销毁。
        inactive_monsters = self._game.get_group(
            Matcher(
                all_of=[
                    DeadAction,
                    MonsterActorFlagComponent,
                ],
                none_of=[
                    DestroyFlagComponent,
                ],
            )
        ).entities.copy()

        # 怪物死亡的处理，直接加上销毁标记。走pipeline-
        for actor in inactive_monsters:
            actor.replace(DestroyFlagComponent, actor.get(DeadAction).name)

    ######################################################################################################################################################
    def execute1(self) -> None:
        if self._game._battle_manager._new_turn_flag:
            return
        if self._game._battle_manager._battle_end_flag:
            return

        # 检查回合结束
        if len(self._game._battle_manager._order_queue) == 0:
            self._game._battle_manager.add_history("回合结束！")
            self._game._battle_manager._new_turn_flag = True

        # 检查战斗结束
        # 英雄全死了，输了
        """
        hero_entities = self._game.get_group(
            Matcher(
                all_of=[
                    ActorComponent,
                    HeroActorFlagComponent,
                ],
            )
        ).entities
        all_heroes_dead = all(
            hero.get(AttributeCompoment).hp <= 0 for hero in hero_entities
        )
        if all_heroes_dead:
            self._game._battle_manager.add_history("战斗结束！你输了！")
            self._game._battle_manager._battle_end_flag = True
        # 怪全死了，赢了
        enemy_entities = self._game.get_group(
            Matcher(
                all_of=[
                    ActorComponent,
                    MonsterActorFlagComponent,
                ],
            )
        ).entities
        all_enemies_dead = all(
            enemy.get(AttributeCompoment).hp <= 0 for enemy in enemy_entities
        )
        if all_enemies_dead:
            self._game._battle_manager.add_history("战斗结束！你赢了！")
            self._game._battle_manager._battle_end_flag = True

        self._game._battle_manager.write_battle_history()

        # 结束就回Home，写死 TODO
        if self._game._battle_manager._battle_end_flag:
            self._game.teleport_actors_to_stage(hero_entities, "场景.营地")
        """

        result = 0
        if self._are_all_heroes_dead():
            # 英雄全死了，输了
            self._game._battle_manager.add_history("战斗结束！你输了！")
            self._game._battle_manager._battle_end_flag = True
            result = 1
        elif self._are_all_enemies_dead():
            # 怪全死了，赢了
            self._game._battle_manager.add_history("战斗结束！你赢了！")
            self._game._battle_manager._battle_end_flag = True
            result = 2

        # 写入战斗历史。
        self._game._battle_manager.write_battle_history()

        # 战斗1结束去战斗2，战斗2结束回Home。写死，TODO
        if self._game._battle_manager._battle_end_flag:

            # 出战斗前的清理工作
            self._process_battle_end_actions()

            current_stage = self._game.get_current_stage_entity()
            assert current_stage is not None
            current_stage_name = current_stage._name

            if current_stage_name == "场景.哥布林巢穴王座厅":
                if result == 1:
                    # 回到营地
                    self._game.teleport_actors_to_stage(
                        self._game.retrieve_all_hero_entities(), "场景.营地"
                    )
                    return
                elif result == 2:
                    # 去战斗2
                    self._game._battle_manager._new_battle_refresh()
                    self._game.teleport_actors_to_stage(
                        self._game.retrieve_all_hero_entities(), "场景.哥布林巢穴密室"
                    )
                    return

            # 回到营地
            self._game.teleport_actors_to_stage(
                self._game.retrieve_all_hero_entities(), "场景.营地"
            )
