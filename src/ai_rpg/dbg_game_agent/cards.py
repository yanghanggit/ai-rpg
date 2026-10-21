"""卡牌调测工具：原型索引查询、显式候选规格解析、纯设计回路（不落存档）。

只服务开发期（`ai-rpg-dbg-agent-game`），不进生产链路。三件事：

- `load_prototype_index` / `filter_entries` / `prototype_slots`：先「查得见」有哪些原型、
  各自开放哪些槽，解决「想指定某个原型却不知道 id」；
- `resolve_prototype_ids` / `resolve_candidate_ids`：把 CLI 的三种指定方式
  （具体 id / 槽位选择器 / 关键词）解析成**具体 id 列表**，再交给
  `GenerateSpoilsAction.prototype_ids` 或 `GenerateDungeonAction.spec.deck_prototype_ids`；
  系统侧因此只需理解「显式 id 列表」这一件事；
- `design_cards_preview`：直接对指定原型跑设计会话并读回结果，**不写游戏状态**，
  用于迭代人设 / 艺术锚点 / 提示词（比 generate-spoils → pick-card 快得多）；
- `rebuild_deck_in_dungeon`：对**已生成副本**里的某只怪物重做牌库，直接改写
  `.dungeons/<副本>.json`——生成期的怪物名是 LLM 之后才产出的，所以「按名字精确控制」
  只能在生成之后做。两种语义：整副重建（用系统的牌库张数）与定点替换（只换指定的几张，
  其余保留）。
"""

import json
import random
from typing import Any, Dict, List, Optional, Sequence

from loguru import logger

from ..game.dbg_game import DBGGame
from ..models import (
    DESIGNABLE_AFFIX_FIELDS,
    Actor,
    Card,
    DeckComponent,
    Dungeon,
    MotifComponent,
)
from ..paths import DUNGEONS_DIR
from ..pgsql import (
    CardPrototypeIndexEntry,
    get_card_prototype,
    list_card_prototype_index,
)
from ..systems.card_common import (
    Candidate,
    design_cards_for_actor,
    materialize_candidate,
    read_actor_system_prompt,
    read_motif_from_components,
)

#######################################################################################################################################
DEFAULT_CARD_TYPE: str = "手牌"


#######################################################################################################################################
def load_prototype_index(
    card_type: str = DEFAULT_CARD_TYPE,
) -> List[CardPrototypeIndexEntry]:
    """拉取一级索引（id / 分类 / name / summary / keywords）。"""
    return list_card_prototype_index(card_type=card_type)


#######################################################################################################################################
def prototype_slots(prototype_id: str) -> List[str]:
    """该原型开放的词缀槽（`card_json` 中非空的 `DESIGNABLE_AFFIX_FIELDS`）。"""
    prototype = get_card_prototype(prototype_id)
    card = Card.model_validate(json.loads(prototype.card_json))
    return [field for field in DESIGNABLE_AFFIX_FIELDS if getattr(card, field)]


#######################################################################################################################################
def filter_entries(
    index: Sequence[CardPrototypeIndexEntry],
    *,
    slot: Optional[str] = None,
    keyword: Optional[str] = None,
) -> List[CardPrototypeIndexEntry]:
    """按槽位 / 关键词过滤索引（保持索引顺序）。

    `slot` 命中「该槽非空的开放槽」，比记 id 更抗原型库变更；`keyword` 是大小写不敏感的
    子串匹配，覆盖 name / summary / archetype / archetype_subtype / keywords。
    """
    entries = list(index)

    if slot:
        entries = [
            entry for entry in entries if slot in prototype_slots(entry["prototype_id"])
        ]

    if keyword:
        needle = keyword.lower()
        entries = [
            entry
            for entry in entries
            if needle
            in " ".join(
                [
                    entry["name"],
                    entry["summary"],
                    entry["archetype"],
                    entry["archetype_subtype"],
                    *entry["keywords"],
                ]
            ).lower()
        ]

    return entries


