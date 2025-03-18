from entitas import ExecuteProcessor, Matcher  # type: ignore
from typing import final, override
from game.tcg_game import TCGGame
from components.components import ActorComponent
from components.actions2 import (
    CandidateAction2,
)
from extended_systems.combat_system import CombatSystem, CombatState

@final
class DungeonStateActorPlanningSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###################################################################################################################################################################
    @override
    def execute(self) -> None:
        
        combat_system = self._game.combat_system.current_combat()
        match(combat_system.current_state):
            case CombatState.INIT:
                self._excute_combat_init()
            case _:
                assert False, f"未知的状态 = {combat_system.current_state}"
        
        
        

        # self._game._round_number = self._game._round_number + 1

        # entities2 = self._game.get_group(
        #     Matcher(
        #         all_of=[
        #             ActorComponent,
        #         ],
        #     )
        # ).entities

        # for actor_entity in entities2:
            
        #     break

        #     stage_entity = self._game.safe_get_stage_entity(actor_entity)
        #     assert stage_entity is not None

        #     self._game.append_human_message(
        #         entity=actor_entity,
        #         chat=f"# 提示！战斗回合开始 = {self._game._round_number}",
        #         tag=f"battle:{stage_entity._name}:{self._game._round_number}",
        #     )

        #     actor_entity.replace(CandidateAction2, actor_entity._name)
            
    ###################################################################################################################################################################
    def _excute_combat_init(self) -> None:
        pass
            

    ###################################################################################################################################################################
