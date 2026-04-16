"""开发期 AI 响应磁盘缓存工具。

以 context + prompt 的 SHA-256 hash 为 key，将 AI 返回的 AIMessage 列表
缓存到 DEBUG_CACHE_DIR/{hash}.json，避免开发期重复调用 AI 接口。
"""

import hashlib
import json
from typing import List, Optional
from ..models.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    get_buffer_string,
)
from ..game.config import DEBUG_CACHE_DIR


###########################################################################################################################################
def compute_cache_key(
    context: List[AIMessage | HumanMessage | SystemMessage],
    prompt: str,
    entity_name: str,
) -> str:
    """计算 entity_name + context + prompt 的 SHA-256 hash，作为缓存文件名。

    将实体名称、context 与本次 prompt 一同编码进 key，确保不同实体的相同
    context/prompt 不会产生 key 碰撞。

    Args:
        context: 当前实体的对话历史（SystemMessage/HumanMessage/AIMessage 列表）。
        prompt: 本次发送给 AI 的提示词。
        entity_name: 实体名称，用于提高 key 唯一性。

    Returns:
        64 位十六进制 SHA-256 hash 字符串。
    """
    combined = context + [HumanMessage(content=prompt)]
    raw = entity_name + "|" + get_buffer_string(combined)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


###########################################################################################################################################
def load_debug_cache(cache_key: str) -> Optional[List[AIMessage]]:
    """从磁盘加载缓存的 AI 响应。

    Args:
        cache_key: 由 compute_cache_key 生成的 hash 字符串

    Returns:
        缓存的 AIMessage 列表；若缓存不存在或读取失败则返回 None
    """
    cache_file = DEBUG_CACHE_DIR / f"{cache_key}.json"
    if not cache_file.exists():
        return None

    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        return [AIMessage.model_validate(msg) for msg in data["ai_messages"]]
    except Exception:
        return None


###########################################################################################################################################
def save_debug_cache(cache_key: str, ai_messages: List[AIMessage]) -> None:
    """将 AI 响应序列化后写入磁盘缓存。

    Args:
        cache_key: 由 compute_cache_key 生成的 hash 字符串
        ai_messages: 需要缓存的 AIMessage 列表
    """
    DEBUG_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = DEBUG_CACHE_DIR / f"{cache_key}.json"
    payload = {"ai_messages": [msg.model_dump() for msg in ai_messages]}
    cache_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
