"""出牌 Screen

在此 Screen 内完整走完当前回合的出牌流程：
- 敌人回合：按 Enter 触发 AI 决策并轮询结果
- 玩家回合：输入卡牌编号选牌，再输入目标编号（或 Enter 跳过）完成出牌
- 回合全部出完后，提示 Escape 返回
"""

import asyncio
from enum import auto, Enum
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Input, RichLog, Static

from .server_client import (
    dungeon_combat_play_cards as server_play_cards,
    fetch_dungeon_room,
    fetch_tasks_status,
)
from ..models import TaskStatus


# ─────────────────────────────────────────────────
# 状态机枚举
# ─────────────────────────────────────────────────
class _Phase(Enum):
    LOADING = auto()  # 初始加载回合信息
    ENEMY_TURN = auto()  # 等待用户按 Enter 触发敌人 AI
    SELECT_CARD = auto()  # 等待用户输入卡牌编号
    SELECT_TARGET = auto()  # 等待用户输入目标编号（或 Enter 跳过）
    WAITING = auto()  # 正在等待后端任务完成
    ROUND_DONE = auto()  # 回合已全部完成


# ─────────────────────────────────────────────────
# Screen
# ─────────────────────────────────────────────────
class PlayCardsScreen(Screen[None]):
    """出牌 Screen：引导玩家完成当前回合的完整出牌流程。"""

    CSS = """
    PlayCardsScreen {
        align: center middle;
    }

    #play-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #play-status-bar {
        height: 3;
        dock: bottom;
        padding: 0 1;
        content-align: left middle;
        background: $surface-darken-1;
        color: $text-muted;
    }

    #play-input-row {
        height: 3;
        dock: bottom;
    }

    #play-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #play-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "返回"),
    ]

    _POLL_INTERVAL = 1.0
    _MAX_POLLS = 90

    def __init__(self, user_name: str, game_name: str) -> None:
        super().__init__()
        self._user_name = user_name
        self._game_name = game_name

        # 当前回合状态（在 _load_round 中填充）
        self._action_order: List[str] = []
        self._completed_actors: List[str] = []
        self._hand_cards: List[Dict[str, Any]] = (
            []
        )  # [{name, damage_dealt, block_gain}]
        self._alive_enemy_names: List[str] = []  # 场上存活敌人
        self._alive_ally_names: List[str] = []  # 场上存活友方

        # 选牌流程的临时存储
        self._pending_card_name: Optional[str] = None

        self._phase = _Phase.LOADING

    # ──────────────────────────────────────────────
    # Textual 生命周期
    # ──────────────────────────────────────────────
    def compose(self) -> ComposeResult:
        yield RichLog(id="play-log", highlight=True, markup=True, wrap=True)
        yield Static("", id="play-status-bar")
        with Horizontal(id="play-input-row"):
            yield Static("> ", id="play-prompt")
            yield Input(placeholder="", id="play-input")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(
            "[bold cyan]── 出牌阶段 ─────────────────────────────────────────[/]\n"
            "  逐步完成当前回合所有角色的出牌。[bold]Escape[/] 可随时返回。\n"
        )
        self._set_input_disabled(True)
        self._load_round()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    # ──────────────────────────────────────────────
    # 输入处理
    # ──────────────────────────────────────────────
    @on(Input.Submitted, "#play-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()

        if self._phase == _Phase.ENEMY_TURN:
            # 任意 Enter 触发敌人 AI
            self._trigger_enemy_turn()

        elif self._phase == _Phase.SELECT_CARD:
            self._handle_card_selection(raw)

        elif self._phase == _Phase.SELECT_TARGET:
            self._handle_target_selection(raw)

        elif self._phase == _Phase.ROUND_DONE:
            log = self.query_one(RichLog)
            log.write("[dim]回合已结束，请按 Escape 返回。[/]")

    # ──────────────────────────────────────────────
    # 加载回合信息
    # ──────────────────────────────────────────────
    @work
    async def _load_round(self) -> None:
        log = self.query_one(RichLog)
        log.write("[dim]正在加载回合信息...[/]")
        try:
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            combat = room_resp.room.combat
            rounds = combat.rounds

            if not rounds:
                log.write("[yellow]⚠ 当前没有进行中的回合，请先抽牌。[/]")
                self._phase = _Phase.ROUND_DONE
                self._update_status_bar("无活跃回合")
                return

            cur = rounds[-1]
            self._action_order = list(cur.action_order)
            self._completed_actors = list(cur.completed_actors)

            # 拿场上存活角色（通过 room 内 actors 列表）
            self._alive_enemy_names = [
                a.name
                for a in room_resp.room.stage.actors
                if any(
                    c.component_name == "EnemyComponent"
                    for c in (a.components if hasattr(a, "components") else [])
                )
            ]

            log.write(
                f"[bold yellow]回合 {len(rounds)}[/]  "
                f"行动序列：{' → '.join(self._action_order)}\n"
                f"已出手：{', '.join(self._completed_actors) if self._completed_actors else '（无）'}\n"
            )

            logger.info(
                f"PlayCardsScreen._load_round: action_order={self._action_order} "
                f"completed={self._completed_actors}"
            )
        except Exception as e:
            logger.error(f"PlayCardsScreen._load_round: 加载失败 error={e}")
            log.write(f"[bold red]❌ 加载回合信息失败: {e}[/]")
            self._phase = _Phase.ROUND_DONE
            self._update_status_bar("加载失败")
            return

        self._advance_to_next_actor()

    # ──────────────────────────────────────────────
    # 状态机推进
    # ──────────────────────────────────────────────
    def _advance_to_next_actor(self) -> None:
        """根据 action_order / completed_actors 决定下一步操作。"""
        completed_count = len(self._completed_actors)
        if completed_count >= len(self._action_order):
            self._enter_round_done()
            return

        next_actor = self._action_order[completed_count]
        # 判断是否是玩家角色（包含在 action_order 中且不是纯敌人回合由用户控制的角色）
        # 简单规则：名称中含 "怪物" 或 "敌" 认定为敌人，其余为玩家
        if self._is_enemy(next_actor):
            self._enter_enemy_turn(next_actor)
        else:
            self._enter_select_card(next_actor)

    def _is_enemy(self, actor_name: str) -> bool:
        """简单判断：名称段中含 '怪物' 视为敌人。"""
        parts = actor_name.split(".")
        return any("怪物" in p for p in parts)

    def _enter_enemy_turn(self, actor_name: str) -> None:
        log = self.query_one(RichLog)
        short = actor_name.split(".")[-1]
        log.write(
            f"[bold red]── 敌人回合：{short} ──────────────────────────────────[/]"
        )
        log.write("  按 [bold]Enter[/] 触发 AI 决策...")
        self._phase = _Phase.ENEMY_TURN
        self._update_status_bar(f"敌人 [{short}] 的回合 — 按 Enter 触发 AI 出牌")
        self._set_input_disabled(False)
        self._pending_card_name = None

    def _enter_select_card(self, actor_name: str) -> None:
        log = self.query_one(RichLog)
        short = actor_name.split(".")[-1]
        log.write(
            f"[bold green]── 你的回合：{short} ────────────────────────────────[/]"
        )
        self._fetch_hand_and_show(actor_name)

    def _enter_round_done(self) -> None:
        log = self.query_one(RichLog)
        log.write("\n[bold green]✅ 本回合所有角色已出手，回合结束。[/]")
        log.write("  按 [bold]Escape[/] 返回地下城房间。\n")
        self._phase = _Phase.ROUND_DONE
        self._update_status_bar("回合已结束 — Escape 返回")
        self._set_input_disabled(True)

    # ──────────────────────────────────────────────
    # 手牌加载与显示
    # ──────────────────────────────────────────────
    @work
    async def _fetch_hand_and_show(self, actor_name: str) -> None:
        log = self.query_one(RichLog)
        log.write("[dim]正在加载手牌...[/]")
        try:
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            combat = room_resp.room.combat
            rounds = combat.rounds
            if rounds:
                self._completed_actors = list(rounds[-1].completed_actors)

            # 从 room_resp 中找该 actor 的手牌
            # room_resp.room.stage.actors 有各角色信息
            self._hand_cards = []
            self._alive_enemy_names = []
            for actor in room_resp.room.stage.actors:
                if actor.name == actor_name and hasattr(actor, "hand_cards"):
                    self._hand_cards = [
                        {
                            "name": c.name,
                            "damage_dealt": c.damage_dealt,
                            "block_gain": c.block_gain,
                            "hit_count": c.hit_count,
                        }
                        for c in actor.hand_cards
                    ]
                # 同时收集存活敌人
                if self._is_enemy(actor.name):
                    self._alive_enemy_names.append(actor.name)

            # 若 actor 没有 hand_cards 字段，尝试从 HandComponent 中取
            if not self._hand_cards:
                from .server_client import fetch_entities_details

                details = await fetch_entities_details(
                    self._user_name, self._game_name, [actor_name]
                )
                for entity in details.entities_serialization:
                    if entity.name == actor_name:
                        for comp in entity.components:
                            if comp.name == "HandComponent":
                                self._hand_cards = comp.data.get("cards", [])
                        break

        except Exception as e:
            logger.error(
                f"PlayCardsScreen._fetch_hand_and_show: 加载手牌失败 error={e}"
            )
            log.write(f"[bold red]❌ 加载手牌失败: {e}[/]")
            self._phase = _Phase.ROUND_DONE
            self._update_status_bar("加载失败")
            return

        if not self._hand_cards:
            log.write("[yellow]⚠ 该角色没有手牌，跳过出牌。[/]")
            self._advance_to_next_actor()
            return

        log.write("  [bold]手牌：[/]")
        for i, card in enumerate(self._hand_cards, 1):
            name = card["name"]
            dmg = card["damage_dealt"]
            blk = card["block_gain"]
            hit = card.get("hit_count", 1)
            hit_str = f"x[yellow]{hit}[/]" if hit > 1 else ""
            log.write(
                f"    [bold cyan]{i}.[/] {name}  伤害:[red]{dmg}[/]{hit_str}  格挡:[blue]{blk}[/]"
            )

        self._phase = _Phase.SELECT_CARD
        short = actor_name.split(".")[-1]
        self._update_status_bar(
            f"[{short}] 输入卡牌编号（1-{len(self._hand_cards)}）选牌"
        )
        self._set_input_disabled(False)

    # ──────────────────────────────────────────────
    # 卡牌选择
    # ──────────────────────────────────────────────
    def _handle_card_selection(self, raw: str) -> None:
        log = self.query_one(RichLog)
        if not self._hand_cards:
            log.write("[red]没有可用手牌。[/]")
            return

        card = None
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(self._hand_cards):
                card = self._hand_cards[idx]
        else:
            # 支持输入名称
            for c in self._hand_cards:
                name = c["name"]
                if name == raw:
                    card = c
                    break

        if card is None:
            log.write(
                f"[red]无效输入 '{raw}'，请输入 1-{len(self._hand_cards)} 的数字或卡牌名称。[/]"
            )
            return

        self._pending_card_name = card["name"]
        log.write(f"  已选：[bold cyan]{self._pending_card_name}[/]")

        # 展示可攻击目标
        if self._alive_enemy_names:
            log.write("  [bold]可用目标：[/]")
            for i, name in enumerate(self._alive_enemy_names, 1):
                log.write(f"    [bold cyan]{i}.[/] {name.split('.')[-1]}  ({name})")
            self._phase = _Phase.SELECT_TARGET
            self._update_status_bar(
                f"输入目标编号（1-{len(self._alive_enemy_names)}），或直接 Enter 跳过"
            )
        else:
            # 无目标，直接出牌
            self._phase = _Phase.SELECT_TARGET
            self._submit_play_card(targets=[])

    # ──────────────────────────────────────────────
    # 目标选择
    # ──────────────────────────────────────────────
    def _handle_target_selection(self, raw: str) -> None:
        log = self.query_one(RichLog)
        targets: list[str] = []

        if raw == "":
            # 直接 Enter 跳过，targets=[]
            log.write("  [dim]无目标[/]")
        else:
            if raw.isdigit():
                idx = int(raw) - 1
                if 0 <= idx < len(self._alive_enemy_names):
                    targets = [self._alive_enemy_names[idx]]
                else:
                    log.write(
                        f"[red]无效目标编号 '{raw}'，请输入 1-{len(self._alive_enemy_names)} 或直接 Enter 跳过。[/]"
                    )
                    return
            else:
                # 支持输入名称
                matched = [
                    n
                    for n in self._alive_enemy_names
                    if n == raw or n.split(".")[-1] == raw
                ]
                if matched:
                    targets = [matched[0]]
                else:
                    log.write(f"[red]找不到目标 '{raw}'，请重新输入。[/]")
                    return

        self._submit_play_card(targets=targets)

    # ──────────────────────────────────────────────
    # 出牌提交（玩家）
    # ──────────────────────────────────────────────
    def _submit_play_card(self, targets: list[str]) -> None:
        assert self._pending_card_name is not None
        completed_count = len(self._completed_actors)
        actor_name = self._action_order[completed_count]
        self._do_play_card(actor_name, self._pending_card_name, targets)
        self._pending_card_name = None

    # ──────────────────────────────────────────────
    # 敌人出牌触发
    # ──────────────────────────────────────────────
    def _trigger_enemy_turn(self) -> None:
        completed_count = len(self._completed_actors)
        actor_name = self._action_order[completed_count]
        # 敌人传空卡名，服务端会用 activate_enemy_play_trigger
        self._do_play_card(actor_name, "", [])

    # ──────────────────────────────────────────────
    # 后台出牌任务（玩家 & 敌人共用）
    # ──────────────────────────────────────────────
    @work
    async def _do_play_card(
        self, actor_name: str, card_name: str, targets: list[str]
    ) -> None:
        log = self.query_one(RichLog)
        self._phase = _Phase.WAITING
        self._set_input_disabled(True)

        short = actor_name.split(".")[-1]
        display_card = card_name if card_name else "（AI 自选）"
        log.write(
            f"  [dim]▶ {short} 出牌中：{display_card}  目标：{[t.split('.')[-1] for t in targets] or '无'}[/]"
        )
        logger.info(
            f"PlayCardsScreen._do_play_card: actor={actor_name} card={card_name} targets={targets}"
        )

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
            self._advance_to_next_actor()
            self._set_input_disabled(False)
            return
        except Exception as e:
            log.write(f"[bold red]❌ 出牌请求失败: {e}[/]")
            logger.error(f"_do_play_card: 请求失败 error={e}")
            self._advance_to_next_actor()
            self._set_input_disabled(False)
            return

        # 轮询任务结果
        self._update_status_bar(f"等待 {short} 出牌完成...")
        for _ in range(self._MAX_POLLS):
            await asyncio.sleep(self._POLL_INTERVAL)
            try:
                status_resp = await fetch_tasks_status([task_id])
                if not status_resp.tasks:
                    continue
                record = status_resp.tasks[0]
                if record.status == TaskStatus.COMPLETED:
                    log.write(f"  [green]✓ {short} 出牌完成[/]")
                    logger.info(f"_do_play_card: 任务完成 task_id={task_id}")
                    break
                elif record.status == TaskStatus.FAILED:
                    error_msg = record.error or "未知错误"
                    log.write(f"[bold red]❌ {short} 出牌失败: {error_msg}[/]")
                    logger.error(
                        f"_do_play_card: 任务失败 task_id={task_id} error={error_msg}"
                    )
                    break
            except Exception as e:
                logger.warning(f"_do_play_card: 轮询失败 error={e}")
        else:
            log.write("[bold yellow]⚠️ 等待超时，请检查服务器状态[/]")
            logger.warning(f"_do_play_card: 轮询超时 task_id={task_id}")

        # 重新拉取回合状态，更新 completed_actors
        try:
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            combat = room_resp.room.combat
            if combat.rounds:
                cur = combat.rounds[-1]
                self._completed_actors = list(cur.completed_actors)
                self._action_order = list(cur.action_order)
                # 追加叙事与战斗日志（若有新内容）
                if cur.narrative:
                    log.write(f"  [italic]{cur.narrative[-1]}[/]")
                if cur.combat_log:
                    log.write(f"  [dim]{cur.combat_log[-1]}[/]")
        except Exception as e:
            logger.warning(f"_do_play_card: 刷新回合状态失败 error={e}")

        self._advance_to_next_actor()

    # ──────────────────────────────────────────────
    # 辅助
    # ──────────────────────────────────────────────
    def _set_input_disabled(self, disabled: bool) -> None:
        inp = self.query_one("#play-input", Input)
        inp.disabled = disabled
        if not disabled:
            inp.focus()

    def _update_status_bar(self, text: str) -> None:
        bar = self.query_one("#play-status-bar", Static)
        bar.update(text)
