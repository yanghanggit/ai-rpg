"""牌库初始化系统：为牌库中 source 为空的卡牌回填来源，并做一次性叙事个人化润色。"""

from functools import partial
from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Dict,
    Final,
    List,
    Tuple,
    Union,
    final,
)

from loguru import logger
from overrides import override
from pydantic import BaseModel

from ..deepseek import ToolDefinition, ToolFunction, agent_loop
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    ActorComponent,
    Card,
    DeathComponent,
    DeckComponent,
    InitializeDeckAction,
)
from ..utils import batch_run_boolean_tasks, prompt_builder


#######################################################################################################################################
@final
class _DeckCardEdit(BaseModel):
    """submit_deck_card 提交的单张卡牌叙事调整（仅 name/description，结构上杜绝改属性/词缀）。"""

    uuid: str
    name: str
    description: str


#######################################################################################################################################
SUBMIT_DECK_CARD_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="submit_deck_card",
        description="提交一张卡牌的叙事调整（仅 name 与 description）。每张卡各调用一次，用 uuid 精确定位目标卡。",
        parameters={
            "type": "object",
            "properties": {
                "uuid": {
                    "type": "string",
                    "description": "目标卡牌的 uuid（来自任务清单，精确区分同名卡）",
                },
                "name": {
                    "type": "string",
                    "description": "改写后的卡牌名",
                },
                "description": {
                    "type": "string",
                    "description": "改写后的叙事描述（叙事锚点：不含数值，不重述字段已确定的效果）",
                },
            },
            "required": ["uuid", "name", "description"],
        },
    )
)


#######################################################################################################################################
FINISH_DECK_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="finish_deck",
        description="全部卡牌均已通过 submit_deck_card 提交后调用，结束本次牌库初始化。",
        parameters={"type": "object", "properties": {}},
    )
)


#######################################################################################################################################
def _handle_submit_deck_card(
    edits: List[_DeckCardEdit],
    uuid: str,
    name: str,
    description: str,
) -> str:
    """处理 submit_deck_card 工具调用：校验并暂存一张卡牌的叙事调整。"""
    assert uuid, "uuid 不能为空"
    edits.append(_DeckCardEdit(uuid=uuid, name=name, description=description))
    logger.info(f"[DeckInitializationSystem] submit_deck_card: {uuid} → {name}")
    return "已记录该卡牌的叙事调整。"


#######################################################################################################################################
def _handle_finish_deck() -> str:
    """处理 finish_deck 工具调用（无参，仅作为终止信号）。"""
    return "已结束牌库初始化。"


#######################################################################################################################################
def _format_card_for_prompt(card: Card) -> str:
    """将单张待润色卡牌格式化为 prompt 片段（机械字段仅作只读上下文）。"""
    lines = [
        f"- uuid: {card.uuid}",
        f"  当前名: {card.name}",
        f"  当前描述: {card.description}",
        f"  功能（只读）: cost={card.cost} damage={card.damage} hit_count={card.hit_count} "
        f"block={card.block} target_type={card.target_type.value} self_target={card.self_target}",
    ]
    if card.on_play_affixes:
        lines.append(f"  on_play_affixes（只读）: {card.on_play_affixes}")
    if card.on_hit_affixes:
        lines.append(f"  on_hit_affixes（只读）: {card.on_hit_affixes}")
    if card.on_turn_end_affixes:
        lines.append(f"  on_turn_end_affixes（只读）: {card.on_turn_end_affixes}")

    flags: List[str] = []
    if not card.playable:
        flags.append(f"playable={card.playable}")
    if card.exhaust:
        flags.append(f"exhaust={card.exhaust}")
    if card.retain:
        flags.append(f"retain={card.retain}")
    if card.ethereal:
        flags.append(f"ethereal={card.ethereal}")
    if card.transferable:
        flags.append(f"transferable={card.transferable}")
    if flags:
        lines.append(f"  特性（只读）: {', '.join(flags)}")
    return "\n".join(lines)


