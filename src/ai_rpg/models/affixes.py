"""卡牌词条常量定义。

每个词条以 ComponentSerialization 的形式存储：
  - name : 对应已注册的 Component 类名（可反序列化）
  - data : flat 参数字典，由对应 Component 的 model_dump() 生成
"""

from typing import Final
from .serialization import ComponentSerialization
from .components import AffixSealedComponent


###############################################################################################################################################
AFFIX_SEALED: Final[ComponentSerialization] = ComponentSerialization(
    name=AffixSealedComponent.__name__,
    data=AffixSealedComponent(description="不可被出牌，也不可被弃牌").model_dump(),
)


###############################################################################################################################################
