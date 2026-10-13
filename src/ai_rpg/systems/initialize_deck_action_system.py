"""牌库初始化系统：响应 InitializeDeckAction，为尚未初始化的卡牌做一次性叙事个人化润色。

「未初始化」判据为 `source == ""`，而 `source` 由**本流程**在牌库初始化时确定性回填
（不依赖 LLM）：先回填 source，再做叙事润色，故润色后再次触发会自动幂等跳过。设计路径
（assemble_deck / spoils / 装备物化）已显式设置 source，直接跳过；蓝图初始牌库与兜底牌单
则由本流程润色。

时序：在 pipeline 中本系统先于 FillDrawPileSystem 执行，保证 source 回填/润色发生在
抽牌堆复制之前。
"""

from functools import partial
from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Dict,
    Final,
    List,
    Set,
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
    BUILD_CARD_FIELD_DESCRIPTION,
    ActorComponent,
    Card,
    DeathComponent,
    DeckComponent,
    InitializeDeckAction,
    render_labeled_str_list,
)
from ..utils import batch_run_boolean_tasks, prompt_builder


#######################################################################################################################################
@final
class _DeckCardEdit(BaseModel):
    """submit_deck_polish 提交的单张卡牌叙事调整（仅 name/description，结构上杜绝改属性/词缀）。"""

    uuid: str
    name: str
    description: str


#######################################################################################################################################
SUBMIT_POLISH_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="submit_deck_polish",
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
FINISH_POLISH_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="finish_deck_polish",
        description="全部卡牌均已通过 submit_deck_polish 提交后调用，结束本次牌库初始化。",
        parameters={"type": "object", "properties": {}},
    )
)


#######################################################################################################################################
def _handle_submit_polish(
    valid_uuids: Set[str],
    edits: List[_DeckCardEdit],
    uuid: str,
    name: str,
    description: str,
) -> str:
    """处理 submit_deck_polish：校验 uuid 与叙事字段，不合法则返回错误让 agent 修正重提。"""
    if uuid not in valid_uuids:
        return f"错误：未知 uuid {uuid!r}。请使用任务清单中给出的 uuid。"
    if not name.strip():
        return "错误：name 不能为空。请修正后重新调用 submit_deck_polish。"
    if not description.strip():
        return "错误：description 不能为空。请修正后重新调用 submit_deck_polish。"
    edits.append(
        _DeckCardEdit(uuid=uuid, name=name.strip(), description=description.strip())
    )
    logger.info(f"[InitializeDeckActionSystem] submit_deck_polish: {uuid} → {name}")
    return f"已记录第 {len(edits)} 张卡牌的叙事调整。"


#######################################################################################################################################
def _handle_finish_polish() -> str:
    """处理 finish_deck_polish 工具调用（无参，仅作为终止信号）。"""
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
        lines.append(
            render_labeled_str_list(
                "  on_play_affixes（只读）", card.on_play_affixes, indent="    "
            )
        )
    if card.on_hit_affixes:
        lines.append(
            render_labeled_str_list(
                "  on_hit_affixes（只读）", card.on_hit_affixes, indent="    "
            )
        )
    if card.on_turn_end_affixes:
        lines.append(
            render_labeled_str_list(
                "  on_turn_end_affixes（只读）", card.on_turn_end_affixes, indent="    "
            )
        )

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
    """生成牌库初始化（叙事个人化）提示词。"""
    card_lines = "\n\n".join(_format_card_for_prompt(c) for c in cards)
    return f"""# 任务：初始化你的初始牌库（叙事个人化）

你是「{entity.name}」。你刚被赋予若干张初始卡牌，请依据你的角色设定（见对话开头的系统设定），对这些卡牌的 `name` 与 `description` 做一次叙事个人化润色，使其更像是"你自己"的招式、习惯或随身手段。

## 待润色卡牌清单

{card_lines}

{BUILD_CARD_FIELD_DESCRIPTION}

## 硬性约束

- 只允许改写每张卡的 `name` 与 `description`；其余字段（cost/damage/hit_count/block/target_type/self_target/三类词缀/playable/exhaust/retain/ethereal/transferable）一律禁止改动，也禁止在提交中输出。
- `description` 保持"叙事锚点"：不含具体数值，不重述 cost/damage/block 等字段已确定的效果；可自由采用动作、物件、意象、氛围、典故等形态。
- `name` 简洁有辨识度，体现你的个人风格。

## 工作流程

1. 逐一审视每张卡（以 `uuid` 精确定位，避免同名混淆）；
2. 为每张卡各调用一次 `submit_deck_polish`（参数：uuid / name / description）；
3. 全部提交完毕后调用 `finish_deck_polish` 结束。"""


#######################################################################################################################################
@final
class InitializeDeckActionSystem(ReactiveProcessor):
    """响应 InitializeDeckAction，为触发角色做牌库叙事个人化润色。

    幂等语义：仅处理 `source == ""` 的卡牌（视为「未初始化」）；先确定性回填 source，
    再做叙事润色，故下次触发自动跳过。设计路径已自设 source，直接跳过。
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
            valid_uuids: Set[str] = {c.uuid for c in targets}
            handlers: Dict[str, Callable[..., Union[str, Awaitable[str]]]] = {
                "submit_deck_polish": partial(
                    _handle_submit_polish, valid_uuids, edits
                ),
                "finish_deck_polish": _handle_finish_polish,
            }

            # 3) 组装 agent_loop 协程；messages 直接传真实记忆（原地写回）
            coro = agent_loop(
                name=entity.name,
                prompt=_build_deck_init_prompt(entity, targets),
                messages=self._game.get_agent_memory(entity).messages,
                tools=[SUBMIT_POLISH_TOOL, FINISH_POLISH_TOOL],
                handlers=handlers,
                terminal_tools=[FINISH_POLISH_TOOL],
                max_rounds=6,
            )

            pending.append((entity, targets, edits))
            tasks.append((entity.name, coro))

        if not tasks:
            logger.debug(
                "[InitializeDeckActionSystem] 无待初始化牌库（source 均已回填）"
            )
            return

        logger.info(
            f"[InitializeDeckActionSystem] 为 {len(tasks)} 个角色并发初始化牌库..."
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
                        f"[InitializeDeckActionSystem] {entity.name} 提交了未知 uuid "
                        f"{edit.uuid!r}，忽略"
                    )
                    continue
                target_card.name = edit.name
                target_card.description = edit.description
                applied += 1

            logger.info(
                f"[InitializeDeckActionSystem] {entity.name}: 初始化 {len(targets)} 张"
                f"，应用叙事调整 {applied} 张（agent_loop 成功={ok}）"
            )
