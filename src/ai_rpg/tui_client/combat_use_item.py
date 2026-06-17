"""道具使用公共基础 Mixin（UseItemMixin）。"""

from abc import abstractmethod
from enum import auto, Enum
from typing import List, Optional, Tuple
from textual.widgets import RichLog
from .base import BaseGameScreen
from .server_client import (
    fetch_dungeon_room,
    fetch_entities_details,
    fetch_stages_state,
)
from ..models import (
    MonsterComponent,
    PartyMemberComponent,
)


# ─────────────────────────────────────────────────────────────────
# 出牌 / 消耗品 / 装备状态机枚举
# ─────────────────────────────────────────────────────────────────
class _Phase(Enum):
    LOADING = auto()  # 初始加载回合信息
    ENEMY_TURN = auto()  # 等待用户按 Enter 触发敌人 AI
    SELECT_CARD = auto()  # 等待用户输入卡牌编号（出牌）
    SELECT_TARGET = auto()  # 等待用户输入出牌目标编号
    WAITING = auto()  # 正在等待后端任务完成
    ROUND_DONE = auto()  # 回合已全部完成
    SELECT_CONSUMABLE = auto()  # 等待用户输入消耗品编号
    SELECT_CONSUMABLE_TARGET = auto()  # 等待用户输入消耗品目标编号
    SELECT_GEAR = auto()  # 等待用户输入装备编号
    SELECT_GEAR_TARGET = auto()  # 等待用户输入装备目标编号


# ─────────────────────────────────────────────────────────────────


class UseItemMixin(BaseGameScreen):
    """所有"使用道具"子流程的公共基类。

    声明 PlayCardsMixin 与 CombatRoomScreen 须实现的抽象接口，
    并提供目标列表拉取等共享工具方法。
    子类 UseConsumableMixin 与 UseGearMixin 均继承此类，互为平级，
    最终由 PlayCardsMixin 通过多继承统一组合。
    """

    # ── 由 CombatRoomScreen 提供 ──────────────────────────────────
    @property
    @abstractmethod
    def _user_name(self) -> str: ...

    @property
    @abstractmethod
    def _game_name(self) -> str: ...

    # ── 由 PlayCardsMixin 提供 ────────────────────────────────────
    @abstractmethod
    def _return_to_menu(
        self,
        hint: str = "[dim]已中断出牌。输入 [bold]3[/] 可随时继续本回合。[/]",
    ) -> None: ...

    @abstractmethod
    def _advance(self) -> object: ...

    @abstractmethod
    def _clear_to_play_area(
        self, title: str = "[bold cyan]── 出牌阶段 ──[/]"
    ) -> RichLog: ...

    @abstractmethod
    def _update_play_status(self, text: str) -> None: ...

    # ── 与出牌流程共享的状态（由 _init_item_state 初始化）────────────
    _phase: Optional[_Phase]
    _target_candidates: List[str]

    # ── 状态初始化（子类通过 super() 协作链式调用）────────────────
    def _init_item_state(self) -> None:
        """初始化道具子流程的共享状态字段。

        UseConsumableMixin 与 UseGearMixin 分别 override 并调用 super()，
        由 PlayCardsMixin._init_play_state() 统一触发，形成链式初始化：
          PlayCardsMixin._init_play_state
            └─ self._init_item_state()
                 └─ UseConsumableMixin._init_item_state (via MRO)
                       └─ super() → UseGearMixin._init_item_state
                             └─ super() → UseItemMixin._init_item_state (终点)
        """
        self._phase: Optional[_Phase] = None
        self._target_candidates: List[str] = []

    # ── 共享工具：获取当前场景的存活敌方与友方 ────────────────────
    async def _fetch_alive_actors(
        self,
    ) -> Tuple[List[str], List[str]]:
        """返回 (alive_enemies, alive_allies) 两个名称列表。

        若拉取失败抛出异常，调用方自行处理。
        """
        room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
        stage_name = room_resp.room.stage.name
        stages_resp = await fetch_stages_state(self._user_name, self._game_name)
        actor_names: List[str] = list(stages_resp.mapping.get(stage_name, []))
        all_details = await fetch_entities_details(
            self._user_name, self._game_name, actor_names
        )
        alive_enemies: List[str] = []
        alive_allies: List[str] = []
        for entity in all_details.entities_serialization:
            comp_names = {c.name for c in entity.components}
            if MonsterComponent.__name__ in comp_names:
                alive_enemies.append(entity.name)
            elif PartyMemberComponent.__name__ in comp_names:
                alive_allies.append(entity.name)
        return alive_enemies, alive_allies
