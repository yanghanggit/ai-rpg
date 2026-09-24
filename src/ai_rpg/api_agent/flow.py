"""由当前世界状态推断「下一步可执行动作」。

这里沉淀的是原本编码在 TUI 各 Screen 路由里的**流程知识**：
- 副本房间路由（开场房间 vs 战斗房间）
- 战斗回合推进（抓牌 → 出牌/过牌 → 换手 → 新回合 → 结算）
- 战后顺序（收取战利品 → 推进关卡 → 退出）
- 开场房间顺序（初始化 → 生成奖励 → 领卡 → 推进）

输入是 :func:`ai_rpg.api_agent.status.build_status` 产出的快照 dict，
输出是建议的 CLI 子命令字符串列表（含 home/dungeon/opening/combat 组前缀，
可直接作为 ``ai_rpg/cli/agent_api.py``（入口 ``ai-rpg-agent-api``）的参数；不含全局的 --user/--game）。
代理据此决策，但仍以服务端的实际校验为准。
"""

from typing import Any, Dict, List


########################################################################################################################
def _hand_of(status: Dict[str, Any], actor_name: str) -> List[Dict[str, Any]]:
    for entity in status.get("entities", []):
        if entity.get("name") == actor_name:
            return list(entity.get("hand", []))
    return []


########################################################################################################################
def suggest_actions(status: Dict[str, Any]) -> List[str]:
    """返回建议的下一步命令列表（模板含占位符，由代理按实际状态填充）。"""
    mode = status.get("mode")
    dungeon = status.get("dungeon") or {}
    actions: List[str] = []

    if mode == "home":
        actions.append("home advance --actor <actor>")
        actions.append("home speak --target <actor> --content <text>")
        actions.append("home switch-stage --stage <stage_name>")
        actions.append("home generate-dungeon")
        actions.append("home enter-dungeon --dungeon <dungeon_name>")
        actions.append("dungeon-list")
        actions.append("blueprint-list")
        actions.append("home roster-add --member <actor>")
        actions.append("home roster-remove --member <actor>")
        actions.append("home item-to-inventory --item <item>")
        actions.append("home item-to-storage --item <item>")
        actions.append("home craft-consumable --material <m> [--material <m> ...]")
        actions.append("home craft-gear --material <m> [--material <m> ...]")
        actions.append("home craft-costume --material <m> [--material <m> ...]")
        actions.append("home wear-costume --item <costume> --target <actor>")
        actions.append("home remove-costume --target <actor>")
        actions.append("compact --target <entity>")

    elif mode == "dungeon":
        room_type = dungeon.get("room_type")

        if room_type == "opening":
            opening = dungeon.get("opening") or {}
            if not opening.get("initialized"):
                actions.append("opening init")
            elif not opening.get("spoils_generated"):
                actions.append("opening generate-spoils")
            else:
                for entry in opening.get("by_actor", []):
                    for card in entry.get("candidate_cards", []):
                        actions.append(
                            f"opening pick-spoils-card --actor {entry['actor']} "
                            f"--card {card.get('name')}"
                        )
                actions.append("dungeon advance-stage")
            actions.append("dungeon exit")

        elif room_type == "combat":
            combat = status.get("combat") or {}
            state = combat.get("state")

            if state in ("NONE", "INITIALIZATION"):
                actions.append("combat init")

            elif state == "ONGOING":
                rnd_obj = combat.get("round")
                rnd: Dict[str, Any] = rnd_obj if isinstance(rnd_obj, dict) else {}
                need_draw = (
                    not rnd
                    or not rnd.get("draw_completed")
                    or rnd.get("is_completed")
                    or not rnd.get("current_actor")
                )
                if need_draw:
                    actions.append("combat draw-cards")
                else:
                    current_actor = str(rnd["current_actor"])
                    hand = _hand_of(status, current_actor)
                    if hand:
                        for card in hand:
                            if not card.get("playable", True):
                                continue
                            target = (
                                "" if card.get("self_target") else " --target <entity>"
                            )
                            actions.append(
                                f"combat play-cards --actor {current_actor} "
                                f"--card {card.get('name')}{target}"
                            )
                    else:
                        actions.append(
                            f"combat play-cards --actor {current_actor} "
                            f"--card <card> [--target <entity>]"
                        )
                    actions.append(f"combat pass-turn --actor {current_actor}")
                    actions.append(
                        "combat use-consumable --item <item> [--target <entity>]"
                    )
                    actions.append("combat equip-gear --item <item>")
                    actions.append("combat retreat")

            elif state in ("COMPLETE", "POST_COMBAT"):
                actions.append("combat collect-loot")
                has_next = dungeon.get("current_room_index", -1) + 1 < dungeon.get(
                    "room_count", 1
                )
                if has_next:
                    actions.append("dungeon advance-stage")
                actions.append("dungeon exit")

    actions.append("status")
    return actions
