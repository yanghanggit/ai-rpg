"""副本牌库组建系统。

位于 AssembleDungeonSystem 之后（Step 4.5）：为已组装副本中的每个 Actor，
从其自己的 agent 视角浏览卡牌原型库、选定恰好 5 张并做叙事润色（name/description），
随后写盘 Dungeon JSON（Step 5 插图暂注释禁用）；任何一步失败均回退默认牌库
（3 攻击 + 2 防御，source 留空交给战斗初始化的 DeckInitializationSystem 回填并润色）。
"""

import json
from functools import partial
from pathlib import Path
from typing import Any, Coroutine, Dict, Final, List, Set, Tuple, final, override
from uuid import uuid4

from loguru import logger
from pydantic import BaseModel

from ..deepseek import ToolDefinition, ToolFunction, agent_loop
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.config import DUNGEONS_DIR
from ..game.dbg_game import DBGGame
from ..models import (
    Actor,
    AssembleDeckAction,
    BUILD_CARD_FIELD_DESCRIPTION,
    Card,
    ChatMessage,
    CombatRoom,
    ComponentSerialization,
    DeckComponent,
    SystemMessage,
    TargetType,
)
from ..pgsql import get_card_prototype, list_card_prototype_index
from ..utils import batch_run_boolean_tasks, prompt_builder


####################################################################################################################################
def _make_attack_card() -> Card:
    """创建基础攻击卡牌（damage 为卡牌自身值，填充牌库时叠加角色 attack）。"""
    return Card(
        name="攻击",
        description="对单个敌人造成直接伤害。",
        on_play_affixes=[],
        playable=True,
        exhaust=False,
        cost=1,
        damage=1,
        hit_count=1,
        block=0,
        target_type=TargetType.SINGLE,
        self_target=False,
    )


def _make_defense_card() -> Card:
    """创建基础防御卡牌（block 为卡牌自身格挡值，填充牌库时叠加角色 defense）。"""
    return Card(
        name="防御",
        description="为自身提供格挡值，持有时提升防御。",
        on_play_affixes=[],
        playable=True,
        exhaust=False,
        cost=1,
        damage=0,
        hit_count=1,
        block=2,
        target_type=TargetType.SINGLE,
        self_target=True,
    )


def make_default_deck_cards() -> List[Card]:
    """默认牌库：3 攻 + 2 防（source 留空，战斗初始化时回填并润色）。"""
    return [
        _make_attack_card(),
        _make_attack_card(),
        _make_attack_card(),
        _make_defense_card(),
        _make_defense_card(),
    ]


####################################################################################################################################
DECK_SIZE: Final[int] = 5  # 每副牌库固定 5 张


####################################################################################################################################
@final
class _DeckCardPick(BaseModel):
    """submit_deck_card 提交的单张卡牌选定（原型 id + 叙事改写）。"""

    prototype_id: str
    name: str
    description: str


####################################################################################################################################
LIST_CARD_PROTOTYPES_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="list_card_prototypes",
        description="纵览全部可选手牌卡牌原型的索引（id / archetype / archetype_subtype / name / summary / keywords），用于组建牌库前建立全局观。",
        parameters={"type": "object", "properties": {}},
    )
)


####################################################################################################################################
GET_CARD_PROTOTYPE_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="get_card_prototype",
        description="按 id 获取某个手牌卡牌原型的完整规格（name / summary / guide / card 全字段），用于精读候选。",
        parameters={
            "type": "object",
            "properties": {
                "prototype_id": {
                    "type": "string",
                    "description": "原型 id，必须来自 list_card_prototypes 返回的索引（如 proto.attack / proto.burst）",
                },
            },
            "required": ["prototype_id"],
        },
    )
)


####################################################################################################################################
SUBMIT_DECK_CARD_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="submit_deck_card",
        description="选定一张卡牌原型并提交其叙事改写（name 与 description）。每张卡各调用一次，用 prototype_id 精确指定原型。",
        parameters={
            "type": "object",
            "properties": {
                "prototype_id": {
                    "type": "string",
                    "description": "所选原型的 id，必须来自 list_card_prototypes 返回的索引",
                },
                "name": {
                    "type": "string",
                    "description": "改写后的卡牌名（叙事、有辨识度，避免教学性命名的原型名）",
                },
                "description": {
                    "type": "string",
                    "description": "改写后的叙事描述（叙事锚点：不含数值，不重述字段已确定的效果）",
                },
            },
            "required": ["prototype_id", "name", "description"],
        },
    )
)


