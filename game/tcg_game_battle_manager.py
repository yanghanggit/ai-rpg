from collections import deque
import json
from typing import Deque, List, Union
from game.tcg_game import TCGGame
from tcg_models.v_0_0_1 import (
    BattleHistory,
    EventMsg,
    ActiveSkill,
    HitInfo,
    HitType,
    TriggerSkill,
    ActorInstance,
)
from components.components import ActorComponent


# TODO 整个系统都是prototype里临时用的！！demo全重写！
class BattleManager:
    def __init__(self) -> None:
        self._combat_num: int = 0
        self._turn_num: int = 0
        self._new_turn_flag: bool = False
        self._battle_end_flag: bool = False
        self._hits_stack: Deque[HitInfo] = deque()
        self._order_queue: Deque[str] = deque()
        self.battle_history: BattleHistory

    def add_history(self, msg: Union[str, EventMsg]) -> None:
        self.battle_history.logs[self._turn_num].append(msg)

    """ def __init__(self, game: TCGGame, context: TCGGameContext) -> None:
        self._battle_num: int = 0
        self._log_path: str = ""
        self._game: TCGGame = game
        self._context: TCGGameContext = context
        self.turn_num: int = 0
        self.battle_history: BattleHistory = BattleHistory()
        # self.player_formation_map : Dic[int, str]
        # self.enemy_formation_map
        self._event_temp: str = ""
        self._option_temp: int = 0
        self._actor_move_queue_temp: Deque[str] = deque()
        self._hit_stack_temp : Deque[HitInfo] = deque()

    # 用于新战斗开始时重置状态
    def refresh(self) -> None:
        self._battle_num += 1
        self._log_path = f"battlelog/{self._battle_num}.json"

    # 每回合开始，重新计算行动顺序，没做可能影响速度的技能，没做回合开始时触发的技能，没做回合开始时减buff持续时间，可以让ai来，多等会就多等会
    def new_turn(self) -> None:
        self.turn_num += 1
        actor_list = self._game.world_runtime.root.actors.copy()
        actor_list.extend(self._game.world_runtime.root.players.copy())
        actor_list.sort(key=lambda x: x.attributes[5], reverse=True)
        for actor in actor_list:
            self._actor_move_queue_temp.append(actor.name)

    def gen_BattleMsg(self, description: str) -> BattleMsg:
        return BattleMsg(self._hit_stack_temp, description)

    def gen_EventMsg(self, result: str) -> EventMsg:
        return EventMsg(self._event_temp, self._option_temp, result)

    # 根据不同的技能创造hit TODO
    def gen_Hit(
        self, skill: ActiveSkill, source: str, target: str, level: int
    ) -> List[HitInfo]:
        pass

    # 检查该trigger skill会不会对hit有反应
    def check_trigger(self, trigger: TriggerSkill, hit: HitInfo) -> HitInfo | None:
        pass

    # 执行所有hit
    def execute_hit(self) -> None:
        target_entity = self._context.get_actor_entity(hit.target)
        if target_entity is None:
            assert False
        target_comp = target_entity.get(ActorComponent)
        instance_list = self._game.world_runtime.root.actors.copy()
        instance_list.append(self._game.world_runtime.root.players.copy())
        target_instance : ActorInstance = None
        for instance in instance_list:
            if instance.name == hit.target:
                target_instance = hit.target
                break
        if target_instance is None:
            assert False

        

    def save_log(self) -> None:
        with open(self._log_path, "w", encoding="utf-8") as file:
            json.dump(self.battle_history, file)
 """
