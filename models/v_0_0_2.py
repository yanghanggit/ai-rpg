from typing import Final, Dict, final
from pydantic import BaseModel
from models.v_0_0_1 import World as World_v_0_0_1

"""
这是一个试验。@yanghang
"""


# 注意，不允许动！
SCHEMA_VERSION: Final[str] = "0.0.2"


###############################################################################################################################################
# 采用最“傻，纯，直”的策略，直接包上一次的版本，并根据需要，再加上新的字段。
@final
class WorldRuntime(BaseModel):
    version: str = SCHEMA_VERSION
    previous: World_v_0_0_1 = World_v_0_0_1()
    extends: Dict[str, str] = {}  # 测试的字段。


###############################################################################################################################################
