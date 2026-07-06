"""开发期 AI 响应磁盘缓存工具。

以对话上下文列表的 SHA-256 hash 为 key，将单条 ContextMessage 序列化后
缓存到 DEBUG_CACHE_DIR/{hash}.json，避免开发期重复调用 AI 接口。
"""

import hashlib
import json
from typing import List, Optional
from pydantic import TypeAdapter
from ..models.messages import ContextMessage
from ..game.config import DEBUG_CACHE_DIR

_CONTEXT_MESSAGE_ADAPTER: TypeAdapter[ContextMessage] = TypeAdapter(ContextMessage)


###########################################################################################################################################
def compute_cache_key(
    context: List[ContextMessage],
) -> str:
    """计算对话上下文列表的 SHA-256 hash，作为缓存文件名。

    Args:
        context: 当前实体的完整对话历史。

    Returns:
        64 位十六进制 SHA-256 hash 字符串。
    """
    raw = json.dumps(
        [m.model_dump() for m in context],
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


###########################################################################################################################################
def load_debug_cache(cache_key: str) -> Optional[ContextMessage]:
    """从磁盘加载缓存的 ContextMessage。

    Args:
        cache_key: 由 compute_cache_key 生成的 hash 字符串。

    Returns:
        缓存的 ContextMessage（SystemMessage / HumanMessage / AIMessage / ToolMessage
        之一）；若缓存不存在或读取失败则返回 None。
    """
    cache_file = DEBUG_CACHE_DIR / f"{cache_key}.json"
    if not cache_file.exists():
        return None

    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        return _CONTEXT_MESSAGE_ADAPTER.validate_python(data)
    except Exception:
        return None


###########################################################################################################################################
def save_debug_cache(cache_key: str, message: ContextMessage) -> None:
    """将 ContextMessage 序列化后写入磁盘缓存。

    Args:
        cache_key: 由 compute_cache_key 生成的 hash 字符串。
        message: 需要缓存的 ContextMessage。
    """
    DEBUG_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = DEBUG_CACHE_DIR / f"{cache_key}.json"
    cache_file.write_text(
        json.dumps(message.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