#######################################################################################################################################
def resolve_prototype_ids(
    *,
    prototype_ids: Sequence[str] = (),
    slot: Optional[str] = None,
    keyword: Optional[str] = None,
    card_type: str = DEFAULT_CARD_TYPE,
    index: Optional[List[CardPrototypeIndexEntry]] = None,
) -> List[str]:
    """把「具体 id + 选择器」解析成 id 列表：显式 id 在前，选择器命中项按索引顺序追加（去重）。

    显式 id 会被校验：必须属于该 `card_type` 的索引（防止把装备原型塞进手牌奖励，
    否则设计契约会错配）。选择器无命中视为错误，而不是静默返回空列表。
    """
    entries = index if index is not None else load_prototype_index(card_type)
    known = {entry["prototype_id"] for entry in entries}

    unknown = [
        prototype_id for prototype_id in prototype_ids if prototype_id not in known
    ]
    if unknown:
        raise ValueError(
            f"未知的 {card_type} 原型 id: {unknown}。用 card-prototypes 命令查看可用 id"
        )

    resolved: List[str] = list(prototype_ids)

    if slot or keyword:
        matched = [
            entry["prototype_id"]
            for entry in filter_entries(entries, slot=slot, keyword=keyword)
        ]
        if not matched:
            raise ValueError(
                f"没有匹配的原型（slot={slot!r}, keyword={keyword!r}, card_type={card_type!r}）"
            )
        resolved.extend(item for item in matched if item not in resolved)

    return resolved


#######################################################################################################################################
def resolve_candidate_ids(
    *,
    count: Optional[int] = None,
    prototype_ids: Sequence[str] = (),
    slot: Optional[str] = None,
    keyword: Optional[str] = None,
    fill_random: bool = False,
    seed: Optional[int] = None,
    card_type: str = DEFAULT_CARD_TYPE,
    index: Optional[List[CardPrototypeIndexEntry]] = None,
) -> List[str]:
    """解析一批候选规格（spoils 候选 / 怪物牌库 / 定点重做）。

    `count` 是**可选的目标张数**：不给就「指定了几张就是几张」——游戏常量（如一副牌的张数）
    只用于未指定时的默认路径，不构成约束。给了 `count` 才做严格数量校验，`fill_random`
    时按 `count` 随机补足（不重复已选项，从 `seed` 派生随机源便于复现）。
    """
    entries = index if index is not None else load_prototype_index(card_type)
    resolved = resolve_prototype_ids(
        prototype_ids=prototype_ids,
        slot=slot,
        keyword=keyword,
        card_type=card_type,
        index=entries,
    )

    if count is None:
        if fill_random:
            raise ValueError(
                "随机补足需要先给出目标张数（--count / --deck-size / --size）"
            )
        return resolved

    if len(resolved) > count:
        raise ValueError(
            f"候选最多 {count} 张，实际指定 {len(resolved)} 张: {resolved}"
        )

    if len(resolved) < count:
        if not fill_random:
            raise ValueError(
                f"需要恰好 {count} 张候选，实际 {len(resolved)} 张；补足剩余随机请加 --fill-random"
            )
        chosen = set(resolved)
        pool = [
            entry["prototype_id"]
            for entry in entries
            if entry["prototype_id"] not in chosen
        ]
        need = count - len(resolved)
        rng = random.Random(seed)
        resolved.extend(rng.sample(pool, k=min(need, len(pool))))
        if len(resolved) != count:
            raise ValueError(
                f"原型库不足以补足候选：需要 {count} 张，只能凑到 {len(resolved)} 张"
            )

    return resolved


#######################################################################################################################################
def format_prototype_line(entry: CardPrototypeIndexEntry) -> str:
    """单行展示一个原型：id / 分类 / 摘要 / 开放槽（供只读命令输出）。"""
    slots = prototype_slots(entry["prototype_id"])
    slot_text = "、".join(slots) if slots else "无（仅 name/description）"
    header = f"{entry['archetype']} / {entry['archetype_subtype']} — {entry['name']}"
    return f"{entry['prototype_id']}\n  {header}\n  {entry['summary']}\n  开放槽: {slot_text}"


#######################################################################################################################################
def read_actor_motif(game: DBGGame, actor_name: str) -> str:
    """读角色挂载的艺术锚点；未挂 `MotifComponent` 时返回空串（与生产侧口径一致）。"""
    entity = game.get_actor_entity(actor_name)
    if entity is None:
        raise ValueError(f"找不到角色: {actor_name}")
    return entity.get(MotifComponent).motif if entity.has(MotifComponent) else ""


