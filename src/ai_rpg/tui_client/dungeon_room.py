"""地下城房间 Screen"""

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Input, RichLog, Static

from .server_client import dungeon_exit as server_dungeon_exit
from .server_client import fetch_dungeon_room, fetch_dungeon_state
from .server_client import fetch_entities_details, fetch_stages_state

DUNGEON_ROOM_HEADER = """\
[bold cyan]── 地下城 ──────────────────────────────────────────[/]

[bold]/status[/] 查看当前房间状态，[bold]/exit[/] 退出地下城。
"""

HELP_TEXT = """\
[bold cyan]── 帮助 ──────────────────────────────────────────[/]

[bold]/status[/]    显示当前房间信息及所有角色属性
[bold]/exit[/]      退出地下城，返回地下城总览
"""


class DungeonRoomScreen(Screen[None]):
    """地下城房间 Screen：进入地下城后的主界面，支持状态查询和退出。"""

    CSS = """
    DungeonRoomScreen {
        align: center middle;
    }

    #room-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #room-input-row {
        height: 3;
        dock: bottom;
    }

    #room-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #room-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "suggest_exit", "使用 /exit 退出"),
    ]

    def __init__(self, user_name: str, game_name: str) -> None:
        super().__init__()
        self._user_name = user_name
        self._game_name = game_name

    def compose(self) -> ComposeResult:
        yield RichLog(id="room-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="room-input-row"):
            yield Static("> ", id="room-prompt")
            yield Input(placeholder="输入命令...", id="room-input")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(DUNGEON_ROOM_HEADER)
        self._fetch_status()
        self.query_one(Input).focus()

    def action_suggest_exit(self) -> None:
        log = self.query_one(RichLog)
        log.write("[yellow]请使用 /exit 命令退出地下城。[/]")

    @on(Input.Submitted, "#room-input")
    def handle_command(self, event: Input.Submitted) -> None:
        cmd = event.value.strip().lower()
        event.input.clear()
        log = self.query_one(RichLog)

        if not cmd:
            return

        if cmd == "/help":
            log.write(HELP_TEXT)

        elif cmd == "/status":
            self._fetch_status()

        elif cmd == "/exit":
            self._do_exit()

        else:
            log.write(f"[red]未知命令：{cmd}。输入 /help 查看帮助。[/]")

    @work
    async def _fetch_status(self) -> None:
        """查询地下城状态并渲染当前房间及角色信息。"""
        log = self.query_one(RichLog)
        log.write("[dim]正在查询地下城状态...[/]")
        logger.info(
            f"DungeonRoomScreen._fetch_status: user={self._user_name} game={self._game_name}"
        )

        try:
            # ── 第一段：地下城整体信息（名称、生态、总房间数） ──
            state_resp = await fetch_dungeon_state(self._user_name, self._game_name)
            dungeon = state_resp.dungeon

            log.write(
                f"[bold yellow]── 地下城：{dungeon.name} ──────────────────────────────────────[/]"
            )
            log.write(f"  [bold]生态环境：[/] {dungeon.ecology}")
            log.write(
                f"  [bold]当前房间：[/] {dungeon.current_room_index + 1} / {len(dungeon.rooms)}"
            )
            log.write("")

            logger.info(
                f"DungeonRoomScreen._fetch_status: 地下城状态查询成功 dungeon={dungeon.name}"
            )
        except Exception as e:
            logger.error(
                f"DungeonRoomScreen._fetch_status: 地下城状态查询失败 error={e}"
            )
            log.write(f"[bold red]❌ 查询地下城状态失败: {e}[/]")
            return

        try:
            # ── 第二段：当前房间详情（ECS 运行时数据链） ──

            # Step A：获取当前房间及战斗状态
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            room = room_resp.room
            stage = room.stage
            combat = room.combat

            log.write(
                f"[bold cyan]── 当前房间：{stage.name} ──────────────────────────────────────[/]"
            )

            # Step B：从 stages state 取该场景的运行时 actor 名单
            stages_resp = await fetch_stages_state(self._user_name, self._game_name)
            actor_names = stages_resp.mapping.get(stage.name, [])

            # Step C：逐实体获取运行时 ECS 组件数据
            if actor_names:
                details_resp = await fetch_entities_details(
                    self._user_name, self._game_name, actor_names
                )
                for entity in details_resp.entities_serialization:
                    # 阵营检测
                    faction = "[dim]未知[/]"
                    for comp in entity.components:
                        if comp.name == "AllyComponent":
                            faction = "[bold green]友方[/]"
                            break
                        elif comp.name == "EnemyComponent":
                            faction = "[bold red]敌方[/]"
                            break

                    # 战斗属性
                    stats_comp = next(
                        (
                            c
                            for c in entity.components
                            if c.name == "CombatStatsComponent"
                        ),
                        None,
                    )
                    if stats_comp is not None:
                        stats = stats_comp.data.get("stats", {})
                        hp = stats.get("hp", "?")
                        max_hp = stats.get("max_hp", "?")
                        attack = stats.get("attack", "?")
                        defense = stats.get("defense", "?")
                        status_effects = stats_comp.data.get("status_effects", [])
                        log.write(
                            f"  · {faction} [bold]{entity.name}[/]"
                            f"  HP:[yellow]{hp}/{max_hp}[/]"
                            f"  ATK:[red]{attack}[/]"
                            f"  DEF:[blue]{defense}[/]"
                        )
                        for effect in status_effects:
                            effect_name = (
                                effect.get("name", "?")
                                if isinstance(effect, dict)
                                else str(effect)
                            )
                            log.write(f"    └ 状态：{effect_name}")
                    else:
                        log.write(
                            f"  · {faction} [bold]{entity.name}[/]  [dim](无战斗属性)[/]"
                        )
            else:
                log.write("  [dim]（房间内无角色）[/]")
            log.write("")

            log.write(
                f"  [bold]战斗状态：[/] {combat.state.name}  "
                f"[bold]战斗结果：[/] {combat.result.name}"
            )
            log.write("")

            logger.info(
                f"DungeonRoomScreen._fetch_status: 房间查询成功 room={stage.name}"
            )
        except Exception as e:
            logger.warning(
                f"DungeonRoomScreen._fetch_status: 房间查询失败（可能尚未进入房间）error={e}"
            )
            log.write("[dim]（当前地下城暂无进行中的房间）[/]")

    @work
    async def _do_exit(self) -> None:
        """退出地下城，返回到地下城总览。"""
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True

        log.write("[dim]▶ 正在退出地下城...[/]")
        logger.info(
            f"DungeonRoomScreen._do_exit: user={self._user_name} game={self._game_name}"
        )

        try:
            await server_dungeon_exit(self._user_name, self._game_name)
            log.write("[bold green]✅ 已退出地下城，正在返回...[/]")
            logger.info("DungeonRoomScreen._do_exit: 退出成功")
            self.app.pop_screen()
        except Exception as e:
            logger.error(f"DungeonRoomScreen._do_exit: 退出失败 error={e}")
            log.write(f"[bold red]❌ 退出地下城失败: {e}[/]")
            inp.disabled = False
            inp.focus()
