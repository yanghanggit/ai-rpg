"""卡池系统：从卡牌原型库随机抽取 N 个原型，润色后装入卡池供后续抽卡。"""

import json
import random
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
from uuid import uuid4

from loguru import logger
from overrides import override
from pydantic import BaseModel

from ..deepseek import ToolDefinition, ToolFunction, agent_loop
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    ActorComponent,
    Card,
    CardPoolComponent,
    DeathComponent,
    GenerateCardPoolAction,
)
from ..pgsql import get_card_prototype, list_card_prototype_index
from ..utils import batch_run_boolean_tasks, prompt_builder


#######################################################################################################################################
CARD_POOL_SIZE: Final[int] = 3  # 卡池候选数量（3 选 1），未来可调


#######################################################################################################################################
@final
class _CardPoolEdit(BaseModel):
    """submit_pool_card 提交的单张卡牌叙事调整（仅 name/description，结构上杜绝改属性/词缀）。"""

    uuid: str
    name: str
    description: str


#######################################################################################################################################
SUBMIT_POOL_CARD_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="submit_pool_card",
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
FINISH_POOL_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="finish_pool",
        description="全部卡牌均已通过 submit_pool_card 提交后调用，结束本次卡池润色。",
        parameters={"type": "object", "properties": {}},
    )
)


#######################################################################################################################################
def _handle_submit_pool_card(
    edits: List[_CardPoolEdit],
    uuid: str,
    name: str,
    description: str,
) -> str:
    """处理 submit_pool_card 工具调用：校验并暂存一张卡牌的叙事调整。"""
    assert uuid, "uuid 不能为空"
    edits.append(_CardPoolEdit(uuid=uuid, name=name, description=description))
    logger.info(f"[CardPoolSystem] submit_pool_card: {uuid} → {name}")
    return "已记录该卡牌的叙事调整。"


#######################################################################################################################################
def _handle_finish_pool() -> str:
    """处理 finish_pool 工具调用（无参，仅作为终止信号）。"""
    return "已结束卡池润色。"


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
def _build_card_pool_prompt(entity: Entity, cards: List[Card]) -> str:
    """生成卡池候选卡牌的叙事个人化提示词。"""
    card_lines = "\n\n".join(_format_card_for_prompt(c) for c in cards)
    return f"""# 任务：为你新获得的卡池候选卡牌做叙事润色

你是「{entity.name}」。你刚获得若干张候选卡牌（将进入你的卡池，供之后抽选）。请依据你的角色设定（见对话开头的系统设定），对这些卡牌的 `name` 与 `description` 做一次叙事个人化润色，使其更像是"你自己"的招式、习惯或随身手段。

## 待润色卡牌清单

{card_lines}

## 硬性约束

- 只允许改写每张卡的 `name` 与 `description`；其余字段（cost/damage/hit_count/block/target_type/self_target/三类词缀/playable/exhaust/retain/ethereal/transferable）一律禁止改动，也禁止在提交中输出。
- `description` 保持"叙事锚点"：不含具体数值，不重述 cost/damage/block 等字段已确定的效果；可自由采用动作、物件、意象、氛围、典故等形态。
- `name` 简洁有辨识度，体现你的个人风格。

## 工作流程

1. 逐一审视每张卡（以 `uuid` 精确定位，避免同名混淆）；
2. 为每张卡各调用一次 `submit_pool_card`（参数：uuid / name / description）；
3. 全部提交完毕后调用 `finish_pool` 结束。"""


#######################################################################################################################################
@final
class CardPoolSystem(ReactiveProcessor):
    """响应卡池生成动作，为触发角色从原型库抽取候选卡、润色后装入卡池。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(GenerateCardPoolAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(GenerateCardPoolAction)
            and entity.has(ActorComponent)
            and not entity.has(DeathComponent)
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        # 拉取一次原型索引（系统侧随机，不用 LLM 浏览）
        try:
            index = list_card_prototype_index(card_type="手牌")
        except Exception as e:
            logger.error(f"[CardPoolSystem] 拉取卡牌原型失败: {e}")
            return

        if not index:
            logger.error("[CardPoolSystem] 卡牌原型库为空，无法生成卡池")
            return

        # 组装待生成卡池的任务（每个实体一个 agent_loop，并发执行）
        pending: List[Tuple[Entity, List[Card], List[_CardPoolEdit]]] = []
        tasks: List[Tuple[str, Coroutine[Any, Any, bool]]] = []

        for entity in entities:

            candidates = self._materialize_candidates(entity, index)
            if not candidates:
                continue

            # 每实体独立的结果容器与工具处理器
            edits: List[_CardPoolEdit] = []
            handlers: Dict[str, Callable[..., Union[str, Awaitable[str]]]] = {
                "submit_pool_card": partial(_handle_submit_pool_card, edits),
                "finish_pool": _handle_finish_pool,
            }

            # 组装 agent_loop 协程；messages 直接传真实记忆（原地写回）
            coro = agent_loop(
                name=entity.name,
                prompt=_build_card_pool_prompt(entity, candidates),
                messages=self._game.get_agent_memory(entity).messages,
                tools=[SUBMIT_POOL_CARD_TOOL, FINISH_POOL_TOOL],
                handlers=handlers,
                terminal_tools=[FINISH_POOL_TOOL],
                max_rounds=6,
            )

            pending.append((entity, candidates, edits))
            tasks.append((entity.name, coro))

        if not tasks:
            logger.debug("[CardPoolSystem] 无待生成卡池的角色")
            return

        logger.info(f"[CardPoolSystem] 为 {len(tasks)} 个角色并发生成卡池...")

        # 并发执行
        outcomes = await batch_run_boolean_tasks(tasks)

        # 应用结果：仅按 uuid 回填 name/description（硬约束），随后装入卡池
        for (entity, candidates, edits), ok in zip(pending, outcomes):
            by_uuid = {c.uuid: c for c in candidates}
            applied = 0
            for edit in edits:
                target_card = by_uuid.get(edit.uuid)
                if target_card is None:
                    logger.warning(
                        f"[CardPoolSystem] {entity.name} 提交了未知 uuid "
                        f"{edit.uuid!r}，忽略"
                    )
                    continue
                target_card.name = edit.name
                target_card.description = edit.description
                applied += 1

            # 装入卡池（replace 覆盖旧池，避免残留）
            entity.replace(CardPoolComponent, entity.name, candidates)

            logger.info(
                f"[CardPoolSystem] {entity.name}: 生成卡池 {len(candidates)} 张"
                f"，应用叙事调整 {applied} 张（agent_loop 成功={ok}）"
            )

    ####################################################################################################################################
    def _materialize_candidates(
        self,
        entity: Entity,
        index: List[Dict[str, object]],
    ) -> List[Card]:
        """从原型索引随机抽取并物化为独立卡牌（换新 uuid、回填 source）。"""

        sample = random.sample(index, k=min(CARD_POOL_SIZE, len(index)))

        candidates: List[Card] = []
        for entry in sample:
            prototype_id = entry["prototype_id"]
            try:
                proto = get_card_prototype(str(prototype_id))
                card = Card.model_validate(json.loads(proto.card_json))
            except Exception as e:
                logger.error(
                    f"[CardPoolSystem] 获取/解析原型 {prototype_id!r} 失败: {e}"
                )
                continue

            # 原型 uuid 是共享常量，必须换新；source 回填持有者名（与牌库初始化一致）
            card.uuid = str(uuid4())
            card.source = entity.name
            candidates.append(card)

        return candidates
