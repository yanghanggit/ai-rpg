"""战斗怪物回合 Screen（CombatMonsterTurnScreen）"""

from dataclasses import dataclass, field
from itertools import zip_longest
from typing import Dict, List, Optional, Tuple, final

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from ..models import CombatRoom, EntitySerialization
from .base import BaseGameScreen
from .combat_common import (
    classify_faction,
    find_stage_of_actor,
    render_stage_actors,
    write_actor_detail,
)
from .combat_data_access import (
    get_dungeon_room,
    get_entities_details,
    get_stages_state,
    is_mock_mode,
    resolve_identity,
)
from .server_client import (
    TaskFailedError,
    dungeon_combat_play_cards,
    watch_task_until_done,
)
from .utils import display_name

BASE_INFO_HEADER = """\
[bold cyan]── 怪物回合 ──────────────────────────────────────[/]

[dim]显示当前 turn 怪物的属性 / 手牌 / 状态效果；出牌/过牌决策由服务端 AI 自动完成。[/]
"""

COMMANDS_MENU_TEMPLATE = """\
[bold yellow]── 可用操作 ─────────[/]
  [bold green]1[/]  推进 {current_actor_label} 的回合（由 AI 自动出牌/过牌）
  [bold green]2[/]  清屏（刷新基础信息 + 清除历史信息）"""

# 竞态防护：进入本页时 current_actor 已不再是怪物（如上一次操作后回合已推进）
STALE_TURN_MENU_TEMPLATE = """\
[bold yellow]── 可用操作 ─────────[/]
  [yellow]当前回合已发生变化，不再是怪物回合，无法在本页推进。[/]
  [bold green]2[/]  清屏（刷新基础信息，请确认后按 Escape 返回）"""


###############################################################################################################################################
@dataclass
class _MonsterTurnSnapshot:
    """怪物回合页从服务器拉取到的战斗快照缓存。"""

    stage_name: Optional[str] = None
    entities_map: Dict[str, EntitySerialization] = field(default_factory=dict)
    entities_serialization: List[EntitySerialization] = field(default_factory=list)
    current_actor: Optional[str] = None
    is_monster_turn: bool = False


