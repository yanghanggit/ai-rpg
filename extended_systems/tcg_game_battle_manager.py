from collections import deque
from pathlib import Path
from typing import Deque, List, Optional

from loguru import logger
from pydantic import BaseModel
from tcg_models.v_0_0_1 import (
    BattleHistory,
    Buff,
    DamageType,
    ActiveSkill,
    HitInfo,
    HitType,
    # TriggerSkill,
)
import random


class _EventMsg(BaseModel):
    event: str
    choice: int
    result: str
    done_flag: bool


# TODO 整个系统都是prototype里临时用的！！demo全重写！
class BattleManager:
    def __init__(self, root_write_dir: Path) -> None:

        self._root_write_dir: Path = root_write_dir
        self._combat_num: int = 0
        self._turn_num: int = 0
        self._new_turn_flag: bool = False
        self._battle_end_flag: bool = False
        self._hits_stack: Deque[HitInfo] = deque()
        self._order_queue: Deque[str] = deque()
        self._battle_history: BattleHistory = BattleHistory()
        self._event_msg: _EventMsg = _EventMsg(
            event="", choice=0, result="", done_flag=False
        )

        self.write_battle_history()
        self.add_history("战斗开始！")

    def _new_battle_refresh(self) -> None:
        self._combat_num += 1
        self._turn_num = 0
        self._new_turn_flag = False
        self._battle_end_flag = False
        self._hits_stack.clear()
        self._order_queue.clear()
        self._battle_history.logs.clear()
        self._event_msg.done_flag = False

        self.write_battle_history()
        self.add_history("战斗开始！")

    def add_history(self, msg: str) -> None:
        if msg != "":
            self._battle_history.logs.setdefault(self._turn_num, []).append(msg)

    def generate_hits(
        self, skill: ActiveSkill, source: str, target: str, text: str
    ) -> List[HitInfo]:
        buff: Optional[Buff] = skill.buff
        log = f"{source} 对 {target} 使用了 {skill.name}。"
        ret = []

        # 这里应该是造成属性多少倍的伤害，懒得写好长的get了，原型里写死吧
        # 有效性，先不问ai了，随便roll一个吧
        match skill.name:
            case "斩击":
                value = int(skill.values[random.randint(0, 3)] * 50)
                type = HitType.DAMAGE
                dmgtype = DamageType.PHYSICAL
            case "战地治疗":
                value = int(30)
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
                value = int(skill.values[random.randint(0, 3)] * 65)
                type = HitType.DAMAGE
                dmgtype = DamageType.PHYSICAL
                ret.append(
                    HitInfo(
                        skill=skill,
                        source=source,
                        target=target,
                        value=int(skill.values[4]),
                        type=HitType.ADDBUFF,
                        dmgtype=DamageType.BUFF,
                        buff=buff,
                        log="",
                        text="",
                        is_cost=False,
                        is_event=False,
                    )
                )
            case "乱舞":
                value = int(skill.values[random.randint(0, 3)] * 65)
                type = HitType.DAMAGE
                dmgtype = DamageType.PHYSICAL

        ret.append(
            HitInfo(
                skill=skill,
                source=source,
                target=target,
                value=value,
                type=type,
                dmgtype=dmgtype,
                buff=buff,
                log=log,
                text=text,
                is_cost=True,
                is_event=False,
            )
        )
        return ret

    @property
    def battle_history_dump(self) -> str:
        return self._battle_history.model_dump_json()

    def write_battle_history(self) -> None:

        try:

            write_dir: Path = self._root_write_dir / "battlelog"
            write_dir.mkdir(parents=True, exist_ok=True)
            assert write_dir.exists()
            assert write_dir.is_dir()

            write_file_path: Path = write_dir / "history.json"
            write_file_path.write_text(
                self.battle_history_dump,
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            assert False, f"An error occurred: {e}"
