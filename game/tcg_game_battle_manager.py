from collections import deque
from pathlib import Path
from typing import Deque, Optional

from loguru import logger
from tcg_models.v_0_0_1 import (
    BattleHistory,
    Buff,
    DamageType,
    EventMsg,
    ActiveSkill,
    HitInfo,
    HitType,
    # TriggerSkill,
    # ActorInstance,
    # SkillInfo,
)

# from components.components import ActorComponent
import random


# TODO 整个系统都是prototype里临时用的！！demo全重写！
class BattleManager:
    def __init__(self) -> None:
        from game.tcg_game import TCGGame

        # self._game: Optional[TCGGame] = None
        self._combat_num: int = 0
        self._turn_num: int = 0
        self._new_turn_flag: bool = False
        self._battle_end_flag: bool = False
        self._hits_stack: Deque[HitInfo] = deque()
        self._order_queue: Deque[str] = deque()
        self.battle_history: BattleHistory = BattleHistory(logs={})
        # self._event_msg: EventMsg = EventMsg(event="", option=0, result="")

        try:
            write_path: Path = Path("battlelog") / "battle_history.json"
            write_path.mkdir(parents=True, exist_ok=True)
            write_path.write_text(
                self.battle_history.model_dump_json(), encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"An error occurred: {e}")

        self.add_history("战斗开始！")

    def add_history(self, msg: str) -> None:
        if self._turn_num not in self.battle_history.logs:
            self.battle_history.logs[self._turn_num] = []
        self.battle_history.logs[self._turn_num].append(msg)

    def generate_hit(
        self, skill: ActiveSkill, source: str, target: str, text: str
    ) -> HitInfo:
        value: int
        type: HitType
        dmgtype: DamageType
        buff: Optional[Buff] = skill.buff
        log: str
        log = f"{source} 对 {target} 使用了 {skill.name}。"

        # 这里应该是造成属性多少倍的伤害，懒得写好长的get了，原型里写死吧
        # 有效性，先不问ai了，随便roll一个吧
        match skill.name:
            case "斩击":
                value = int(skill.values[random.randint(0, 3)] * 50)
                type = HitType.DAMAGE
                dmgtype = DamageType.PHYSICAL
            case "战地治疗":
                value = int(0.5 * 30)
                type = HitType.HEAL
                dmgtype = DamageType.HEAL
            case "火球":
                value = int(skill.values[random.randint(0, 3)] * 60)
                type = HitType.DAMAGE
                dmgtype = DamageType.FIRE
            case "冰雾":
                value = int(skill.values[random.randint(0, 3)] * 60)
                type = HitType.DAMAGE
                dmgtype = DamageType.ICE
            case "猛砸":
                value = int(skill.values[random.randint(0, 3)] * 80)
                type = HitType.DAMAGE
                dmgtype = DamageType.PHYSICAL
            case "乱舞":
                value = int(skill.values[random.randint(0, 3)] * 80)
                type = HitType.DAMAGE
                dmgtype = DamageType.PHYSICAL

        return HitInfo(
            skill=skill,
            source=source,
            target=target,
            value=value,
            type=type,
            dmgtype=dmgtype,
            buff=buff,
            log=log,
            text=text,
        )

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
