"""卡牌与状态效果模型定义"""

from typing import final
from uuid import uuid4
from pydantic import BaseModel, Field, field_validator
from .phase_type import PhaseType


@final
class AffixTrigger(BaseModel):
    """affixes 触发信号载体。"""

    source: str  # 触发来源标签，如"卡牌"/"装备命中·受击者"/"装备穿戴"/"消耗品"/"场景交互"/"战斗初始化场景"
    affix: str  # 原始词缀文本；场景类触发（无具体词缀实体）则为已自带描述格式的完整触发文本
    context: str = (
        ""  # 触发上下文（actor/card/targets 等信息拼成的一句话）；场景类触发可为空
    )


###############################################################################################################################################
@final
class StatusEffect(BaseModel):
    """状态效果（增益/减益）"""

    name: str
    description: (
        str  # 效果描述（静态规则说明，不随状态变化，由 LLM 创建时写入后不再修改）
    )
    duration: int = 3  # 持续回合数；-1=永久，>0=剩余回合
    phase: PhaseType = PhaseType.ARBITRATION  # 生效阶段，默认仲裁阶段
    counter: int = (
        0  # 特殊计数器；仅 ARBITRATION 阶段效果使用；由仲裁 LLM 按游戏事件更新（倒计型从初始值递减，累加型从 0 递增）；普通效果保持 0
    )
    source: str = ""  # 效果施加者名称；空字符串表示来源未知
    affix: str = (
        ""  # 生成该效果的原始触发词缀文本；由创建流程从对应 AffixTrigger.affix 复制写入
    )
    speed: int = (
        0  # 速度加成（正值加速、负值减速）；叠加到角色最终速度，影响每回合出手顺序
    )
    defense: int = (
        0  # 防御加成（正值增防、负值破甲）；叠加到角色最终防御，影响仲裁阶段的伤害减免
    )
    uuid: str = Field(default_factory=lambda: str(uuid4()))  # 全局唯一标识符

    @field_validator("speed")
    @classmethod
    def clamp_speed(cls, v: int) -> int:
        """将 speed 归一化到 {-1, 0, +1}，保留正负号。"""
        if v > 0:
            return 1
        if v < 0:
            return -1
        return 0


###############################################################################################################################################
