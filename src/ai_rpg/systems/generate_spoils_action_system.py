"""奖励(Spoils)生成系统：从卡牌原型库随机抽取 N 个原型，交由角色 agent 设计后装入 SpoilsComponent 供后续领取。

原型提供「骨架字段 + 设计指导」，agent 在此之上为本角色设计 `name` / `description`
与三类词缀（增益/减益规则）。词缀设计由 `validate_affix_slot` / `apply_affix_design` 校验，
任一槽不满足字段锚点/数值护栏则整槽回退原型。
"""

import json
import random
from dataclasses import dataclass
from functools import partial
from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Dict,
    Final,
    List,
    Optional,
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
    AFFIX_DESIGN_SPEC,
    BUILD_CARD_FIELD_DESCRIPTION,
    ActorComponent,
    Card,
    SpoilsComponent,
    DeathComponent,
    GenerateSpoilsAction,
    apply_affix_design,
)
from ..pgsql import get_card_prototype, list_card_prototype_index
from ..utils import batch_run_boolean_tasks, prompt_builder

#######################################################################################################################################
SPOILS_CARD_COUNT: Final[int] = 3  # 候选卡数量（3 选 1），未来可调


#######################################################################################################################################
@dataclass
class _Candidate:
    """一张待设计的候选卡 = 骨架卡 + 原型设计指导。"""

    card: Card
    archetype: str
    archetype_subtype: str
    summary: str
    guide: str


#######################################################################################################################################
@final
class _SpoilsCardEdit(BaseModel):
    """submit_spoils_card 提交的单张候选卡设计（name/description + 三类词缀）。"""

    uuid: str
    name: str
    description: str
    # 三类词缀：agent 在原型已存在的槽位内重新设计；缺省则保留原型。
    on_play_affixes: Optional[List[str]] = None
    on_hit_affixes: Optional[List[str]] = None
    on_turn_end_affixes: Optional[List[str]] = None


#######################################################################################################################################
SUBMIT_SPOILS_CARD_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="submit_spoils_card",
        description="提交一张候选卡的设计（name / description，以及可选的 on_play_affixes / on_hit_affixes / on_turn_end_affixes）。每张卡各调用一次，用 uuid 精确定位目标卡。",
        parameters={
            "type": "object",
            "properties": {
                "uuid": {
                    "type": "string",
                    "description": "目标卡牌的 uuid（来自任务清单，精确区分同名卡）",
                },
                "name": {
                    "type": "string",
                    "description": "设计后的卡牌名",
                },
                "description": {
                    "type": "string",
                    "description": "设计后的叙事描述（叙事锚点：不含数值，不重述字段已确定的效果）",
                },
                "on_play_affixes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "本卡打出时结算的即时词缀（可选），格式 `[词缀名]:机械结算描述`。仅当原型该槽非空时可提交；须满足字段锚点与数值护栏，否则整槽回退原型。",
                },
                "on_hit_affixes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "本卡持有者被命中时触发的受击词缀（可选），格式同上。仅当原型该槽非空时可提交；须满足字段锚点与数值护栏。",
                },
                "on_turn_end_affixes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "持有者每次 pass turn 结算的回合结束词缀（可选），格式同上。仅当原型该槽非空时可提交；须满足字段锚点与数值护栏。",
                },
            },
            "required": ["uuid", "name", "description"],
        },
    )
)


#######################################################################################################################################
FINISH_SPOILS_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="finish_spoils",
        description="全部候选卡均已通过 submit_spoils_card 提交后调用，结束本次候选奖励设计。",
        parameters={"type": "object", "properties": {}},
    )
)


#######################################################################################################################################
def _handle_submit_spoils_card(
    edits: List[_SpoilsCardEdit],
    uuid: str,
    name: str,
    description: str,
    on_play_affixes: Optional[List[str]] = None,
    on_hit_affixes: Optional[List[str]] = None,
    on_turn_end_affixes: Optional[List[str]] = None,
) -> str:
    """处理 submit_spoils_card 工具调用：校验并暂存一张候选卡的设计。"""
    assert uuid, "uuid 不能为空"
    edits.append(
        _SpoilsCardEdit(
            uuid=uuid,
            name=name,
            description=description,
            on_play_affixes=on_play_affixes,
            on_hit_affixes=on_hit_affixes,
            on_turn_end_affixes=on_turn_end_affixes,
        )
    )
    logger.info(f"[GenerateSpoilsActionSystem] submit_spoils_card: {uuid} → {name}")
    return "已记录该候选卡的设计。"


#######################################################################################################################################
def _handle_finish_spoils() -> str:
    """处理 finish_spoils 工具调用（无参，仅作为终止信号）。"""
    return "已结束候选奖励设计。"