#######################################################################################################################################
async def design_cards_preview(
    game: DBGGame,
    *,
    actor_name: str,
    prototype_ids: Sequence[str],
    repeat: int = 1,
    max_rounds: int = 16,
) -> List[List[Candidate]]:
    """对指定原型跑 `repeat` 次设计会话，返回每次的候选卡（**不写游戏状态**）。

    走的是与生产完全相同的入口（`design_cards_for_actor`：世界契约 + 角色设定 +
    艺术锚点），只是不落 `SpoilsComponent` / `DeckComponent`，方便反复调人设与提示词。
    """
    if not prototype_ids:
        raise ValueError("design-cards 至少需要一个原型 id")

    entity = game.get_actor_entity(actor_name)
    if entity is None:
        raise ValueError(f"找不到角色: {actor_name}")

    system_prompt = read_actor_system_prompt(game, entity)
    motif = read_actor_motif(game, actor_name)

    runs: List[List[Candidate]] = []
    for round_index in range(1, max(repeat, 1) + 1):
        candidates: List[Candidate] = []
        for prototype_id in prototype_ids:
            candidate = materialize_candidate(prototype_id, actor_name)
            if candidate is None:
                raise ValueError(f"物化原型 {prototype_id!r} 失败")
            candidates.append(candidate)

        outcome = await design_cards_for_actor(
            game,
            actor_name=actor_name,
            actor_system_prompt=system_prompt,
            candidates=candidates,
            actor_motif=motif,
            max_rounds=max_rounds,
        )
        if not outcome.ok or outcome.designed != len(candidates):
            detail = (
                f"{outcome.designed}/{len(candidates)}（agent_loop 成功={outcome.ok}）"
            )
            logger.warning(
                f"[design-cards] 第 {round_index}/{repeat} 次未完成: {detail}"
            )
        runs.append(candidates)

    return runs


#######################################################################################################################################
def format_designed_card(candidate: Candidate, *, index: int) -> str:
    """单张设计结果的展示文本（含数值与词缀，便于直接对照原型骨架）。"""
    card = candidate.card
    lines: List[str] = [
        f"#{index} {card.name}",
        f"  描述: {card.description}",
        f"  数值: cost={card.cost} damage={card.damage} hit={card.hit_count} block={card.block}",
    ]
    for field in DESIGNABLE_AFFIX_FIELDS:
        affixes = getattr(card, field)
        if affixes:
            lines.append(f"  {field}: {' / '.join(affixes)}")
    return "\n".join(lines)


#######################################################################################################################################
def preview_summary(runs: Sequence[Sequence[Candidate]]) -> Dict[str, Any]:
    """把多次设计结果汇总成一份可打印/可断言的概要（用于观察同一批原型的多样性）。"""
    return {
        "runs": len(runs),
        "names": [[candidate.card.name for candidate in run] for run in runs],
        "affix_counts": [
            sum(
                1
                for candidate in run
                for field in DESIGNABLE_AFFIX_FIELDS
                if getattr(candidate.card, field)
            )
            for run in runs
        ],
    }


#######################################################################################################################################
def find_dungeon_actor(dungeon: Dungeon, actor_name: str) -> Actor:
    """在副本模型里按名字找角色（含所有房间）；找不到即报错并列出可选名字。"""
    for room in dungeon.rooms:
        for actor in room.stage.actors:
            if actor.name == actor_name:
                return actor

    available = [actor.name for room in dungeon.rooms for actor in room.stage.actors]
    raise ValueError(
        f"副本「{dungeon.name}」里没有角色 {actor_name!r}；可选：{available or '（无角色）'}"
    )


#######################################################################################################################################
def _existing_deck_cards(actor: Actor) -> List[Card]:
    """读角色当前牌库（副本模型里的组件数据）；没有牌库时返回空列表。"""
    data = actor.components.get(DeckComponent.__name__)
    if not isinstance(data, dict):
        return []
    return DeckComponent.model_validate(data).cards


def _deck_names(cards: Sequence[Card]) -> str:
    return "、".join(f"{index}.{card.name}" for index, card in enumerate(cards, 1))


