"""战斗进行中 Screen（CombatOngoingScreen）"""

from typing import List, Tuple, final

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from ..models import CombatRoom, CombatState
from .base import BaseGameScreen
from .combat_common import (
    classify_faction,
    find_stage_of_actor,
    render_combat_summary,
    render_round_info,
    render_stage_actors,
)
from .combat_data_access import (
    get_dungeon_room,
    get_entities_details,
    get_stages_state,
    is_mock_mode,
    resolve_identity,
)
from .combat_deck_view import CombatDeckViewScreen
from .combat_draw_cards import CombatDrawCardsScreen
from .combat_entity_inspect import CombatEntityInspectScreen
from .combat_hand_status_view import CombatHandStatusViewScreen
from .combat_inventory_view import CombatInventoryViewScreen
from .combat_monster_turn import CombatMonsterTurnScreen
from .combat_play_cards import CombatPlayCardsScreen
from .combat_post_combat import CombatPostCombatScreen
from .combat_round_history import CombatRoundHistoryScreen
from .combat_use_consumable import CombatUseConsumableScreen
from .combat_use_gear import CombatUseGearScreen
from .home_main import HomeMainScreen
from .server_client import (
    TaskFailedError,
    dungeon_combat_pass_turn,
    dungeon_combat_retreat,
    watch_task_until_done,
)

BASE_INFO_HEADER = """\
[bold cyan]── 战斗进行中（ONGOING） ──────────────────────────────────────[/]

[dim]核心战斗交互（出牌 / 抽牌 / 使用道具与装备等）开发中；当前显示基础信息。[/]
"""

ONGOING_COMMANDS_MENU = """\
[bold yellow]── 可用操作 ─────────[/]
  [bold green]1[/]  查阅牌组（双方）
  [bold green]2[/]  查阅我方背包
  [bold green]3[/]  查阅指定实体信息（场景 / 角色）
  [bold green]4[/]  查阅历史回合详情"""

HAND_STATUS_COMMAND_LINE = "\n  [bold green]5[/]  查看手牌 + 状态效果"
RETREAT_COMMAND_LINE = "\n  [bold green]6[/]  战斗中撤退"
POST_COMBAT_COMMAND_LINE = "\n  [bold green]6[/]  结束战斗"
DRAW_CARDS_COMMAND_LINE = "\n  [bold green]7[/]  抽牌"
PLAY_CARDS_COMMAND_LINE = "\n  [bold green]7[/]  出牌"
MONSTER_TURN_COMMAND_LINE = "\n  [bold green]7[/]  推进怪物回合"
USE_CONSUMABLE_COMMAND_LINE = "\n  [bold green]8[/]  使用消耗品"
USE_GEAR_COMMAND_LINE = "\n  [bold green]9[/]  使用装备"
PASS_TURN_COMMAND_LINE = "\n  [bold green]10[/] 过牌"


