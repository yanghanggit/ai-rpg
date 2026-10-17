"""基础牌（开局保底）的不变量：统一命名、无词缀、tier=basic。

基础攻击/防守是「保底发放」而非「选型候选」：同一持卡者会有多张一模一样的副本，
因此必须共用一个名字、且不带任何词缀；否则每张副本被各自取名/加词缀，既难读、
又把「基础」和「设计」混成一谈。
"""

from ai_rpg.models.card import AFFIX_FIELDS
from demo import CARD_PROTOTYPES
from demo.card_skeletons import BASIC_ATTACK_SKELETON, BASIC_DEFENSE_SKELETON
from demo.world import _make_attack_card, _make_defense_card


def test_basic_skeletons_have_no_affixes() -> None:
    for skeleton in (BASIC_ATTACK_SKELETON, BASIC_DEFENSE_SKELETON):
        for field in AFFIX_FIELDS:
            assert not getattr(skeleton, field), f"{skeleton.name} 不应带词缀: {field}"


def test_basic_prototypes_are_tier_basic() -> None:
    basics = {p.meta.prototype_id for p in CARD_PROTOTYPES if p.meta.tier == "basic"}
    assert basics == {"proto.basic_attack", "proto.basic_defense"}


def test_basic_copies_share_one_name_and_no_affixes() -> None:
    attacks = [_make_attack_card("角色.测试") for _ in range(3)]
    defenses = [_make_defense_card("角色.测试") for _ in range(2)]

    assert {card.name for card in attacks} == {"攻击"}
    assert {card.name for card in defenses} == {"防守"}
    for card in attacks + defenses:
        for field in AFFIX_FIELDS:
            assert not getattr(card, field), f"{card.name} 不应带词缀: {field}"
