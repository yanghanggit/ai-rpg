"""与具体 provider 无关的对话数据类型。

这些结构是 OpenAI 兼容的（DeepSeek 直接沿用），因此不属于 `ai_rpg.deepseek`：
任何一家 OpenAI 兼容服务、以及未来的本地模型网关都能复用同一套定义。

依赖方向：`ai_rpg.llm` 是被依赖方，本模块**不得** import `ai_rpg.deepseek`。
"""

from typing import Any, Dict, Literal

from pydantic import BaseModel

############################################################################################################
# tool_choice 取值（OpenAI 兼容）
ToolChoice = Literal["auto", "none", "required"]

# reasoning_effort 取值（DeepSeek 思考模式档位；其他 provider 可自行映射或忽略）
ReasoningEffort = Literal["low", "high", "max"]


############################################################################################################
class ToolFunction(BaseModel):
    """工具函数参数的 JSON Schema 描述（对应 DeepSeek/OpenAI tools[].function）"""

    name: str  # 工具名称，应与业务逻辑函数名一致
    description: str  # 面向 LLM 的工具功能说明
    parameters: Dict[str, Any]  # 参数的 JSON Schema（object 类型）


############################################################################################################
class ToolDefinition(BaseModel):
    """单个工具定义，对应 DeepSeek/OpenAI tools 数组的一个元素"""

    type: Literal["function"] = "function"  # 固定为 "function"
    function: ToolFunction  # 函数描述内容


############################################################################################################
class ToolCall(BaseModel):
    """LLM 返回的单次工具调用指令（finish_reason == \"tool_calls\" 时存在）"""

    class Function(BaseModel):
        name: str  # 被调用的工具名称
        arguments: str  # JSON 序列化的参数字符串

    id: str  # 本次调用的唯一 ID，需在 ToolMessage 中回传
    type: str = "function"  # 固定为 "function"
    function: Function  # 函数调用信息


############################################################################################################
class Usage(BaseModel):
    """响应中的 token 用量统计（对应 DeepSeek/OpenAI usage 字段）"""

    prompt_tokens: int  # 本次请求上下文（输入）消耗的 token 数
    completion_tokens: int  # 本次生成（输出）消耗的 token 数
    total_tokens: int  # 输入 + 输出的 token 总数
    prompt_cache_hit_tokens: int  # 命中 KVCache 的输入 token 数
    prompt_cache_miss_tokens: int  # 未命中 KVCache 的输入 token 数
    reasoning_tokens: int = 0  # 思考过程消耗的 token 数；非思考模式响应中不返回该字段


__all__ = [
    "ReasoningEffort",
    "ToolCall",
    "ToolChoice",
    "ToolDefinition",
    "ToolFunction",
    "Usage",
]