####################################################################################################################################
FINISH_DECK_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="finish_deck",
        description="恰好 5 张卡牌均已通过 submit_deck_card 提交后调用，结束本次牌库组建。",
        parameters={"type": "object", "properties": {}},
    )
)


####################################################################################################################################
def _handle_list_card_prototypes(index: List[Dict[str, object]]) -> str:
    """处理 list_card_prototypes 工具调用：返回缓存的手牌原型索引纵览。"""
    payload = [
        {
            "id": item["prototype_id"],
            "archetype": item["archetype"],
            "archetype_subtype": item["archetype_subtype"],
            "name": item["name"],
            "summary": item["summary"],
            "keywords": item["keywords"],
        }
        for item in index
    ]
    logger.info(
        f"[AssembleDeckSystem] list_card_prototypes 执行: 共 {len(payload)} 个手牌原型"
    )
    return json.dumps(payload, ensure_ascii=False)


####################################################################################################################################
def _handle_get_card_prototype(prototype_id: str) -> str:
    """处理 get_card_prototype 工具调用：按 id 返回完整卡牌原型（含 card 全字段）。"""
    try:
        proto = get_card_prototype(prototype_id)
    except ValueError as e:
        return f"错误：{e}。可用 id 请通过 list_card_prototypes 查询。"
    if proto.card_type != "手牌":
        return f"错误：{prototype_id!r} 不是手牌卡牌原型，可用 id 请通过 list_card_prototypes 查询。"
    logger.info(f"[AssembleDeckSystem] get_card_prototype 执行: {prototype_id}")
    return json.dumps(
        {
            "id": proto.prototype_id,
            "name": proto.name,
            "summary": proto.summary,
            "keywords": json.loads(proto.keywords_json),
            "guide": proto.guide,
            "card": json.loads(proto.card_json),
        },
        ensure_ascii=False,
    )


####################################################################################################################################
def _handle_submit_deck_card(
    valid_ids: Set[str],
    picks: List[_DeckCardPick],
    prototype_id: str,
    name: str,
    description: str,
) -> str:
    """处理 submit_deck_card 工具调用：校验并暂存一张卡牌的选定与叙事改写。"""
    assert name.strip(), "name 不能为空"
    assert description.strip(), "description 不能为空"
    if prototype_id not in valid_ids:
        return (
            f"错误：未知原型 id {prototype_id!r}。"
            "可用 id 请通过 list_card_prototypes 查询。"
        )
    picks.append(
        _DeckCardPick(
            prototype_id=prototype_id,
            name=name.strip(),
            description=description.strip(),
        )
    )
    logger.info(
        f"[AssembleDeckSystem] submit_deck_card: {prototype_id} → {name} "
        f"（已选 {len(picks)}/{DECK_SIZE}）"
    )
    return f"已记录第 {len(picks)} 张卡牌。"


####################################################################################################################################
def _handle_finish_deck() -> str:
    """处理 finish_deck 工具调用（无参，仅作为终止信号）。"""
    return "已结束牌库组建。"


