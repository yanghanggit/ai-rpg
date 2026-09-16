"""Replicate 传输层纯函数单元测试。

覆盖 ``image_format_from_url``：从产物 URL 推断真实图片格式。
不调用任何外部 API。
"""

from typing import Optional

import pytest

from src.ai_rpg.replicate.pipeline import image_format_from_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://replicate.delivery/abc/tmp123.jpeg", "jpeg"),
        ("https://replicate.delivery/abc/tmp123.png", "png"),
        ("https://replicate.delivery/abc/tmp123.webp", "webp"),
        ("https://replicate.delivery/abc/tmp123.JPG", "jpg"),
        ("https://replicate.delivery/abc/tmp123.png?token=xyz&v=2", "png"),
        ("https://replicate.delivery/abc/tmp123", None),
        ("https://replicate.delivery/abc/tmp123.txt", None),
        ("", None),
    ],
)
def test_image_format_from_url(url: str, expected: Optional[str]) -> None:
    assert image_format_from_url(url) == expected
