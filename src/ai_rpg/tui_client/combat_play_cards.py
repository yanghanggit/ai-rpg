"""出牌流程状态机 Mixin（PlayCardsMixin）。

此模块包含：
- COMBAT_ROOM_MENU：主菜单文本常量
- PlayCardsMixin：出牌流程的 13 个方法（继承自 UseConsumableMixin）

_Phase 枚举已移至 combat_use_consumable，此模块重新导出以保持向后兼容。

PlayCardsMixin 继承 UseConsumableMixin，宿主类只需继承 PlayCardsMixin。
宿主类需提供：
  - self._user_name: str
  - self._game_name: str
  - self.query_one()  ← 由 Textual Widget 提供
  - self._fetch_status()  ← 由 CombatRoomScreen 提供
"""

from typing import Final, List, Optional
import httpx
from loguru import logger
from textual import work
from textual.widgets import Input, RichLog
from .server_client import dungeon_combat_play_cards as server_play_cards
from .server_client import fetch_dungeon_room
from .server_client import (
    fetch_entities_details,
    fetch_stages_state,
    watch_task_until_done,
    TaskFailedError,
)
from ..models import (
    Card,
    CombatResult,
    CombatState,
    HandComponent,
    MonsterComponent,
    PartyMemberComponent,
)
from .combat_room_renderer import (
    write_battlefield_block,
    write_full_entities_block,
    write_hand_table,
)
from .utils import display_name
from .combat_use_consumable import _Phase as _Phase, UseConsumableMixin


COMBAT_ROOM_MENU: Final[
    str
] = """\
[bold yellow]可用操作（输入编号执行）：[/]

[bold cyan]── 战斗 ──────────────────────────────────────[/]
  [bold green]1[/]  战斗开始        执行战斗初始化（首次进入战斗时）
  [bold green]2[/]  抽牌            为全员抽牌
  [bold green]3[/]  出牌            进入出牌界面完成本回合
  [bold green]4[/]  使用消耗品      从背包使用一件消耗品
[bold cyan]── 查看 ──────────────────────────────────────[/]
  [bold green]6[/]  当前战斗状态    房间信息与角色属性
  [bold green]7[/]  回合详情        行动顺序与出手记录
  [bold green]8[/]  查阅牌组        本次地下城各角色历史牌组

[bold cyan]── 离场 ──────────────────────────────────────[/]
  [bold green]9[/]   撤退            在战斗进行中撤退
  [bold green]10[/]  退出战斗        战斗结束后返回游戏主场景

[bold cyan]── 系统 ──────────────────────────────────────[/]
  [bold green]0[/]  显示此菜单
  [bold dim]Escape[/]  提示退出方式

"""