####################################################################################################################################
@prompt_builder
def _build_deck_prompt(actor_name: str) -> str:
    """生成组建初始牌库（选 5 张原型 + 叙事润色）提示词。"""
    return f"""# 任务：为你自己组建初始牌库（恰好 {DECK_SIZE} 张）

你是「{actor_name}」。请依据你的角色设定（见对话开头的系统设定），从卡牌原型库中为自己挑选恰好 {DECK_SIZE} 张卡牌组成初始牌库，并做叙事个人化润色，使其更像「你自己」的招式、习惯或随身手段。

## 卡牌是什么（字段语义，只读背景）

{BUILD_CARD_FIELD_DESCRIPTION}

## 工作流程

1. 调用 `list_card_prototypes` 纵览全部可选手牌原型（含 archetype/archetype_subtype/summary/keywords），结合你的角色设定筛选方向；
2. 对感兴趣的候选，调用 `get_card_prototype` 精读其完整卡牌规格（guide + card 全字段）；
3. 为最终选定的 **恰好 {DECK_SIZE} 张** 卡牌，各调用一次 `submit_deck_card`：
   - `prototype_id`：所选原型的 id；
   - `name`：改写后的卡牌名（体现你的个人风格，避免教学性命名的原型名）；
   - `description`：改写后的叙事描述（叙事锚点：不含数值，不重述字段已确定的效果；可自由采用动作/物件/意象/氛围/典故等形态）。
4. 全部 {DECK_SIZE} 张提交完毕后调用 `finish_deck` 结束。

## 硬性约束

- 只能通过 `prototype_id` 选定原型；卡牌的机械字段（cost/damage/hit_count/block/target_type/self_target/三类词缀/playable/exhaust/retain/ethereal/transferable）一律沿用原型，禁止改动，也禁止在提交中输出。
- `name`/`description` 只做叙事表达，不重述数值与机械效果。
- 可重复选择同一原型（会得到多张独立卡牌）；但提交总量必须恰好为 {DECK_SIZE} 张。"""