#######################################################################################################################################
def _format_card_for_prompt(candidate: _Candidate) -> str:
    """将单张候选卡格式化为 prompt 片段（骨架字段只读 + 原型设计指导）。"""
    card = candidate.card
    lines = [
        f"- uuid: {card.uuid}",
        f"  原型定位: {candidate.archetype} / {candidate.archetype_subtype}",
        f"  原型摘要: {candidate.summary}",
        f"  设计指导: {candidate.guide}",
        f"  骨架字段（只读）: cost={card.cost} damage={card.damage} hit_count={card.hit_count} "
        f"block={card.block} target_type={card.target_type.value} self_target={card.self_target}",
    ]

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

    # 原型词缀：既是槽位声明，也是设计失败时的回退参考。
    if card.on_play_affixes:
        lines.append(
            f"  on_play_affixes（原型回退参考，需重设计）: {card.on_play_affixes}"
        )
    if card.on_hit_affixes:
        lines.append(
            f"  on_hit_affixes（原型回退参考，需重设计）: {card.on_hit_affixes}"
        )
    if card.on_turn_end_affixes:
        lines.append(
            f"  on_turn_end_affixes（原型回退参考，需重设计）: {card.on_turn_end_affixes}"
        )

    return "\n".join(lines)


#######################################################################################################################################
@prompt_builder
def _build_spoils_prompt(entity: Entity, candidates: List[_Candidate]) -> str:
    """生成候选奖励（卡牌）的设计提示词：骨架字段 + 原型指导 + 词缀设计规范。"""
    card_lines = "\n\n".join(_format_card_for_prompt(c) for c in candidates)
    return f"""# 任务：为你新获得的候选奖励（卡牌）做设计

你是「{entity.name}」。你刚获得若干张候选卡牌（将进入你的 Spoils，供之后领取一项）。请依据角色设定（见对话开头的系统设定），为每张卡设计 `name`、`description`，并在原型已存在的词缀槽位内**重新设计**词缀，使它们成为"你自己"的招式、习惯或随身手段。

## 待设计候选卡清单

{card_lines}

{BUILD_CARD_FIELD_DESCRIPTION}

{AFFIX_DESIGN_SPEC}

## 骨架与设计的边界

- **骨架字段只读**：`cost/damage/hit_count/block/target_type/self_target/playable/exhaust/retain/ethereal/transferable` 由原型给定，你只能引用，不能改动，也不能在提交中输出。
- **词缀槽位**：只能对原型已非空的槽位提交设计，不得新增其它时机；不提交则保留原型词缀，提交不合法则整槽回退原型。
- **原型词缀只是回退参考**：它不是你必须照抄的答案；请按上方规范为你的角色设计更贴合的版本。

## 叙事与边界

- `description` 保持"叙事锚点"：不含具体数值，不重述 cost/damage/block 等已确定的效果；可自由采用动作、物件、意象、氛围、典故等形态。
- `name` 简洁有辨识度，体现你的个人风格。
- **场景中立（重要）**：卡牌是你内在能力的外化，只能取材于你的角色设定（系统设定中的历史、性格、禁忌、最爱、体型，以及你的技艺、习惯与典故）。**禁止**在 `name`、`description` 或词缀中出现当前所在场景/地点的名称与景物、本次邂逅的人或怪、以及刚刚发生的具体遭遇；请刻意忽略对话中"当前场景感知"这类即时信息，成稿应在更换任何场景后依然成立。

## 工作流程

1. 逐一审视每张卡（以 `uuid` 精确定位，避免同名混淆）：读骨架字段与设计指导，判断该卡能为你的角色带来什么收益/代价；
2. 为每张卡各调用一次 `submit_spoils_card`：提交 `uuid` / `name` / `description`；对原型已存在的词缀槽位，提交你设计好的 `on_play_affixes` / `on_hit_affixes` / `on_turn_end_affixes`（合法则采用，不合法整槽回退原型）；
3. 全部提交完毕后调用 `finish_spoils` 结束。"""


