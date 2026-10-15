"""DeepSeek 通讯层错误模型。

单次通讯的失败统一用 `DeepSeekError` 表达。通讯层只负责如实记录与抛出，
**不做重试**；`retryable` 仅作为元数据交给业务层，由其决定重试策略与依赖程度。
"""

from typing import Final, Literal, Optional, Set

###########################################################################################################################################
# 失败类别：网络超时 / 网络连接 / 服务端返回非 200
###########################################################################################################################################
ErrorKind = Literal["timeout", "connection", "api"]


###########################################################################################################################################
# 明确属于「重试可能成功」的瞬时 HTTP 状态码（429 限流、408 请求超时、5xx 服务端故障）。
# 其余（400/401/402/422 等）为不可重试的确定性错误。
###########################################################################################################################################
_RETRYABLE_STATUS_CODES: Final[Set[int]] = {408, 429}


###########################################################################################################################################
class DeepSeekError(Exception):
    """单次 DeepSeek 通讯失败的统一异常。

    - name: 本次请求所属 client 名（批量场景下用于定位失败项）。
    - kind: 失败类别，`timeout` / `connection` / `api`。
    - status_code: HTTP 状态码；网络层错误（timeout / connection）为 None。
    - retryable: 该错误是否属于「重试可能成功」的瞬时故障。通讯层不据此重试，
      仅提供给业务层决策。
    """

    def __init__(
        self,
        name: str,
        message: str,
        *,
        kind: ErrorKind,
        status_code: Optional[int] = None,
    ) -> None:
        super().__init__(f"[{name}] {message}")
        self.name: Final[str] = name
        self.kind: Final[ErrorKind] = kind
        self.status_code: Final[Optional[int]] = status_code
        self.retryable: Final[bool] = self._is_retryable(kind, status_code)

    #######################################################################################################################################
    @staticmethod
    def _is_retryable(kind: ErrorKind, status_code: Optional[int]) -> bool:
        """判定是否为瞬时故障：网络层错误一律可重试；HTTP 层仅 429/408/5xx 可重试。"""
        if kind in ("timeout", "connection"):
            return True
        if status_code is None:
            return False
        return status_code in _RETRYABLE_STATUS_CODES or status_code >= 500