####################################################################################################################################
@final
class AssembleDeckSystem(ReactiveProcessor):
    """响应 AssembleDeckAction：为每个角色并发组建牌库，写盘并衔接插图。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(AssembleDeckAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(AssembleDeckAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        assert len(entities) == 1, "同时存在多个 AssembleDeckAction，数据异常"
        entity = entities[0]
        await self._run(entity)

    ####################################################################################################################################
    async def _run(self, entity: Entity) -> None:
        action = entity.get(AssembleDeckAction)
        dungeon = action.dungeon
        dungeon_name = dungeon.name

        combat_actors = [
            actor
            for room in dungeon.rooms
            if isinstance(room, CombatRoom)
            for actor in room.stage.actors
        ]

        logger.info(
            f"[AssembleDeckSystem] Step 4.5 开始: dungeon={dungeon_name}, "
            f"actors={len(combat_actors)}"
        )

        # 预取一次手牌原型索引，供所有并发 agent_loop 共享（list_card_prototypes 返回缓存）
        index: List[Dict[str, object]] = []
        try:
            index = list_card_prototype_index(card_type="手牌")
        except Exception as e:
            logger.error(
                f"[AssembleDeckSystem] 拉取卡牌原型索引失败，全部回退默认牌库: {e}"
            )

        if combat_actors:
            tasks: List[Tuple[str, Coroutine[Any, Any, bool]]] = [
                (actor.name, self._assemble_actor_deck(actor, index))
                for actor in combat_actors
            ]
            outcomes = await batch_run_boolean_tasks(tasks)
            succeeded = sum(1 for ok in outcomes if ok)
            logger.info(
                f"[AssembleDeckSystem] 牌库组建完成: "
                f"{succeeded}/{len(combat_actors)} 个角色使用原型牌库"
            )

        # 写盘最终 Dungeon JSON（含已填充的牌库）
        dungeon_path: Path = DUNGEONS_DIR / f"{dungeon.name}.json"
        dungeon_path.write_text(dungeon.model_dump_json(indent=4), encoding="utf-8")
        logger.info(
            f"[AssembleDeckSystem] Dungeon 已保存: {dungeon_path}\n"
            f"  rooms ({len(dungeon.rooms)}): "
            + ", ".join(
                f"{room.stage.name}({room.stage.actors[0].name if room.stage.actors else 'no actor'})"
                for room in dungeon.rooms
            )
        )

        # 衔接 Step 5：插图生成（暂注释禁用）
        # entity.replace(IllustrateDungeonAction, entity.name, dungeon_name)
        # logger.info(
        #     f"[AssembleDeckSystem] 添加 IllustrateDungeonAction: dungeon={dungeon_name}"
        # )

        # 副本生成完成：重置副本生成系统实体（WorldComponent + DungeonGenerationComponent）
        # 的 agent memory，仅保留首条 system prompt，清除其余全部对话
        agent_memory = self._game.get_agent_memory(entity)
        del agent_memory.messages[1:]
        logger.info(
            f"[AssembleDeckSystem] 已重置 agent memory，保留 {len(agent_memory.messages)} 条消息"
        )
        assert isinstance(
            agent_memory.messages[0], SystemMessage
        ), "首条消息不是 SystemMessage"

    ####################################################################################################################################
    async def _assemble_actor_deck(
        self, actor: Actor, index: List[Dict[str, object]]
    ) -> bool:
        """为单个角色组建并挂载牌库；返回 True 表示使用原型牌库，False 表示回退默认。"""
        try:
            cards, is_fallback = await self._build_cards(actor, index)
        except Exception as e:
            logger.error(
                f"[AssembleDeckSystem] {actor.name} 牌库组建异常，回退默认: {e}"
            )
            cards = make_default_deck_cards()
            is_fallback = True

        actor.components = [
            ComponentSerialization(
                name=DeckComponent.__name__,
                data=DeckComponent(name=actor.name, cards=cards).model_dump(),
            )
        ]
        return not is_fallback

    ####################################################################################################################################
    async def _build_cards(
        self, actor: Actor, index: List[Dict[str, object]]
    ) -> Tuple[List[Card], bool]:
        """让 actor 通过工具自选 5 张原型并润色；返回 (牌列表, 是否回退)。"""
        if not index:
            logger.warning(f"[AssembleDeckSystem] {actor.name} 原型索引为空，回退默认")
            return make_default_deck_cards(), True

        picks: List[_DeckCardPick] = []
        valid_ids: Set[str] = {str(item["prototype_id"]) for item in index}
        # 上下文隔离：以 actor 自己的 system_message 为唯一上下文，
        # 传入全新列表（agent_loop 原地追加），结束后丢弃 → 选完自动「失忆」。
        messages: List[ChatMessage] = [SystemMessage(content=actor.system_message)]

        try:
            ok = await agent_loop(
                name=actor.name,
                prompt=_build_deck_prompt(actor.name),
                messages=messages,
                tools=[
                    LIST_CARD_PROTOTYPES_TOOL,
                    GET_CARD_PROTOTYPE_TOOL,
                    SUBMIT_DECK_CARD_TOOL,
                    FINISH_DECK_TOOL,
                ],
                handlers={
                    "list_card_prototypes": partial(
                        _handle_list_card_prototypes, index
                    ),
                    "get_card_prototype": _handle_get_card_prototype,
                    "submit_deck_card": partial(
                        _handle_submit_deck_card, valid_ids, picks
                    ),
                    "finish_deck": _handle_finish_deck,
                },
                max_rounds=8,
                terminal_tools=[FINISH_DECK_TOOL],
            )
        except Exception as e:
            logger.error(f"[AssembleDeckSystem] {actor.name} agent_loop 异常: {e}")
            return make_default_deck_cards(), True

        if not ok:
            logger.warning(
                f"[AssembleDeckSystem] {actor.name} agent_loop 失败，回退默认"
            )
            return make_default_deck_cards(), True

        if len(picks) != DECK_SIZE:
            logger.warning(
                f"[AssembleDeckSystem] {actor.name} 提交 {len(picks)} 张卡牌"
                f"（需 {DECK_SIZE}），回退默认"
            )
            return make_default_deck_cards(), True

        cards: List[Card] = []
        try:
            for pick in picks:
                proto = get_card_prototype(pick.prototype_id)
                if proto.card_type != "手牌":
                    raise ValueError(
                        f"原型 {pick.prototype_id!r} 不是手牌原型"
                        f"（card_type={proto.card_type!r}）"
                    )
                card = Card.model_validate(json.loads(proto.card_json))
                # 原型 uuid 是共享常量，必须换新；source 回填持有者名（与牌库初始化一致）
                card.uuid = str(uuid4())
                card.source = actor.name
                card.name = pick.name
                card.description = pick.description
                cards.append(card)
        except Exception as e:
            logger.error(f"[AssembleDeckSystem] {actor.name} 物化卡牌失败: {e}")
            return make_default_deck_cards(), True

        logger.info(
            f"[AssembleDeckSystem] {actor.name} 组建原型牌库: "
            + ", ".join(c.name for c in cards)
        )
        return cards, False