#######################################################################################################################################
@final
class GenerateSpoilsActionSystem(ReactiveProcessor):
    """响应奖励生成动作，为触发角色从原型库抽取候选卡、交由 agent 设计后装入 SpoilsComponent。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(GenerateSpoilsAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(GenerateSpoilsAction)
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
            logger.error(f"[GenerateSpoilsActionSystem] 拉取卡牌原型失败: {e}")
            return

        if not index:
            logger.error(
                "[GenerateSpoilsActionSystem] 卡牌原型库为空，无法生成候选奖励"
            )
            return

        # 组装待生成奖励的任务（每个实体一个 agent_loop，并发执行）
        #
        # 第一步：整批物化候选；任一角色物化失败则整批中止（不写任何 SpoilsComponent、不调 LLM）。
        # 这样守卫 `any(has(SpoilsComponent))` 保持“全有或全无”，客户端可安全手动重试。
        materialized: List[Tuple[Entity, List[_Candidate]]] = []
        for entity in entities:
            candidates = self._materialize_candidates(entity, index)
            if not candidates:
                logger.error(
                    f"[GenerateSpoilsActionSystem] {entity.name} 候选物化失败，"
                    f"整批中止，未写入任何 SpoilsComponent（客户端可重试）"
                )
                return
            materialized.append((entity, candidates))

        # 第二步：组装并并发执行 agent_loop（LLM 设计失败不阻断发奖，只影响设计）
        pending: List[Tuple[Entity, List[_Candidate], List[_SpoilsCardEdit]]] = []
        tasks: List[Tuple[str, Coroutine[Any, Any, bool]]] = []

        for entity, candidates in materialized:

            # 每实体独立的结果容器与工具处理器
            edits: List[_SpoilsCardEdit] = []
            handlers: Dict[str, Callable[..., Union[str, Awaitable[str]]]] = {
                "submit_spoils_card": partial(_handle_submit_spoils_card, edits),
                "finish_spoils": _handle_finish_spoils,
            }

            # 组装 agent_loop 协程；messages 直接传真实记忆（原地写回）
            coro = agent_loop(
                name=entity.name,
                prompt=_build_spoils_prompt(entity, candidates),
                messages=self._game.get_agent_memory(entity).messages,
                tools=[SUBMIT_SPOILS_CARD_TOOL, FINISH_SPOILS_TOOL],
                handlers=handlers,
                terminal_tools=[FINISH_SPOILS_TOOL],
                max_rounds=6,
            )

            pending.append((entity, candidates, edits))
            tasks.append((entity.name, coro))

        if not tasks:
            logger.debug("[GenerateSpoilsActionSystem] 无待生成奖励的角色")
            return

        logger.info(
            f"[GenerateSpoilsActionSystem] 为 {len(tasks)} 个角色并发生成候选奖励..."
        )

        # 并发执行
        outcomes = await batch_run_boolean_tasks(tasks)

        # 应用结果：按 uuid 回填 name/description（硬约束），词缀经「字段锚点 + 数值护栏」校验（失败整槽回退原型）
        for (entity, candidates, edits), ok in zip(pending, outcomes):
            by_uuid = {c.card.uuid: c.card for c in candidates}
            applied = 0
            affixes_applied = 0
            for edit in edits:
                target_card = by_uuid.get(edit.uuid)
                if target_card is None:
                    logger.warning(
                        f"[GenerateSpoilsActionSystem] {entity.name} 提交了未知 uuid "
                        f"{edit.uuid!r}，忽略"
                    )
                    continue
                target_card.name = edit.name
                target_card.description = edit.description
                count, fallbacks = apply_affix_design(
                    entity.name,
                    target_card,
                    {
                        "on_play_affixes": edit.on_play_affixes,
                        "on_hit_affixes": edit.on_hit_affixes,
                        "on_turn_end_affixes": edit.on_turn_end_affixes,
                    },
                )
                affixes_applied += count
                for reason in fallbacks:
                    logger.warning(f"[GenerateSpoilsActionSystem] {reason}")
                applied += 1

            # 装入 Spoils（replace 覆盖旧内容；claimed_cards 为空队列）
            entity.replace(
                SpoilsComponent, entity.name, [c.card for c in candidates], []
            )

            logger.info(
                f"[GenerateSpoilsActionSystem] {entity.name}: 生成候选卡 {len(candidates)} 张"
                f"，应用设计 {applied} 张，设计词缀 {affixes_applied} 条（agent_loop 成功={ok}）"
            )

    ####################################################################################################################################
    def _materialize_candidates(
        self,
        entity: Entity,
        index: List[Dict[str, object]],
    ) -> List[_Candidate]:
        """从原型索引随机抽取并物化为独立候选（换新 uuid、回填 source、附设计指导）。"""

        sample = random.sample(index, k=min(SPOILS_CARD_COUNT, len(index)))

        candidates: List[_Candidate] = []
        for entry in sample:
            prototype_id = entry["prototype_id"]
            try:
                proto = get_card_prototype(str(prototype_id))
                card = Card.model_validate(json.loads(proto.card_json))
            except Exception as e:
                logger.error(
                    f"[GenerateSpoilsActionSystem] 获取/解析原型 {prototype_id!r} 失败: {e}"
                )
                continue

            # 原型 uuid 是共享常量，必须换新；source 回填持有者名（与牌库初始化一致）
            card.uuid = str(uuid4())
            card.source = entity.name
            candidates.append(
                _Candidate(
                    card=card,
                    archetype=proto.archetype,
                    archetype_subtype=proto.archetype_subtype,
                    summary=proto.summary,
                    guide=proto.guide,
                )
            )

        return candidates
