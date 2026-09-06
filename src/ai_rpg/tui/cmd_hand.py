"""手牌 / 抓牌命令：hand / draw。"""

from typing import List, Tuple

from loguru import logger

from ..models import (
    CharacterStatsComponent,
    DiscardPileComponent,
    DrawPileComponent,
    ExhaustPileComponent,
    HandComponent,
    RoundStatsComponent,
    compute_effective_stats,
    compute_hand_block,
)
from .app import GameClient
from .combat_common import (
    find_component_data,
    find_stage_of_actor,
    role_label,
)
from .combat_data_access import (
    get_entities_details,
    get_stages_state,
    is_mock_mode,
    resolve_identity,
)
from .mock_data import simulate_mock_draw_cards
from .server_client import (
    TaskFailedError,
    dungeon_combat_draw_cards,
    watch_task_until_done,
)
from .utils import display_name, render_card


async def build_hand_text(game_client: GameClient) -> str:
    """双方手牌 + HP + 能量 + 总格挡 + 抽牌/弃牌/消耗堆，返回富文本字符串。"""
    _, _, player_actor = resolve_identity(game_client)
    logger.info(
        f"build_hand_text: mock={is_mock_mode(game_client)} actor={player_actor}"
    )
    try:
        stages_resp = await get_stages_state(game_client)
        stage_name = find_stage_of_actor(stages_resp.mapping, player_actor)
        assert (
            stage_name is not None
        ), f"未能在场景映射中找到玩家角色所在场景：actor={player_actor}"
        participant_names = list(stages_resp.mapping[stage_name])
        if not participant_names:
            return "[yellow]场景内暂无参战者。[/]"
        resp = await get_entities_details(game_client, participant_names)
    except Exception as e:
        logger.error(f"build_hand_text: 加载失败 error={e}")
        return f"[bold red]❌ 加载手牌数据失败: {e}[/]"

    entity_map = {entity.name: entity for entity in resp.entities}

    lines: List[str] = []
    lines.append(
        "[bold cyan]── 双方手牌 / 卡牌状态 ──────────────────────────────────────[/]"
    )
    for name in participant_names:
        entity = entity_map.get(name)
        if entity is None:
            lines.append(f"[yellow]未找到参战角色：{display_name(name)}[/]")
            lines.append("")
            continue

        lines.append(f"{role_label(entity)} [bold]{display_name(name)}[/]")

        stats_data = find_component_data(entity, CharacterStatsComponent.__name__)
        if stats_data is not None:
            stats = compute_effective_stats(CharacterStatsComponent(**stats_data).stats)
            lines.append(f"  HP：[yellow]{stats.hp}/{stats.max_hp}[/]")
        else:
            lines.append("  HP： [dim]（缺少属性组件）[/]")

        round_stats_data = find_component_data(entity, RoundStatsComponent.__name__)
        energy = (
            RoundStatsComponent(**round_stats_data).energy
            if round_stats_data is not None
            else 0
        )
        lines.append(f"  能量： [yellow]{energy}[/]")

        hand_data = find_component_data(entity, HandComponent.__name__)
        hand = HandComponent(**hand_data) if hand_data is not None else None
        lines.append(f"  总格挡： [cyan]{compute_hand_block(hand)}[/]")

        if hand is None:
            lines.append("  手牌： [dim]（无，尚未抓牌）[/]")
        else:
            lines.append(f"  手牌（{len(hand.cards)}）：")
            if not hand.cards:
                lines.append("    [dim]（空）[/]")
            for card in hand.cards:
                lines.append(render_card(card))

        draw_data = find_component_data(entity, DrawPileComponent.__name__)
        if draw_data is not None:
            draw = DrawPileComponent(**draw_data)
            lines.append(f"  抽牌堆： [bold]{len(draw.cards)}[/] 张")
        else:
            lines.append("  抽牌堆： [dim]（无）[/]")

        discard_data = find_component_data(entity, DiscardPileComponent.__name__)
        if discard_data is not None:
            discard = DiscardPileComponent(**discard_data)
            lines.append(f"  弃牌堆： [bold]{len(discard.cards)}[/] 张")
        else:
            lines.append("  弃牌堆： [dim]（无）[/]")

        exhaust_data = find_component_data(entity, ExhaustPileComponent.__name__)
        if exhaust_data is not None:
            exhaust = ExhaustPileComponent(**exhaust_data)
            lines.append(f"  消耗堆： [bold]{len(exhaust.cards)}[/] 张")
        else:
            lines.append("  消耗堆： [dim]（无）[/]")

        lines.append("")

    return "\n".join(lines)


async def draw_cards(game_client: GameClient) -> Tuple[bool, str]:
    """抓牌（开启新回合 + 填手牌），返回 (是否成功, 展示文本)。"""
    if is_mock_mode(game_client):
        logger.info("draw_cards: mock 模式，模拟开新回合并抓牌")
        return simulate_mock_draw_cards()

    user_name, game_name, _ = resolve_identity(game_client)
    logger.info(f"draw_cards: user_name={user_name} game_name={game_name}")
    try:
        resp = await dungeon_combat_draw_cards(user_name, game_name)
        await watch_task_until_done(resp.job_id)
    except TaskFailedError as e:
        logger.error(f"draw_cards: 任务失败 error={e}")
        return False, f"[bold red]❌ 抓牌失败：{e}[/]"
    except Exception as e:
        logger.error(f"draw_cards: 请求失败 error={e}")
        return False, f"[bold red]❌ 抓牌请求失败：{e}[/]"
    return True, "[bold green]✅ 抓牌完成[/]"
