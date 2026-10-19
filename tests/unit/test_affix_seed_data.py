"""种子卡牌的词缀质量校验：一个元素 = 一条单行规则，不塞叙事。

词缀是多值列表，本意是「多条独立规则各占一个元素」。这里把两条纪律钉在测试上：

1. **一条一个元素**：元素内没有换行；出现多个句末标点即视为把多条规则拼成了一条
   （提示词要求逐条结算，拼在一起会让模型漏结算）；
2. **只写规则**：种子数据的词缀里不出现叙事/心理描写（那属于 `description`）。

原型骨架的占位词缀只做格式与单行校验——它们在设计期本就要被替换。
"""

import re
from typing import Iterator, Tuple

import pytest
from pydantic import ValidationError

from ai_rpg.models import AFFIX_FIELDS, Card
from demo.card_prototypes import CARD_PROTOTYPES
from demo.world import create_badluck, create_nameless

_AFFIX_RE = re.compile(r"^\[[^\[\]]+\]\s*[:：]\s*\S")
_SENTENCE_END_RE = re.compile(r"[。！？]")
_FLAVOR_MARKERS = ("就像", "仿佛", "像是", "心里", "觉得", "感到")


def _iter_seed_affixes() -> Iterator[Tuple[str, str, str]]:
    """遍历演示世界里所有具名种子卡的词缀：(卡名, 槽位, 词缀文本)。

    `create_*()` 产出的是待写入蓝图的分量字典（`dump_components` 的结果），
    所以这里按序列化后的形状读，而不是按实体组件读。
    """
    for factory in (create_nameless, create_badluck):
        actor = factory()
        deck = (actor.components or {}).get("DeckComponent")
        assert deck is not None, f"{actor.name} 缺少 DeckComponent"
        for card in deck["cards"]:
            for field in AFFIX_FIELDS:
                for affix in card[field]:
                    yield card["name"], field, affix


def _iter_skeleton_affixes() -> Iterator[Tuple[str, str, str]]:
    for prototype in CARD_PROTOTYPES:
        card = prototype.skeleton
        for field in AFFIX_FIELDS:
            for affix in getattr(card, field):
                yield card.name, field, affix


@pytest.mark.parametrize(("card_name", "field", "affix"), list(_iter_seed_affixes()))
def test_seed_affix_is_one_single_line_rule(
    card_name: str, field: str, affix: str
) -> None:
    """种子词缀：单行、格式合规、只有一条规则、不含叙事。"""
    assert "\n" not in affix, f"{card_name}.{field} 词缀含换行：{affix!r}"
    assert _AFFIX_RE.match(affix), f"{card_name}.{field} 词缀格式不合规：{affix!r}"
    assert (
        len(_SENTENCE_END_RE.findall(affix)) <= 1
    ), f"{card_name}.{field} 把多条规则塞进了一个元素：{affix!r}；请拆成多个列表元素"
    for marker in _FLAVOR_MARKERS:
        assert (
            marker not in affix
        ), f"{card_name}.{field} 词缀里出现了叙事/心理描写（{marker}）：{affix!r}；叙事属于 description，词缀只写机制"


@pytest.mark.parametrize(
    ("card_name", "field", "affix"), list(_iter_skeleton_affixes())
)
def test_prototype_affix_is_one_single_line_slot(
    card_name: str, field: str, affix: str
) -> None:
    """原型骨架的占位词缀同样必须单行、格式合规（内容会在设计期被替换）。"""
    assert "\n" not in affix, f"{card_name}.{field} 词缀含换行：{affix!r}"
    assert _AFFIX_RE.match(affix), f"{card_name}.{field} 词缀格式不合规：{affix!r}"


def test_multiline_affix_is_rejected_by_model() -> None:
    """模型层兜底：换行词缀直接断言失败，避免绕过设计期校验的写入路径。"""
    with pytest.raises(ValidationError, match="一条词缀只写一行"):
        Card(
            name="坏词缀",
            description="",
            on_play_affixes=["[甲]:造成 3 点伤害\n[乙]:回复 2 点 HP"],
        )


def test_multiple_affixes_are_separate_elements() -> None:
    """正确形态：两条规则 = 两个元素，逐条独立结算。"""
    card = Card(
        name="两段式",
        description="",
        on_play_affixes=["[甲]:造成 3 点伤害", "[乙]:回复 2 点 HP"],
    )
    assert len(card.on_play_affixes) == 2