def resolve_replacement_indices(
    existing: Sequence[Card], references: Sequence[str]
) -> List[int]:
    """把「序号或卡名」解析成现有牌库里的下标（0 起）。

    序号从 1 开始、按当前牌库顺序；卡名必须唯一，重名时要求改用序号——否则「换哪一张」
    会出现歧义。
    """
    indices: List[int] = []
    for reference in references:
        text = reference.strip()
        if not text:
            raise ValueError("替换目标不能为空")

        if text.isdigit():
            index = int(text) - 1
            if not 0 <= index < len(existing):
                raise ValueError(
                    f"序号 {text} 超出范围：当前牌库 {len(existing)} 张（序号从 1 开始）"
                )
        else:
            hits = [index for index, card in enumerate(existing) if card.name == text]
            if not hits:
                raise ValueError(
                    f"当前牌库里没有「{text}」；现有：{_deck_names(existing) or '（空牌库）'}"
                )
            if len(hits) > 1:
                positions = [hit + 1 for hit in hits]
                raise ValueError(
                    f"当前牌库有多张「{text}」（序号 {positions}），请改用序号指定"
                )
            index = hits[0]

        if index in indices:
            raise ValueError(f"同一张牌被指定了两次（序号 {index + 1}）")
        indices.append(index)

    return indices


#######################################################################################################################################
async def rebuild_deck_in_dungeon(
    game: DBGGame,
    *,
    dungeon_name: str,
    actor_name: str,
    prototype_ids: Sequence[str],
    replace: Sequence[str] = (),
    max_rounds: int = 16,
) -> List[Card]:
    """按给定原型重做某只怪物的牌库，并改写 `.dungeons/<副本>.json`。

    两种语义：

    - `replace` 为空：**整副重建**，牌库张数 = 给定原型数（不限制，`DECK_SIZE` 只是默认路径的张数）；
    - `replace` 非空：**定点替换**，`replace` 与 `prototype_ids` 按顺序一一配对，
      每项是现有牌的 1 起序号或唯一卡名，其余牌原样保留、顺序不变。

    走的是与生产完全相同的设计入口（世界契约 + 怪物扮演设定 + 艺术锚点），只是不经过
    generate-dungeon 的选型阶段——生成期的怪物名由 LLM 产出，因此「按名字精确指定」
    只能在生成之后进行。改写只影响**下一次**「进入副本」，对正在进行的存档无作用。

    设计未全部落地时抛错且**不写文件**，避免半成品覆盖已有牌库。
    """
    if not prototype_ids:
        raise ValueError("至少需要一个原型 id")

    dungeon_path = DUNGEONS_DIR / f"{dungeon_name}.json"
    if not dungeon_path.exists():
        raise ValueError(f"副本文件不存在：{dungeon_path}")

    dungeon = Dungeon.model_validate_json(dungeon_path.read_text(encoding="utf-8"))
    actor = find_dungeon_actor(dungeon, actor_name)

    existing_cards = _existing_deck_cards(actor)
    if replace:
        if len(replace) != len(prototype_ids):
            raise ValueError(
                f"替换目标（{len(replace)} 个）与原型（{len(prototype_ids)} 个）必须一一配对"
            )
        replacement_indices = resolve_replacement_indices(existing_cards, replace)
    else:
        replacement_indices = []

    candidates: List[Candidate] = []
    for prototype_id in prototype_ids:
        candidate = materialize_candidate(prototype_id, actor_name)
        if candidate is None:
            raise ValueError(f"物化原型 {prototype_id!r} 失败，未改写副本文件")
        candidates.append(candidate)

    outcome = await design_cards_for_actor(
        game,
        actor_name=actor_name,
        actor_system_prompt=actor.system_message,
        candidates=candidates,
        actor_motif=read_motif_from_components(actor.components),
        max_rounds=max_rounds,
    )
    if not outcome.ok or outcome.designed != len(candidates):
        raise ValueError(
            f"设计未完成（{outcome.designed}/{len(candidates)}），未改写副本文件"
        )

    designed = [candidate.card for candidate in candidates]
    if replace:
        cards = list(existing_cards)
        for index, card in zip(replacement_indices, designed):
            cards[index] = card
    else:
        cards = designed

    deck = DeckComponent(name=actor.name, cards=cards)
    actor.components = {
        **actor.components,
        DeckComponent.__name__: deck.model_dump(),
    }
    dungeon_path.write_text(dungeon.model_dump_json(indent=4), encoding="utf-8")

    detail = f"替换 {len(designed)} 张" if replace else "整副重建"
    logger.info(
        f"[rebuild-deck] {dungeon.name} / {actor.name}: 牌库已改写（{len(cards)} 张，{detail}）"
    )
    return cards