#######################################################################################################################################
@prompt_builder
def _build_deck_init_prompt(entity: Entity, cards: List[Card]) -> str:
    """生成牌库初始化（source 回填后的叙事个人化）提示词。"""
    card_lines = "\n\n".join(_format_card_for_prompt(c) for c in cards)
    return f"""# 任务：初始化你的初始牌库（叙事个人化）

你是「{entity.name}」。你刚被赋予若干张初始卡牌，请依据你的角色设定（见对话开头的系统设定），对这些卡牌的 `name` 与 `description` 做一次叙事个人化润色，使其更像是"你自己"的招式、习惯或随身手段。

## 待润色卡牌清单

{card_lines}

## 硬性约束

- 只允许改写每张卡的 `name` 与 `description`；其余字段（cost/damage/hit_count/block/target_type/self_target/三类词缀/playable/exhaust/retain/ethereal/transferable）一律禁止改动，也禁止在提交中输出。
- `description` 保持"叙事锚点"：不含具体数值，不重述 cost/damage/block 等字段已确定的效果；可自由采用动作、物件、意象、氛围、典故等形态。
- `name` 简洁有辨识度，体现你的个人风格。

## 工作流程

1. 逐一审视每张卡（以 `uuid` 精确定位，避免同名混淆）；
2. 为每张卡各调用一次 `submit_deck_card`（参数：uuid / name / description）；
3. 全部提交完毕后调用 `finish_deck` 结束。"""


#######################################################################################################################################
@final
class DeckInitializationSystem(ReactiveProcessor):
    """响应牌库初始化动作，为触发角色回填 source 并做叙事个人化润色。

    幂等语义：仅处理 `source == ""` 的卡牌，回填后下次自动跳过（不会重复润色）。
    """

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(InitializeDeckAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(InitializeDeckAction)
            and entity.has(ActorComponent)
            and entity.has(DeckComponent)
            and not entity.has(DeathComponent)
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        # 组装待初始化实体的任务（每个实体一个 agent_loop，并发执行）
        pending: List[Tuple[Entity, List[Card], List[_DeckCardEdit]]] = []
        tasks: List[Tuple[str, Coroutine[Any, Any, bool]]] = []

        for entity in entities:

            deck_comp = entity.get(DeckComponent)
            assert deck_comp is not None, f"{entity.name} 缺少 DeckComponent"

            targets = [c for c in deck_comp.cards if not c.source]
            if not targets:
                continue  # 已全部初始化过，幂等跳过

            # 1) 确定性回填 source（不依赖 LLM）
            for card in targets:
                card.source = entity.name
            logger.debug(f"[{entity.name}] 回填 {len(targets)} 张空 source 卡牌的来源")

            # 2) 每实体独立的结果容器与工具处理器
            edits: List[_DeckCardEdit] = []
            handlers: Dict[str, Callable[..., Union[str, Awaitable[str]]]] = {
                "submit_deck_card": partial(_handle_submit_deck_card, edits),
                "finish_deck": _handle_finish_deck,
            }

            # 3) 组装 agent_loop 协程；messages 直接传真实记忆（原地写回）
            coro = agent_loop(
                name=entity.name,
                prompt=_build_deck_init_prompt(entity, targets),
                messages=self._game.get_agent_memory(entity).messages,
                tools=[SUBMIT_DECK_CARD_TOOL, FINISH_DECK_TOOL],
                handlers=handlers,
                terminal_tools=[FINISH_DECK_TOOL],
                max_rounds=6,
            )

            pending.append((entity, targets, edits))
            tasks.append((entity.name, coro))

        if not tasks:
            logger.debug("[DeckInitializationSystem] 无待初始化牌库（source 均已回填）")
            return

        logger.info(
            f"[DeckInitializationSystem] 为 {len(tasks)} 个角色并发初始化牌库..."
        )

        # 4) 并发执行
        outcomes = await batch_run_boolean_tasks(tasks)

        # 5) 应用结果：仅按 uuid 回填 name/description（硬约束，其余字段不触碰）
        for (entity, targets, edits), ok in zip(pending, outcomes):
            by_uuid = {c.uuid: c for c in targets}
            applied = 0
            for edit in edits:
                target_card = by_uuid.get(edit.uuid)
                if target_card is None:
                    logger.warning(
                        f"[DeckInitializationSystem] {entity.name} 提交了未知 uuid "
                        f"{edit.uuid!r}，忽略"
                    )
                    continue
                target_card.name = edit.name
                target_card.description = edit.description
                applied += 1

            logger.info(
                f"[DeckInitializationSystem] {entity.name}: 初始化 {len(targets)} 张"
                f"，应用叙事调整 {applied} 张（agent_loop 成功={ok}）"
            )
