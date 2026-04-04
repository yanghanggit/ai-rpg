"""出牌 Screen

在此 Screen 内完整走完当前回合的出牌流程：
- 敌人回合：按 Enter 触发 AI 决策并轮询结果
- 玩家回合：输入卡牌编号选牌，根据 target_type 决定目标选择方式
- 回合全部出完后，提示 Escape 返回

设计原则：
  不在 Screen 内缓存服务器状态（action_order / completed_actors 等），
  每次需要时通过 API 按需拉取最新数据。
  仅保留当前用户交互阶段的临时 pending 字段（_pending_*）。
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
from textual.widgets import Input, RichLog, Static

from .server_client import (
    dungeon_combat_play_cards as server_play_cards,
    fetch_dungeon_room,
    fetch_entities_details,
    fetch_stages_state,
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

        # 出牌交互临时状态（仅在单次出牌流程内有效，不跨回合缓存服务器数据）
        self._phase = _Phase.LOADING
        self._pending_actor_name: Optional[str] = None  # 当前出牌角色
        self._pending_card_name: Optional[str] = None  # 已选卡牌名
        self._pending_hand_cards: List[Dict[str, Any]] = []  # 当前手牌（供编号解析）
        self._pending_alive_enemies: List[str] = []  # 本次出牌时拉取的存活敌方
        self._pending_alive_allies: List[str] = []  # 本次出牌时拉取的存活友方
        self._pending_target_candidates: List[str] = []  # SELECT_TARGET 阶段的候选列表

    # ──────────────────────────────────────────────
    # Textual 生命周期
    # ──────────────────────────────────────────────
    def compose(self) -> ComposeResult:
        yield RichLog(id="play-log", highlight=True, markup=True, wrap=True)
        yield Static("", id="play-status-bar")
        with Horizontal(id="play-input-row"):
            yield Static("> ", id="play-prompt")
            yield Input(placeholder="", id="play-input")
        # yield Footer()

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
    # 加载回合信息（按需拉取，不缓存）
    # ──────────────────────────────────────────────
    @work
    async def _load_round(self) -> None:
        """从服务器拉取最新回合数据，渲染状态，推进状态机。"""
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
            action_order = list(cur.action_order)
            completed_actors = list(cur.completed_actors)
            stage_name = room_resp.room.stage.name

            # 以 EnemyComponent 组件判断敌方，替代名称硬判断
            enemy_names = await self._fetch_enemy_names(stage_name)

            log.write(
                f"[bold yellow]回合 {len(rounds)}[/]  "
                f"行动序列：{' → '.join(action_order)}\n"
                f"已出手：{', '.join(completed_actors) if completed_actors else '（无）'}\n"
            )
            logger.info(
                f"PlayCardsScreen._load_round: action_order={action_order} "
                f"completed={completed_actors} enemies={enemy_names}"
            )
        except Exception as e:
            logger.error(f"PlayCardsScreen._load_round: 加载失败 error={e}")
            log.write(f"[bold red]❌ 加载回合信息失败: {e}[/]")
            self._phase = _Phase.ROUND_DONE
            self._update_status_bar("加载失败")
            return

        self._advance_to_next_actor(cur.current_actor, enemy_names)

    # ──────────────────────────────────────────────
    # 状态机推进
    # ──────────────────────────────────────────────
    def _advance_to_next_actor(
        self,
        current_actor: Optional[str],
        enemy_names: List[str],
    ) -> None:
        """根据 Round.current_actor 决定下一步。current_actor 为 None 表示回合已结束。"""
        if current_actor is None:
            self._enter_round_done()
            return

        if current_actor in enemy_names:
            self._enter_enemy_turn(current_actor)
        else:
            self._enter_select_card(current_actor)

    def _enter_enemy_turn(self, actor_name: str) -> None:
        log = self.query_one(RichLog)
        short = actor_name.split(".")[-1]
        log.write(
            f"[bold red]── 敌人回合：{short} ──────────────────────────────────[/]"
        )
        log.write("  按 [bold]Enter[/] 触发 AI 决策...")
        self._pending_actor_name = actor_name
        self._phase = _Phase.ENEMY_TURN
        self._update_status_bar(f"敌人 [{short}] 的回合 — 按 Enter 触发 AI 出牌")
        self._set_input_disabled(False)

    def _enter_select_card(self, actor_name: str) -> None:
        log = self.query_one(RichLog)
        short = actor_name.split(".")[-1]
        log.write(
            f"[bold green]── 你的回合：{short} ────────────────────────────────[/]"
        )
        self._pending_actor_name = actor_name
        self._fetch_hand_and_show(actor_name)

    def _enter_round_done(self) -> None:
        log = self.query_one(RichLog)
        log.write("\n[bold green]✅ 本回合所有角色已出手，回合结束。[/]")
        log.write("  按 [bold]Escape[/] 返回地下城房间。\n")
        self._phase = _Phase.ROUND_DONE
        self._update_status_bar("回合已结束 — Escape 返回")
        self._set_input_disabled(True)

    # ──────────────────────────────────────────────
    # 辅助：通过 EnemyComponent 拉取场景存活敌方名单
    # ──────────────────────────────────────────────
    async def _fetch_enemy_names(self, stage_name: str) -> List[str]:
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
            if any(c.name == "EnemyComponent" for c in e.components)
        ]

    # ──────────────────────────────────────────────
    # 手牌加载与显示
    # ──────────────────────────────────────────────
    @work
    async def _fetch_hand_and_show(self, actor_name: str) -> None:
        """按需拉取当前角色手牌及场景角色分类，渲染后进入 SELECT_CARD 阶段。"""
        log = self.query_one(RichLog)
        log.write("[dim]正在加载手牌...[/]")
        try:
            # 1. 拿场景名 + 最新当前行动者（直接用 Round.current_actor）
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            stage_name = room_resp.room.stage.name
            combat = room_resp.room.combat
            cur_round = combat.rounds[-1] if combat.rounds else None

            # 2. 拿场景中所有角色名称（含当前 actor）
            stages_resp = await fetch_stages_state(self._user_name, self._game_name)
            stage_actor_names: List[str] = list(stages_resp.mapping.get(stage_name, []))
            if actor_name not in stage_actor_names:
                stage_actor_names.append(actor_name)

            # 3. 一次性拉取所有角色组件细节
            all_details = await fetch_entities_details(
                self._user_name, self._game_name, stage_actor_names
            )

            # 4. 分类敌友；提取 actor 的手牌
            hand_cards: List[Dict[str, Any]] = []
            alive_enemies: List[str] = []
            alive_allies: List[str] = []
            for entity in all_details.entities_serialization:
                comp_names = {c.name for c in entity.components}
                if "EnemyComponent" in comp_names:
                    alive_enemies.append(entity.name)
                elif "ExpeditionMemberComponent" in comp_names:
                    alive_allies.append(entity.name)
                if entity.name == actor_name:
                    for comp in entity.components:
                        if comp.name == "HandComponent":
                            raw_cards = comp.data.get("cards", [])
                            hand_cards = [
                                c if isinstance(c, dict) else dict(c) for c in raw_cards
                            ]

        except Exception as e:
            logger.error(f"PlayCardsScreen._fetch_hand_and_show: 加载失败 error={e}")
            log.write(f"[bold red]❌ 加载手牌失败: {e}[/]")
            self._phase = _Phase.ROUND_DONE
            self._update_status_bar("加载失败")
            return

        if not hand_cards:
            log.write("[yellow]⚠ 该角色没有手牌，跳过出牌。[/]")
            self._advance_to_next_actor(
                cur_round.current_actor if cur_round else None, alive_enemies
            )
            return

        # 更新 pending 交互字段
        self._pending_hand_cards = hand_cards
        self._pending_alive_enemies = alive_enemies
        self._pending_alive_allies = alive_allies

        _TARGET_LABEL: Dict[str, str] = {
            "enemy_single": "[red]敌方单体[/]",
            "enemy_all": "[red]敌方全体[/]",
            "ally_single": "[green]友方单体[/]",
            "ally_all": "[green]友方全体[/]",
            "self_only": "[cyan]仅自己[/]",
        }
        log.write("  [bold]手牌：[/]")
        for i, card in enumerate(hand_cards, 1):
            name = card.get("name", "?")
            dmg = card.get("damage_dealt", 0)
            blk = card.get("block_gain", 0)
            hit = card.get("hit_count", 1)
            tt = card.get("target_type", "enemy_single")
            hit_str = f"x[yellow]{hit}[/]" if hit > 1 else ""
            tt_str = _TARGET_LABEL.get(str(tt), f"[dim]{tt}[/]")
            log.write(
                f"    [bold cyan]{i}.[/] {name}  "
                f"伤害:[red]{dmg}[/]{hit_str}  格挡:[blue]{blk}[/]  目标:{tt_str}"
            )

        self._phase = _Phase.SELECT_CARD
        short = actor_name.split(".")[-1]
        self._update_status_bar(f"[{short}] 输入卡牌编号（1-{len(hand_cards)}）选牌")
        self._set_input_disabled(False)

    # ──────────────────────────────────────────────
    # 卡牌选择
    # ──────────────────────────────────────────────
    def _handle_card_selection(self, raw: str) -> None:
        log = self.query_one(RichLog)
        if not self._pending_hand_cards:
            log.write("[red]没有可用手牌。[/]")
            return

        card: Optional[Dict[str, Any]] = None
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(self._pending_hand_cards):
                card = self._pending_hand_cards[idx]
        else:
            for c in self._pending_hand_cards:
                if c.get("name") == raw:
                    card = c
                    break

        if card is None:
            log.write(
                f"[red]无效输入 '{raw}'，请输入 1-{len(self._pending_hand_cards)} 的数字或卡牌名称。[/]"
            )
            return

        self._pending_card_name = card.get("name", "")
        target_type = str(card.get("target_type", "enemy_single"))
        log.write(f"  已选：[bold cyan]{self._pending_card_name}[/]")

        # 根据 target_type 决定目标选择流程
        if target_type == "enemy_all":
            log.write("  [dim]此卡自动命中所有存活敌方[/]")
            self._submit_play_card(targets=[])  # 服务端 _resolve_targets 自动填充

        elif target_type == "ally_all":
            log.write("  [dim]此卡自动命中所有存活友方[/]")
            self._submit_play_card(targets=[])

        elif target_type == "self_only":
            log.write("  [dim]此卡仅作用于自身[/]")
            self._submit_play_card(targets=[])  # 服务端自动填入施法者自身

        elif target_type == "ally_single":
            candidates = self._pending_alive_allies
            if candidates:
                log.write("  [bold]可选友方目标：[/]")
                for i, name in enumerate(candidates, 1):
                    log.write(f"    [bold cyan]{i}.[/] {name.split('.')[-1]}  ({name})")
                self._pending_target_candidates = list(candidates)
                self._phase = _Phase.SELECT_TARGET
                self._update_status_bar(
                    f"输入目标编号（1-{len(candidates)}），或直接 Enter 跳过"
                )
            else:
                log.write("  [dim]无存活友方，直接出牌[/]")
                self._submit_play_card(targets=[])

        else:  # enemy_single（默认）
            candidates = self._pending_alive_enemies
            if candidates:
                log.write("  [bold]可用目标：[/]")
                for i, name in enumerate(candidates, 1):
                    log.write(f"    [bold cyan]{i}.[/] {name.split('.')[-1]}  ({name})")
                self._pending_target_candidates = list(candidates)
                self._phase = _Phase.SELECT_TARGET
                self._update_status_bar(
                    f"输入目标编号（1-{len(candidates)}），或直接 Enter 跳过"
                )
            else:
                log.write("  [dim]无存活敌人，直接出牌[/]")
                self._submit_play_card(targets=[])

    # ──────────────────────────────────────────────
    # 目标选择
    # ──────────────────────────────────────────────
    def _handle_target_selection(self, raw: str) -> None:
        log = self.query_one(RichLog)
        targets: list[str] = []

        if raw == "":
            log.write("  [dim]无目标[/]")
        else:
            candidates = self._pending_target_candidates
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
                matched = [n for n in candidates if n == raw or n.split(".")[-1] == raw]
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
        assert self._pending_actor_name is not None
        assert self._pending_card_name is not None
        self._do_play_card(self._pending_actor_name, self._pending_card_name, targets)
        # 清空选牌交互状态
        self._pending_card_name = None
        self._pending_hand_cards = []
        self._pending_alive_enemies = []
        self._pending_alive_allies = []
        self._pending_target_candidates = []

    # ──────────────────────────────────────────────
    # 敌人出牌触发
    # ──────────────────────────────────────────────
    def _trigger_enemy_turn(self) -> None:
        assert self._pending_actor_name is not None
        self._do_play_card(self._pending_actor_name, "", [])

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
            f"  [dim]▶ {short} 出牌中：{display_card}  "
            f"目标：{[t.split('.')[-1] for t in targets] or '无'}[/]"
        )
        logger.info(
            f"PlayCardsScreen._do_play_card: actor={actor_name} card={card_name} targets={targets}"
        )

        # 出牌前记录当前回合快照，以便出牌后精准定位新增日志
        prev_round_idx = -1
        prev_completed_count = 0
        try:
            pre_room = await fetch_dungeon_room(self._user_name, self._game_name)
            pre_rounds = pre_room.room.combat.rounds
            if pre_rounds:
                prev_round_idx = len(pre_rounds) - 1
                prev_completed_count = len(pre_rounds[-1].completed_actors)
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
            await self._reload_and_advance()
            return
        except Exception as e:
            log.write(f"[bold red]❌ 出牌请求失败: {e}[/]")
            logger.error(f"_do_play_card: 请求失败 error={e}")
            await self._reload_and_advance()
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

        # 先显示战斗日志，再推进状态机
        await self._show_play_results(prev_round_idx, prev_completed_count)
        await self._reload_and_advance()

    # ──────────────────────────────────────────────
    # 显示本次出牌的战斗演绎与计算日志
    # ──────────────────────────────────────────────
    async def _show_play_results(
        self, prev_round_idx: int, prev_completed_count: int
    ) -> None:
        """通过出牌前快照的回合索引与出手计数，精准取出本次出手新增的日志条目。

        即使出牌后服务端已创建新回合（rounds[-1] 变为新空回合），
        仍能通过绝对索引 prev_round_idx 定位到正确的历史回合。
        """
        if prev_round_idx < 0:
            return
        log = self.query_one(RichLog)
        try:
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            rounds = room_resp.room.combat.rounds
            if prev_round_idx >= len(rounds):
                return
            cur = rounds[prev_round_idx]
            # 取本次出手新增的 narrative 条目
            new_narratives = cur.narrative[prev_completed_count:]
            for text in new_narratives:
                if text:
                    log.write(f"  [italic]{text}[/]")
            # 取本次出手新增的 combat_log 条目
            new_logs = cur.combat_log[prev_completed_count:]
            for text in new_logs:
                if text:
                    log.write(f"  [dim cyan]{text}[/]")
        except Exception as e:
            logger.warning(f"_show_play_results: 加载日志失败 error={e}")

    # ──────────────────────────────────────────────
    # 出牌后：重新拉取状态并推进状态机
    # ──────────────────────────────────────────────
    async def _reload_and_advance(self) -> None:
        """出牌完成后，从服务器拉取最新回合状态，推进到下一个 actor。"""
        try:
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            combat = room_resp.room.combat
            cur = combat.rounds[-1] if combat.rounds else None

            stage_name = room_resp.room.stage.name
            enemy_names = await self._fetch_enemy_names(stage_name)

        except Exception as e:
            logger.warning(f"_reload_and_advance: 刷新回合状态失败 error={e}")
            self._enter_round_done()
            return

        self._advance_to_next_actor(cur.current_actor if cur else None, enemy_names)

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