@final
class CombatMonsterTurnScreen(BaseGameScreen):
    """战斗 ONGOING 阶段、抽牌已完成后、当前 turn 为怪物时的专用页面：仅提供
    「推进回合」（由服务端 MonsterPrePlaySystem/LLM 自动出牌或过牌）与「清屏」两个
    指令，不提供手动选牌/选目标流程（怪物提交的 card_name / targets 会被服务端
    忽略）。
    """

    CSS = """
    CombatMonsterTurnScreen {
        align: center middle;
    }

    #combat-monster-turn-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #combat-monster-turn-input-row {
        height: 3;
        dock: bottom;
    }

    #combat-monster-turn-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #combat-monster-turn-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "返回"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._snapshot = _MonsterTurnSnapshot()

    def compose(self) -> ComposeResult:
        yield RichLog(
            id="combat-monster-turn-log", highlight=True, markup=True, wrap=True
        )
        with Horizontal(id="combat-monster-turn-input-row"):
            yield Static("> ", id="combat-monster-turn-prompt")
            yield Input(placeholder="输入指令编号...", id="combat-monster-turn-input")

    def on_mount(self) -> None:
        self._load_base_info()
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    ########################################################################################################################
    def _render_menu_text(self) -> str:
        if not self._snapshot.is_monster_turn:
            return STALE_TURN_MENU_TEMPLATE
        current_actor_label = (
            display_name(self._snapshot.current_actor)
            if self._snapshot.current_actor
            else "（无）"
        )
        return COMMANDS_MENU_TEMPLATE.format(current_actor_label=current_actor_label)

    ########################################################################################################################
    async def _fetch_state(self) -> Tuple[bool, str]:
        """重新从服务器拉取最新数据并整体替换 `self._snapshot`，不写日志。返回
        (是否成功, 失败时的错误描述)。

        每次都重新拉取，绝不复用旧快照——怪物出牌会改变场景内任意实体（含自身）
        的属性/状态/手牌，且 current_actor 可能已推进到下一位。
        """
        try:
            _, _, actor_name = resolve_identity(self.game_client)

            room_resp = await get_dungeon_room(self.game_client)
            stages_resp = await get_stages_state(self.game_client)

            room = room_resp.room
            assert isinstance(
                room, CombatRoom
            ), f"当前房间不是战斗房间：type={room.type}"
            assert room.type == "combat"
            combat = room.combat

            stage_name = find_stage_of_actor(stages_resp.mapping, actor_name)
            assert (
                stage_name is not None
            ), f"未能在场景映射中找到玩家角色所在场景：actor={actor_name}"
            actor_names = stages_resp.mapping[stage_name]
            entity_names = [stage_name, *actor_names]

            entities_resp = await get_entities_details(self.game_client, entity_names)
        except Exception as e:
            msg = f"加载怪物回合基础信息失败：{e}"
            logger.error(f"CombatMonsterTurnScreen._fetch_state: {msg}")
            return False, msg

        entities_map = {
            e.name: e
            for e in entities_resp.entities_serialization
            if e.name != stage_name
        }

        latest_round = combat.latest_round
        current_actor = latest_round.current_actor if latest_round is not None else None
        current_entity = entities_map.get(current_actor) if current_actor else None
        # 竞态防护：本页只应在 current_actor 为怪物时使用；若两次拉取之间回合已
        # 推进（如上一次推进已让怪物过牌，轮到下一位），需要如实反映，而不是假装
        # 仍是怪物回合。
        is_monster_turn = classify_faction(current_entity) == "monster"

        self._snapshot = _MonsterTurnSnapshot(
            stage_name=stage_name,
            entities_map=entities_map,
            entities_serialization=entities_resp.entities_serialization,
            current_actor=current_actor,
            is_monster_turn=is_monster_turn,
        )
        return True, ""

    ########################################################################################################################
    @work
    async def _load_base_info(self, clear: bool = True) -> None:
        """`_load_base_info_impl` 的后台 worker 包装（Textual `@work` 会把方法
        调用转换为 `Worker[None]`，无法直接 `await`，故需要这层包装供不需要等待的
        调用点使用）。"""
        await self._load_base_info_impl(clear)

    ########################################################################################################################
    async def _load_base_info_impl(self, clear: bool = True) -> None:
        """重新拉取最新数据并渲染当前 turn 怪物详情 + 场景内角色摘要。

        clear=True（初次进入 / 清屏）：先清空 RichLog 再整体重写；clear=False
        （推进结果反馈之后）：不清空，只在已展示的结果之后追加最新信息。
        """
        log = self.query_one(RichLog)
        if clear:
            log.clear()
            log.write(BASE_INFO_HEADER)
        logger.info(
            f"CombatMonsterTurnScreen._load_base_info_impl: 开始加载 clear={clear}"
        )

        ok, err = await self._fetch_state()
        if not ok:
            log.write(f"[bold red]❌ {err}[/]")
            return

        assert self._snapshot.stage_name is not None
        current_entity = (
            self._snapshot.entities_map.get(self._snapshot.current_actor)
            if self._snapshot.current_actor
            else None
        )

        log.write("[bold yellow]── 当前 turn ─────────────────────────────────[/]")
        if current_entity is not None:
            write_actor_detail(log, current_entity)
        else:
            log.write("  [dim]（无当前出牌角色）[/]")
        log.write("")

        render_stage_actors(
            log, self._snapshot.stage_name, self._snapshot.entities_serialization
        )

        log.write(self._render_menu_text())

    ########################################################################################################################
    @on(Input.Submitted, "#combat-monster-turn-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        if not raw:
            return

        log = self.query_one(RichLog)
        if raw == "2":
            self._load_base_info(clear=True)
            return
        if raw == "1" and self._snapshot.is_monster_turn:
            self._trigger_monster_turn()
            return
        if raw == "1":
            log.write(
                "[yellow]当前回合已发生变化，不再是怪物回合，请输入 2 清屏刷新，"
                "或按 Escape 返回。[/]"
            )
            return
        log.write("[red]无效指令，请输入 1 或 2[/]")

    ########################################################################################################################
    async def _finish_turn_flow(self, inp: Input) -> None:
        """推进流程结束（成功 / 失败 / 中途异常）后的收尾：静默重新拉取最新数据
        替换 `self._snapshot`（不写日志、不追加任何信息），重新启用输入框，交由
        玩家自行按 Escape 返回或输入 2 清屏刷新。"""
        ok, err = await self._fetch_state()
        if not ok:
            logger.warning(
                f"CombatMonsterTurnScreen._finish_turn_flow: 静默刷新缓存失败（{err}），"
                "建议手动输入 2 清屏重试"
            )
        inp.disabled = False
        inp.focus()

    ########################################################################################################################
    @work
    async def _trigger_monster_turn(self) -> None:
        """推进怪物回合：怪物的出牌/过牌决策由服务端 MonsterPrePlaySystem（LLM）
        自动完成，本页提交的 card_name / targets 会被服务端忽略，仅用于触发流程
        推进。结果展示完毕后不再自动刷新，交由玩家自行按 Escape 返回或输入 2 清屏。"""
        log = self.query_one(RichLog)
        actor_name = self._snapshot.current_actor
        assert actor_name is not None, "_trigger_monster_turn: 当前无行动角色"
        assert self._snapshot.is_monster_turn, "_trigger_monster_turn: 当前不是怪物回合"

        inp = self.query_one(Input)
        inp.disabled = True

        actor_label = display_name(actor_name)
        log.write(f"[dim]▶ 正在推进 {actor_label} 的回合（AI 自动决策）...[/]")

        if is_mock_mode(self.game_client):
            logger.info(
                "CombatMonsterTurnScreen._trigger_monster_turn: mock 模式，模拟怪物回合结果"
            )
            log.write(
                "[bold yellow]\\[mock][/] 已模拟提交怪物回合请求（未调用真实接口）。"
            )
            log.write("[bold green]✅ 怪物回合推进完成[/]")
            log.write("[bold yellow]── 回合结果 ─────────────────────────[/]")
            log.write(f"  [dim]战斗：[/] {actor_label} 自动出牌，造成若干伤害。")
            log.write(f"  [dim]叙事：[/] {actor_label}发起了攻击！")
            log.write("")
            await self._finish_turn_flow(inp)
            return

        try:
            user_name, game_name, _ = resolve_identity(self.game_client)

            # 推进前先重新 GET 一次，记录当前回合出牌日志/叙事的基线长度，
            # 便于推进完成后精确 diff 出本次新增的条目。
            baseline_room_resp = await get_dungeon_room(self.game_client)
            baseline_room = baseline_room_resp.room
            assert isinstance(baseline_room, CombatRoom)
            baseline_round = baseline_room.combat.latest_round
            baseline_log_count = (
                len(baseline_round.cards_combat_log) if baseline_round else 0
            )
            baseline_narrative_count = (
                len(baseline_round.cards_narrative) if baseline_round else 0
            )

            # card_name / targets 仅作占位，服务端在识别到 actor 为怪物时会忽略它们，
            # 改由 activate_monster_play_trigger 触发 MonsterPrePlaySystem 自动决策。
            resp = await dungeon_combat_play_cards(
                user_name, game_name, actor_name, "", []
            )
            log.write(f"[dim]任务已提交：{resp.task_id}，等待完成...[/]")
            await watch_task_until_done(resp.task_id)
        except TaskFailedError as e:
            logger.error(
                f"CombatMonsterTurnScreen._trigger_monster_turn: 怪物回合任务失败 error={e}"
            )
            log.write(f"[bold red]❌ 怪物回合推进失败：{e}[/]")
            log.write("")
            await self._finish_turn_flow(inp)
            return
        except Exception as e:
            logger.error(
                f"CombatMonsterTurnScreen._trigger_monster_turn: 怪物回合请求失败 error={e}"
            )
            log.write(f"[bold red]❌ 怪物回合请求失败：{e}[/]")
            log.write("")
            await self._finish_turn_flow(inp)
            return

        log.write("[bold green]✅ 怪物回合推进完成[/]")

        try:
            result_room_resp = await get_dungeon_room(self.game_client)
            result_room = result_room_resp.room
            assert isinstance(result_room, CombatRoom)
            latest_round = result_room.combat.latest_round
        except Exception as e:
            logger.error(
                f"CombatMonsterTurnScreen._trigger_monster_turn: 加载回合结果失败 error={e}"
            )
            log.write(f"[bold red]❌ 加载回合结果失败：{e}[/]")
            log.write("")
            await self._finish_turn_flow(inp)
            return

        if latest_round is not None:
            new_logs = latest_round.cards_combat_log[baseline_log_count:]
            new_narratives = latest_round.cards_narrative[baseline_narrative_count:]
            if new_logs or new_narratives:
                log.write("[bold yellow]── 回合结果 ─────────────────────────[/]")
                for combat_log, narrative in zip_longest(new_logs, new_narratives):
                    log.write(f"  [dim]战斗：[/] {combat_log or '[dim]（无）[/]'}")
                    log.write(f"  [dim]叙事：[/] {narrative or '[dim]（无）[/]'}")
        log.write("")

        await self._finish_turn_flow(inp)
