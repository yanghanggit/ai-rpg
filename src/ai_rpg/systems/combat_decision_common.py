"""战斗决策记录的公共层：为一次决策落一条「做了什么 + 为什么」的记忆。

原因由决策主体自己给出；队员侧没有决策推理（由玩家决定），原因为占位句——
形状一致、缺的那部分如实留白，与家园规划里玩家影子轨迹对齐 NPC 规划同一原则。
决策的原始过程不留在记忆里，写完即被这条记录替换。
"""

import json
from typing import Dict, Final, Sequence

from ..models import Card
from ..utils import prompt_builder

#######################################################################################################################################
# 动作类型（决策记录里只有两种：出牌 / 过牌）
#######################################################################################################################################
ACTION_PLAY = "play"
ACTION_PASS = "pass"

# 队伍侧没有真实动机：占位句与空 `mind` 同性质，只为让两侧记忆形状一致。
REASON_PLACEHOLDER = "（这次行动由你自己决定，没有留下理由）"
REASON_MISSING = "（没有给出理由）"

# 出牌前的计算端拦截口径：`playable=False` 的牌不进入结算。
# 决策记录与结算层共用同一判定与同一措辞（`party_combat_decision_system` / `play_cards_action_system` /
# `monster_combat_decision_system`），否则会出现「记忆说打出了、结算说没打」。
UNPLAYABLE_CAUSE: Final[str] = "这张牌不可出牌"


#######################################################################################################################################
def play_blocked_cause(card: Card) -> str:
    """返回出牌前的拦截原因；空串表示放行（决策记录与结算层共用同一口径）。"""
    return "" if card.playable else UNPLAYABLE_CAUSE


#######################################################################################################################################
@prompt_builder
def format_targets(targets: Sequence[str]) -> str:
    """把解析后的目标列表压成「A ×3、B」形式（SPREAD 的命中会重复出现）。"""
    counts: Dict[str, int] = {}
    for name in targets:
        counts[name] = counts.get(name, 0) + 1
    return "、".join(
        name if count == 1 else f"{name} ×{count}" for name, count in counts.items()
    )


#######################################################################################################################################
@prompt_builder
def build_combat_decision_record(
    round_number: int,
    action: str,
    *,
    card_name: str = "",
    targets: Sequence[str] = (),
    reason: str,
    forced_cause: str = "",
    forced_outcome: str = "过牌",
) -> str:
    """生成决策记录正文：`第 N 回合 · 你的行动` + 做了什么（+ 目标）+ 原因。

    ``forced_cause`` 非空表示「本想出牌但被系统拦下」（能量不足 / 不可出牌等），此时正文说明
    原意图与拦截原因，原因行仍用 ``reason``（模型给的理由）。

    ``forced_outcome`` 是「没打出去之后实际发生了什么」，两侧不同：怪物被拦下后会真的过牌；
    队员的牌在结算层被拦下时只是作废（不交出行动权），故传「这次出牌没有发生」。
    """
    lines = [f"# 第 {round_number} 回合 · 你的行动"]

    if action == ACTION_PLAY:
        lines.append(f"你打出了「{card_name}」。")
        lines.append(f"目标：{format_targets(targets)}。")
    elif forced_cause:
        lines.append(
            f"你本想打出「{card_name}」，但{forced_cause}，因此{forced_outcome}。"
        )
    else:
        lines.append("你选择不出牌，直接过牌。")

    lines.append(f"原因：{reason}")
    return "\n".join(lines)


#######################################################################################################################################
def build_combat_decision_tag(
    round_number: int,
    action: str,
    *,
    card_name: str = "",
    targets: Sequence[str] = (),
    reason: str,
    forced: bool,
) -> str:
    """生成 `combat_decision` 标记值：一条决策的结构化事实（供审计与后续检索）。"""
    payload = {
        "round": round_number,
        "action": action,
        "card": card_name,
        "targets": list(targets),
        "reason": reason,
        "forced": forced,
    }
    return json.dumps(payload, ensure_ascii=False)