class PlayCardsMixin(UseConsumableMixin):
    """出牌流程状态机（消耗品流程由 UseConsumableMixin 提供）。

    宿主类（CombatRoomScreen）必须在 __init__ 中调用 self._init_play_state()。
    """

    # ──────────────────────────────────────────────
    # 状态字段初始化（由 __init__ 调用）
    # ──────────────────────────────────────────────
    def _init_play_state(self) -> None:
        self._phase: Optional[_Phase] = None
        self._current_actor: Optional[str] = None
        self._selected_card_name: Optional[str] = None
        self._target_candidates: List[str] = []
        self._selected_item_name: Optional[str] = None
        self._consumable_actor: Optional[str] = None

    # ──────────────────────────────────────────────
    # 出牌区域重绘辅助
    # ──────────────────────────────────────────────
    def _clear_to_play_area(self) -> RichLog:
        """清空 log，重写主菜单 + 出牌阶段标题，返回 log。

        三个互斥子状态（选牌 / 出牌等待+结果 / 敌人回合）进入时调用，
        确保各状态独占出牌内容区域，同时保持主菜单始终可见。
        """
        log = self.query_one(RichLog)
        log.clear()
        log.write(COMBAT_ROOM_MENU)
        log.write("[bold cyan]── 出牌阶段 ──[/]")
        return log

    # ──────────────────────────────────────────────
    # 出牌流程入口
    # ──────────────────────────────────────────────
    def _start_play_cards(self) -> None:
        """进入出牌模式：启动 _advance()。"""
        inp = self.query_one(Input)
        inp.disabled = True
        self._phase = _Phase.LOADING
        self._advance()

    # ──────────────────────────────────────────────
    # 核心状态机推进（唯一分发点，不递归）
    # ──────────────────────────────────────────────
    @work
    async def _advance(self) -> None:
        """从服务器拉取最新状态，决定下一个 phase，做一次 phase 进入后 return。"""
        log = self.query_one(RichLog)

        try:
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            combat = room_resp.room.combat
            stage_name = room_resp.room.stage.name
            cur = combat.rounds[-1] if combat.rounds else None
            enemy_names = await self._fetch_play_enemy_names(stage_name)
        except Exception as e:
            logger.warning(f"_advance: 拉取状态失败 error={e}")
            self._enter_round_done()
            return

        if combat.state in (CombatState.COMPLETE, CombatState.POST_COMBAT):
            self._confirm_round_done()
            return

        if cur is None:
            log.write("[yellow]⚠ 当前没有进行中的回合，请输入 [bold]1[/] 抽牌。[/]")
            self._phase = None
            inp = self.query_one(Input)
            inp.placeholder = "输入命令..."
            inp.disabled = False
            inp.focus()
            return

        current_actor = cur.current_turn_actor_name
        round_num = len(combat.rounds)
        action_order = list(
            cur.actor_order_snapshots[-1] if cur.actor_order_snapshots else []
        )
        completed_actors = list(cur.completed_actors)

        if current_actor is None:
            self._enter_round_done()
            return

        try:
            stages_resp = await fetch_stages_state(self._user_name, self._game_name)
            stage_actor_names: List[str] = list(stages_resp.mapping.get(stage_name, []))
            if current_actor not in stage_actor_names:
                stage_actor_names.append(current_actor)
            all_details = await fetch_entities_details(
                self._user_name, self._game_name, stage_actor_names
            )
        except Exception as e:
            logger.error(f"_advance: 加载实体详情失败 error={e}")
            log.write(f"[bold red]❌ 加载战场数据失败: {e}[/]")
            self._phase = None
            inp = self.query_one(Input)
            inp.placeholder = "输入命令..."
            inp.disabled = False
            inp.focus()
            return

        hand_cards: List[Card] = []
        for entity in all_details.entities_serialization:
            if entity.name == current_actor:
                for comp in entity.components:
                    if comp.name == HandComponent.__name__:
                        hand_cards = HandComponent(**comp.data).cards
                break

        if not hand_cards:
            if not cur.completed_actors:
                log.write("[yellow]⚠ 新回合已开始，请输入 [bold]1[/] 抽牌后再出牌。[/]")
                self._phase = None
                inp = self.query_one(Input)
                inp.placeholder = "输入命令..."
                inp.disabled = False
                inp.focus()
            else:
                log.write(
                    f"[yellow]⚠ {display_name(current_actor)} 没有手牌，跳过出牌。[/]"
                )
                self._do_play_card(current_actor, "", [])
            return

        if current_actor in enemy_names:
            self._current_actor = current_actor
            self._enter_enemy_turn(
                current_actor, stage_name, round_num, action_order, completed_actors
            )
            return

        short = display_name(current_actor)
        # 选牌状态：清空重绘（互斥子状态入口）
        log = self._clear_to_play_area()
        # 出牌者实体信息（属性 + 状态效果），不含手牌（手牌由 write_hand_table 渲染）
        actor_entities = [
            e for e in all_details.entities_serialization if e.name == current_actor
        ]
        write_full_entities_block(log, actor_entities, show_hand=False)
        write_hand_table(log, hand_cards, current_actor)
        log.write("")
        log.write("[dim]──────────────────────────────────────────────────[/]")
        self._current_actor = current_actor
        self._phase = _Phase.SELECT_CARD
        self._update_play_status(
            f"[{short}] 输入卡牌编号（1-{len(hand_cards)}）选牌  |  q 返回主菜单"
        )
        inp = self.query_one(Input)
        inp.placeholder = f"1-{len(hand_cards)} 或卡牌名 / q 返回"
        inp.disabled = False
        inp.focus()

    @work
    async def _enter_enemy_turn(
        self,
        actor_name: str,
        stage_name: str,
        round_num: int = 0,
        action_order: Optional[List[str]] = None,
        completed_actors: Optional[List[str]] = None,
    ) -> None:
        # 敌人回合状态：清空重绘（互斥子状态入口）
        log = self._clear_to_play_area()
        short = display_name(actor_name)
        log.write(
            f"[bold red]── 敌人回合：{short} ──────────────────────────────────[/]"
        )
        try:
            stages_resp = await fetch_stages_state(self._user_name, self._game_name)
            actor_names: List[str] = list(stages_resp.mapping.get(stage_name, []))
            details = await fetch_entities_details(
                self._user_name, self._game_name, actor_names
            )
            write_battlefield_block(
                log,
                details.entities_serialization,
                round_num,
                action_order,
                completed_actors,
            )
        except Exception as e:
            logger.warning(f"_enter_enemy_turn: 战场态势加载失败 error={e}")
            log.write("[dim](战场态势加载失败)[/]\n")
        log.write(
            "  按 [bold]Enter[/] 触发 AI 决策  [dim]（输入 q 返回主菜单，下次可继续）[/]"
        )
        self._phase = _Phase.ENEMY_TURN
        self._update_play_status(
            f"敌人 [{short}] 的回合 — 按 Enter 触发 AI 出牌  |  q 返回主菜单"
        )
        inp = self.query_one(Input)
        inp.placeholder = "Enter 触发 AI / q 返回主菜单"
        inp.disabled = False
        inp.focus()

    def _enter_round_done(self) -> None:
        """回合结束：保留 log，等待用户按 Enter 回到主菜单。"""
        log = self.query_one(RichLog)
        self._phase = _Phase.ROUND_DONE
        log.write(
            "\n[bold green]✅ 本回合所有角色已出手，回合结束。[/]"
            "  按 [bold]Enter[/] 回到主菜单。\n"
        )
        inp = self.query_one(Input)
        inp.placeholder = "按 Enter 回到主菜单..."
        inp.disabled = False
        inp.focus()

    def _abort_play_cards(
        self,
        hint: str = "[dim]已中断出牌。输入 [bold]2[/] 可随时继续本回合。[/]",
    ) -> None:
        """中断出牌/消耗品流程，清空状态，回到主菜单命令模式。

        hint: 清屏后写入 log 的提示行；传入不同文本可适配消耗品等非出牌场景。
        """
        self._phase = None
        self._current_actor = None
        self._selected_card_name = None
        self._target_candidates = []
        self._selected_item_name = None
        self._consumable_actor = None
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.placeholder = "输入命令..."
        inp.disabled = False
        inp.focus()
        log.clear()
        log.write(COMBAT_ROOM_MENU)
        log.write(hint + "\n")

    def _confirm_round_done(self) -> None:
        """用户确认后跳回主菜单（清 log、重印菜单）。"""
        log = self.query_one(RichLog)
        self._phase = None
        inp = self.query_one(Input)
        inp.placeholder = "输入命令..."
        inp.disabled = False
        inp.focus()
        log.clear()
        log.write(COMBAT_ROOM_MENU)

    # ──────────────────────────────────────────────
    # 敌方名单辅助（通过 MonsterComponent）
    # ──────────────────────────────────────────────
    async def _fetch_play_enemy_names(self, stage_name: str) -> List[str]:
        stages_resp = await fetch_stages_state(self._user_name, self._game_name)
        actor_names = stages_resp.mapping.get(stage_name, [])
        if not actor_names:
            return []
        details = await fetch_entities_details(
            self._user_name, self._game_name, actor_names
        )
        return [
            e.name
            for e in details.entities_serialization
            if any(c.name == MonsterComponent.__name__ for c in e.components)
        ]

    # ──────────────────────────────────────────────
    # 卡牌选择（@work async）
    # ──────────────────────────────────────────────
    @work
    async def _handle_card_selection(self, raw: str) -> None:
        """实时从服务器拉取手牌、阵营列表，解析选择，进入 SELECT_TARGET 或直接提交出牌。"""
        log = self.query_one(RichLog)
        if self._current_actor is None:
            log.write("[red]错误：当前无出牌角色。[/]")
            return

        actor_name = self._current_actor

        try:
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            stage_name = room_resp.room.stage.name
            stages_resp = await fetch_stages_state(self._user_name, self._game_name)
            stage_actor_names: List[str] = list(stages_resp.mapping.get(stage_name, []))
            if actor_name not in stage_actor_names:
                stage_actor_names.append(actor_name)
            all_details = await fetch_entities_details(
                self._user_name, self._game_name, stage_actor_names
            )
        except Exception as e:
            logger.error(f"_handle_card_selection: 加载失败 error={e}")
            log.write(f"[bold red]❌ 加载手牌失败: {e}[/]")
            self._phase = _Phase.SELECT_CARD
            inp = self.query_one(Input)
            inp.disabled = False
            inp.focus()
            return

        hand_cards: List[Card] = []
        alive_enemies: List[str] = []
        alive_allies: List[str] = []
        for entity in all_details.entities_serialization:
            comp_names = {c.name for c in entity.components}
            if MonsterComponent.__name__ in comp_names:
                alive_enemies.append(entity.name)
            elif PartyMemberComponent.__name__ in comp_names:
                alive_allies.append(entity.name)
            if entity.name == actor_name:
                for comp in entity.components:
                    if comp.name == HandComponent.__name__:
                        hand_cards = HandComponent(**comp.data).cards

        if not hand_cards:
            log.write("[yellow]⚠ 手牌已不存在，重新推进回合...[/]")
            self._advance()
            return

        card: Optional[Card] = None
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(hand_cards):
                card = hand_cards[idx]
        else:
            for c in hand_cards:
                if c.name == raw:
                    card = c
                    break

        if card is None:
            log.write(
                f"[red]无效输入 '{raw}'，请输入 1-{len(hand_cards)} 的数字或卡牌名称。[/]"
            )
            self._phase = _Phase.SELECT_CARD
            inp = self.query_one(Input)
            inp.placeholder = f"1-{len(hand_cards)} 或卡牌名 / q 返回"
            inp.disabled = False
            inp.focus()
            return

        log.write(f"  已选：[bold cyan]{card.name}[/]")
        target_type = card.target_type

        if target_type in ("enemy_all", "ally_all", "self_only"):
            label_map = {
                "enemy_all": "自动命中所有存活敌方",
                "ally_all": "自动命中所有存活友方",
                "self_only": "仅作用于自身",
            }
            log.write(f"  [dim]此卡{label_map[target_type]}[/]")
            self._do_play_card(actor_name, card.name, [])

        elif target_type == "ally_single":
            if alive_allies:
                log.write("  [bold]可选友方目标：[/]")
                for i, name in enumerate(alive_allies, 1):
                    log.write(f"    [bold cyan]{i}.[/] {display_name(name)}")
                self._selected_card_name = card.name
                self._target_candidates = list(alive_allies)
                self._phase = _Phase.SELECT_TARGET
                self._update_play_status(
                    f"输入目标编号（1-{len(alive_allies)}），或直接 Enter 跳过"
                )
                inp = self.query_one(Input)
                inp.placeholder = "编号或 Enter 跳过"
                inp.disabled = False
                inp.focus()
            else:
                log.write("  [dim]无存活友方，直接出牌[/]")
                self._do_play_card(actor_name, card.name, [])

        else:  # enemy_single（默认）
            if alive_enemies:
                log.write("  [bold]可用目标：[/]")
                for i, name in enumerate(alive_enemies, 1):
                    log.write(f"    [bold cyan]{i}.[/] {display_name(name)}")
                self._selected_card_name = card.name
                self._target_candidates = list(alive_enemies)
                self._phase = _Phase.SELECT_TARGET
                self._update_play_status(
                    f"输入目标编号（1-{len(alive_enemies)}），或直接 Enter 跳过"
                )
                inp = self.query_one(Input)
                inp.placeholder = "编号或 Enter 跳过"
                inp.disabled = False
                inp.focus()
            else:
                log.write("  [dim]无存活敌人，直接出牌[/]")
                self._do_play_card(actor_name, card.name, [])

    # ──────────────────────────────────────────────
    # 目标选择
    # ──────────────────────────────────────────────
    def _handle_target_selection(self, raw: str) -> None:
        log = self.query_one(RichLog)
        targets: List[str] = []

        if raw == "":
            log.write("  [dim]无目标[/]")
        else:
            candidates = self._target_candidates
            if raw.isdigit():
                idx = int(raw) - 1
                if 0 <= idx < len(candidates):
                    targets = [candidates[idx]]
                else:
                    log.write(
                        f"[red]无效目标编号 '{raw}'，请输入 1-{len(candidates)} 或直接 Enter 跳过。[/]"
                    )
                    return
            else:
                matched = [n for n in candidates if n == raw or display_name(n) == raw]
                if matched:
                    targets = [matched[0]]
                else:
                    log.write(f"[red]找不到目标 '{raw}'，请重新输入。[/]")
                    return

        assert self._current_actor is not None
        assert self._selected_card_name is not None
        actor = self._current_actor
        card_name = self._selected_card_name
        self._selected_card_name = None
        self._target_candidates = []
        self._do_play_card(actor, card_name, targets)

    # ──────────────────────────────────────────────
    # 敌人出牌触发
    # ──────────────────────────────────────────────
    def _trigger_enemy_turn(self) -> None:
        assert self._current_actor is not None
        self._do_play_card(self._current_actor, "", [])

    # ──────────────────────────────────────────────
    # 后台出牌任务（玩家 & 敌人共用）
    # ──────────────────────────────────────────────
    @work
    async def _do_play_card(
        self, actor_name: str, card_name: str, targets: List[str]
    ) -> None:
        # 出牌等待/结果状态：清空重绘（互斥子状态入口）
        log = self._clear_to_play_area()
        self._phase = _Phase.WAITING
        self.query_one(Input).disabled = True

        short = display_name(actor_name)
        display_card = card_name if card_name else "（AI 自选）"
        log.write(
            f"  [dim]▶ {short} 出牌中：{display_card}  "
            f"目标：{[display_name(t) for t in targets] or '无'}[/]"
        )
        logger.info(
            f"_do_play_card: actor={actor_name} card={card_name} targets={targets}"
        )

        prev_round_idx = -1
        prev_completed_count = 0
        prev_energy = 0
        try:
            pre_room = await fetch_dungeon_room(self._user_name, self._game_name)
            pre_rounds = pre_room.room.combat.rounds
            if pre_rounds:
                prev_round_idx = len(pre_rounds) - 1
                prev_completed_count = len(pre_rounds[-1].completed_actors)
                snapshot = pre_rounds[-1].actor_order_snapshots
                prev_energy = len(snapshot[-1] if snapshot else [])
        except Exception as e:
            logger.warning(f"_do_play_card: 出牌前快照失败 error={e}")

        task_id = ""
        try:
            resp = await server_play_cards(
                self._user_name, self._game_name, actor_name, card_name, targets
            )
            task_id = resp.task_id
            logger.info(f"_do_play_card: 任务已创建 task_id={task_id}")
        except httpx.HTTPStatusError as e:
            try:
                detail = e.response.json().get("detail", str(e))
            except Exception:
                detail = str(e)
            log.write(f"[bold red]❌ 出牌请求失败: {detail}[/]")
            logger.error(f"_do_play_card: 请求失败 error={e}")
            self._advance()
            return
        except Exception as e:
            log.write(f"[bold red]❌ 出牌请求失败: {e}[/]")
            logger.error(f"_do_play_card: 请求失败 error={e}")
            self._advance()
            return

        self._update_play_status(f"等待 {short} 出牌完成...")
        try:
            await watch_task_until_done(task_id, timeout_seconds=90)
            log.write(f"  [green]✓ {short} 出牌完成[/]")
            logger.info(f"_do_play_card: 任务完成 task_id={task_id}")
        except TaskFailedError as e:
            log.write(f"[bold red]❌ {short} 出牌失败: {e}[/]")
            logger.error(f"_do_play_card: 任务失败 task_id={task_id} error={e}")
        except TimeoutError:
            log.write("[bold yellow]⚠️ 等待超时，请检查服务器状态[/]")
            logger.warning(f"_do_play_card: 轮询超时 task_id={task_id}")
        except Exception as e:
            logger.warning(f"_do_play_card: 等待任务失败 error={e}")

        await self._show_play_results(prev_round_idx, prev_completed_count)

        if prev_energy > 0 and prev_round_idx >= 0:
            try:
                post_room = await fetch_dungeon_room(self._user_name, self._game_name)
                post_combat = post_room.room.combat
                post_rounds = post_combat.rounds
                log = self.query_one(RichLog)

                if post_combat.state in (CombatState.COMPLETE, CombatState.POST_COMBAT):
                    result = post_combat.result
                    if result == CombatResult.WIN:
                        log.write("\n[bold green]✅ 战斗胜利！所有敌人已被击败。[/]")
                    elif result == CombatResult.LOSE:
                        log.write("\n[bold red]💀 战斗失败，队伍全员阵亡。[/]")
                    else:
                        log.write("\n[bold yellow]⚔ 战斗已结束。[/]")
                    self._enter_round_done()
                    return

                if (
                    prev_round_idx < len(post_rounds)
                    and len(post_rounds[prev_round_idx].completed_actors) >= prev_energy
                ):
                    self._enter_round_done()
                    return
            except Exception as e:
                logger.warning(f"_do_play_card: 出牌后状态检查失败 error={e}")

        self._advance()

    # ──────────────────────────────────────────────
    # 显示本次出牌的战斗演绎与计算日志
    # ──────────────────────────────────────────────
    async def _show_play_results(
        self, prev_round_idx: int, prev_completed_count: int
    ) -> None:
        if prev_round_idx < 0:
            return
        log = self.query_one(RichLog)
        try:
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            rounds = room_resp.room.combat.rounds
            if prev_round_idx >= len(rounds):
                return
            cur = rounds[prev_round_idx]
            for text in cur.narrative[prev_completed_count:]:
                if text:
                    log.write(f"  [italic]{text}[/]")
            for text in cur.combat_log[prev_completed_count:]:
                if text:
                    log.write(f"  [dim cyan]{text}[/]")
        except Exception as e:
            logger.warning(f"_show_play_results: 加载日志失败 error={e}")

    # ──────────────────────────────────────────────
    # 出牌阶段提示
    # ──────────────────────────────────────────────
    def _update_play_status(self, text: str) -> None:
        if text:
            log = self.query_one(RichLog)
            log.write(f"[dim]{text}[/]")
