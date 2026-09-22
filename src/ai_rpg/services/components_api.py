"""组件名清单接口模块。

`COMPONENT_TYPES` 是 ECS 组件类名的唯一事实源（`models/components.py` 里每个
`@register_component_type` 的类名）。`ComponentSerialization.name` 在契约里只是
`string`（后端还支持 `create_component_type` 动态类，无法收窄成枚举），前端拿不到
这层约束，类名拼错只会静默读不到数据。本接口把注册表的键暴露出来，供前端
`scripts/genApi.mjs` 生成编译期清单使用。
"""

from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from ..models import COMPONENT_TYPES

################################################################################################################
components_api_router = APIRouter()


################################################################################################################
class ComponentNamesResponse(BaseModel):
    """已注册的 ECS 组件类名清单。"""

    names: List[str]


################################################################################################################
################################################################################################################
################################################################################################################
@components_api_router.get(
    path="/api/components/v1/", response_model=ComponentNamesResponse
)
async def list_component_names() -> ComponentNamesResponse:
    """返回所有已注册的组件类名（排序后）。"""

    return ComponentNamesResponse(names=sorted(COMPONENT_TYPES))