@final
class CombatOngoingScreen(BaseGameScreen):
    """战斗 ONGOING 阶段页面：展示基础信息，并提供查阅型（GET）指令入口。"""

    CSS = """
    CombatOngoingScreen {
        align: center middle;
    }

    #combat-ongoing-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #combat-ongoing-input-row {
        height: 3;
        dock: bottom;
    }

    #combat-ongoing-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #combat-ongoing-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "app.quit", "退出"),
    ]

    def compose(self) -> ComposeResult:
        yield RichLog(id="combat-ongoing-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="combat-ongoing-input-row"):
            yield Static("> ", id="combat-ongoing-prompt")
            yield Input(placeholder="输入指令编号...", id="combat-ongoing-input")

    def on_mount(self) -> None:
        """本页首次挂载时不做任何渲染；实际（重新）渲染统一交给 on_screen_resume
        处理，避免与其重复写入。"""

    def on_screen_resume(self) -> None:
        """本页成为当前活动页面时触发：既覆盖首次进入，也覆盖从子 Screen（如抽牌 /
        查阅手牌等）返回的情况，统一在此处（重新）加载战斗基础信息，确保手牌数、
        抽牌完成标记等随最新状态刷新。"""
        logger.info("CombatOngoingScreen: on_screen_resume，加载/刷新战斗基础信息")
        self._load_base_info()
        self.query_one(Input).focus()

    ########################################################################################################################
    @work
    async def _load_base_info(self) -> None:
        """加载并渲染战斗宏观状态 + 回合信息 + 场景内角色有效属性（含手牌/状态效果数量）。

        注意：每次调用都会先清空 RichLog 再重新写入全部内容，避免从子 Screen（如
        抽牌 / 查阅手牌等）返回触发 on_screen_resume 重新加载时，内容在原有基础上
        不断追加、重复堆叠。"""
        log = self.query_one(RichLog)
        log.clear()
        log.write(BASE_INFO_HEADER)
        logger.info("CombatOngoingScreen._load_base_info: 开始加载")

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
            logger.error(f"CombatOngoingScreen._load_base_info: 加载失败 error={e}")
            log.write(f"[bold red]❌ 加载战斗基础信息失败：{e}[/]")
            return

        render_combat_summary(
            log, combat.name, combat.state.name, combat.result.name, combat.retreated
        )
        render_round_info(log, combat)
        render_stage_actors(log, stage_name, entities_resp.entities_serialization)

        # 1-5 为查阅型（GET）指令，从不改变任何状态，无论战斗处于哪个阶段都可用；
        # 指令 6 依 combat.state 而变：ONGOING 阶段为「战斗中撤退」，
        # COMPLETE / POST_COMBAT 阶段为「结束战斗」，其余阶段不显示；
        # 指令 7 仅在 ONGOING 阶段出现，依最新回合 draw_completed 而变：
        # 未完成为「抽牌」，已完成后依当前 turn 角色阵营而变：
        # 怪物回合为「推进怪物回合」，我方回合为「出牌」；
        # 指令 8（使用消耗品）/ 9（使用装备）仅在 ONGOING 阶段出现，具体前置条件
        # （抽牌是否完成 / 当前 turn 是否为我方 / 每回合限用一次 / 装备是否已被
        # 占用 / 目标能量是否充足等）交由各自 Screen 自身校验并提示，本页不做过滤。
        menu = ONGOING_COMMANDS_MENU
        menu += HAND_STATUS_COMMAND_LINE

        # 准备数据
        latest_round = combat.latest_round

        if combat.state == CombatState.ONGOING:

            # 6（战斗中撤退）仅在 ONGOING 阶段出现
            menu += RETREAT_COMMAND_LINE

            # 7（抽牌 / 出牌 / 推进怪物回合）仅在 ONGOING 阶段出现，依最新回合
            # draw_completed 及当前 turn 角色阵营而变；entities_resp 已在上方拉取，
            # 复用它判断阵营，无需额外发起网络请求。
            if latest_round is not None and not latest_round.draw_completed:
                menu += DRAW_CARDS_COMMAND_LINE
            else:
                entities_map = {e.name: e for e in entities_resp.entities_serialization}
                current_entity = (
                    entities_map.get(latest_round.current_actor)
                    if latest_round is not None and latest_round.current_actor
                    else None
                )
                if classify_faction(current_entity) == "monster":
                    menu += MONSTER_TURN_COMMAND_LINE
                else:
                    menu += PLAY_CARDS_COMMAND_LINE

            # 8/9（使用消耗品 / 使用装备）仅在 ONGOING 阶段出现，具体前置条件交由各自 Screen 自身校验并提示，本页不做过滤
            menu += USE_CONSUMABLE_COMMAND_LINE
            menu += USE_GEAR_COMMAND_LINE

            # 10（过牌）仅在 ONGOING 阶段出现
            menu += PASS_TURN_COMMAND_LINE

        elif combat.state in (CombatState.COMPLETE, CombatState.POST_COMBAT):

            # 6（结束战斗）仅在 COMPLETE / POST_COMBAT 阶段出现
            menu += POST_COMBAT_COMMAND_LINE

        else:
            logger.info(
                "CombatOngoingScreen._load_base_info: 战斗处于其它阶段，隐藏指令 6/7/8/9"
            )

        log.write(menu)

    ########################################################################################################################
    @on(Input.Submitted, "#combat-ongoing-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        if not raw:
            return
        self._dispatch_command(raw)

    ########################################################################################################################
    @work
    async def _dispatch_command(self, raw: str) -> None:
        """指令分发：每次都重新 GET 校验战斗状态与场景花名册，避免使用过期数据做出
        错误判断或跳转。
        """
        log = self.query_one(RichLog)

        # 校验输入合法性
        if raw not in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10"):
            log.write("[red]无效指令，请输入 1-9 或 10[/]")
            return

        try:

            # 获取当前身份信息、战斗房间状态、场景花名册
            _, _, actor_name = resolve_identity(self.game_client)
            room_resp = await get_dungeon_room(self.game_client)
            room = room_resp.room
            assert isinstance(
                room, CombatRoom
            ), f"当前房间不是战斗房间：type={room.type}"
            assert room.type == "combat"
            combat = room.combat
        except Exception as e:
            logger.error(
                f"CombatOngoingScreen._dispatch_command: 校验战斗状态失败 error={e}"
            )
            log.write(f"[bold red]❌ 校验战斗状态失败：{e}[/]")
            return

        # 指令 4 / 6 / 10 不需要场景花名册（participant_names），因此提前在
        # 获取花名册之前处理，避免多做一次不必要的 get_stages_state 请求；
        # 这只是网络请求的先后顺序问题，与「是否会返回本页」无关——
        # 撤退（_do_retreat 成功后 switch_screen 到 HomeScreen）确实不会再回到
        # 本页，但 push_screen(CombatPostCombatScreen()) 与其余 1/2/3/5/7/8/9
        # 一样，目标页支持 Escape 返回，回来后会重新触发 on_screen_resume 刷新。
        if raw == "6":
            if combat.state == CombatState.ONGOING:
                self._do_retreat()
            elif combat.state in (CombatState.COMPLETE, CombatState.POST_COMBAT):
                self.app.push_screen(CombatPostCombatScreen())
            else:
                log.write(f"[yellow]还没有实现。[/]")
            return

        if raw == "4":
            self.app.push_screen(CombatRoundHistoryScreen(combat.rounds))
            return

        # 10（过牌）仅在 ONGOING 阶段、当前回合未结束时可用（详见服务端校验）
        latest_round = combat.latest_round
        assert (
            latest_round is not None
        ), "进入到本阶段就意味着至少有一个回合已开始，latest_round 不应为 None"

        if raw == "10":
            if combat.state == CombatState.ONGOING:
                current_actor = latest_round.current_actor
                assert (
                    current_actor is not None
                ), "当前回合未结束时，current_actor 不应为 None, 服务器来保证"

                self._do_pass_turn(current_actor)

            return

        try:
            stages_resp = await get_stages_state(self.game_client)
            stage_name = find_stage_of_actor(stages_resp.mapping, actor_name)
            assert (
                stage_name is not None
            ), f"未能在场景映射中找到玩家角色所在场景：actor={actor_name}"
            participant_names = list(stages_resp.mapping[stage_name])
        except Exception as e:
            logger.error(
                f"CombatOngoingScreen._dispatch_command: 获取场景花名册失败 error={e}"
            )
            log.write(f"[bold red]❌ 获取场景花名册失败：{e}[/]")
            return

        if raw == "1":
            self.app.push_screen(CombatDeckViewScreen(participant_names))
        elif raw == "2":
            self.app.push_screen(CombatInventoryViewScreen())
        elif raw == "3":
            candidates: List[Tuple[str, str]] = [(stage_name, "场景")]
            candidates.extend((name, "角色") for name in participant_names)
            self.app.push_screen(CombatEntityInspectScreen(candidates))
        elif raw == "5":
            self.app.push_screen(CombatHandStatusViewScreen(participant_names))
        elif raw == "7":
            if combat.state == CombatState.ONGOING:
                if latest_round.draw_completed:
                    # 抽牌完成：需要先判断当前 turn 角色阵营，怪物回合与我方回合
                    # 分别路由到不同的专用页面。
                    current_actor = latest_round.current_actor
                    assert (
                        current_actor is not None
                    ), "抽牌已完成时，current_actor 不应为 None，服务器来保证"
                    actor_entities_resp = await get_entities_details(
                        self.game_client, [current_actor]
                    )
                    current_entity = next(
                        (
                            e
                            for e in actor_entities_resp.entities_serialization
                            if e.name == current_actor
                        ),
                        None,
                    )
                    if classify_faction(current_entity) == "monster":
                        self.app.push_screen(CombatMonsterTurnScreen())
                    else:
                        self.app.push_screen(CombatPlayCardsScreen())
                else:
                    # 没抽牌，就会进入抽牌页，
                    self.app.push_screen(CombatDrawCardsScreen(participant_names))
            else:
                log.write(f"[yellow]还没有实现。[/]")

        elif raw == "8":
            self.app.push_screen(CombatUseConsumableScreen())

        elif raw == "9":
            self.app.push_screen(CombatUseGearScreen())

    ########################################################################################################################
    @work
    async def _do_retreat(self) -> None:
        """战斗中撤退（仅 CombatState.ONGOING 阶段可用）：调用"""
        log = self.query_one(RichLog)

        if is_mock_mode(self.game_client):
            logger.info("CombatOngoingScreen._do_retreat: mock 模式，直接退出应用")
            log.write("[dim]mock 模式：无真实会话可撤退，直接退出应用[/]")
            self.app.exit()
            return

        inp = self.query_one(Input)
        inp.disabled = True
        log.write("[dim]▶ 正在撤退...[/]")

        try:
            user_name, game_name, _ = resolve_identity(self.game_client)
            resp = await dungeon_combat_retreat(user_name, game_name)
            log.write(f"[dim]任务已提交：{resp.task_id}，等待完成...[/]")
            await watch_task_until_done(resp.task_id)
        except TaskFailedError as e:
            logger.error(f"CombatOngoingScreen._do_retreat: 撤退任务失败 error={e}")
            log.write(f"[bold red]❌ 撤退失败：{e}[/]")
            inp.disabled = False
            inp.focus()
            return
        except Exception as e:
            logger.error(f"CombatOngoingScreen._do_retreat: 撤退请求失败 error={e}")
            log.write(f"[bold red]❌ 撤退请求失败：{e}[/]")
            inp.disabled = False
            inp.focus()
            return

        log.write("[bold green]✅ 撤退成功[/]")
        logger.info("CombatOngoingScreen._do_retreat: 撤退成功，返回家园")

        self.app.switch_screen(HomeMainScreen())

    ########################################################################################################################
    @work
    async def _do_pass_turn(self, actor_name: str) -> None:
        """过牌（仅 CombatState.ONGOING 阶段、当前回合抽牌已完成时可用）：本页不
        创建新页面，成功后需要重新加载基础信息，因为当前 turn 的角色已变化。"""
        log = self.query_one(RichLog)

        if is_mock_mode(self.game_client):
            logger.info("CombatOngoingScreen._do_pass_turn: mock 模式，模拟过牌结果")
            log.write(
                f"[bold yellow]\\[mock][/] 已模拟提交过牌请求（未调用真实接口）：{actor_name}"
            )
            log.write("[bold green]✅ 过牌完成[/]")
            self._load_base_info()
            return

        inp = self.query_one(Input)
        inp.disabled = True
        log.write(f"[dim]▶ 正在为 {actor_name} 过牌...[/]")

        try:
            user_name, game_name, _ = resolve_identity(self.game_client)
            resp = await dungeon_combat_pass_turn(user_name, game_name, actor_name)
            log.write(f"[dim]任务已提交：{resp.task_id}，等待完成...[/]")
            await watch_task_until_done(resp.task_id)
        except TaskFailedError as e:
            logger.error(f"CombatOngoingScreen._do_pass_turn: 过牌任务失败 error={e}")
            log.write(f"[bold red]❌ 过牌失败：{e}[/]")
            inp.disabled = False
            inp.focus()
            return
        except Exception as e:
            logger.error(f"CombatOngoingScreen._do_pass_turn: 过牌请求失败 error={e}")
            log.write(f"[bold red]❌ 过牌请求失败：{e}[/]")
            inp.disabled = False
            inp.focus()
            return

        log.write("[bold green]✅ 过牌成功[/]")
        logger.info("CombatOngoingScreen._do_pass_turn: 过牌成功，刷新本页")
        inp.disabled = False
        self._load_base_info()
