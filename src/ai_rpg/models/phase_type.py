"""战斗阶段/流程枚举模型定义

PhaseType 描述战斗流程中各个阶段，供 StatusEffect、系统及 LLM 提示词复用。
"""

from enum import StrEnum, unique
from typing import final


###############################################################################################################################################
@final
@unique
class PhaseType(StrEnum):
    """战斗阶段

    标记战斗流程中的各个阶段，状态效果（StatusEffect）通过 phase 字段声明应在哪个阶段起效。

    - draw        : 抽牌阶段（DrawCardsActionSystem）——影响本回合卡牌生成，如"混乱"使牌质下降
    - play        : 出牌阶段（PlayCardsActionSystem）——卡牌被打出、行动写入上下文的阶段；
                    占位，当前未绑定具体效果系统，后续可用于"出牌时触发"类效果
    - arbitration : 仲裁阶段（PlayCardsArbitrationSystem）——作为注入仲裁 LLM 的上下文参数，
                    LLM 自由解读其对出牌结算过程的影响（伤害/防御修正、反伤、眩晕等），与出牌绑定
    - round_end   : 回合末阶段（CombatRoundCleanupSystem）——每回合末自动 tick，
                    实体自身 LLM 推理 HP 变化（DOT 如中毒/燃烧持续扣血，HOT 如再生持续回血）
    """

    DRAW = "draw"
    PLAY = "play"
    ARBITRATION = "arbitration"
    ROUND_END = "round_end"


###############################################################################################################################################
