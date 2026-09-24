"""``TextToImageSpec`` -> Replicate ``model_input`` 映射单元测试。

重点覆盖：
- ``aspect_ratio`` 缺省时按 ``width`` / ``height`` 推导；
- 显式 ``aspect_ratio`` 优先；
- 模型专属参数（``scheduler`` / ``magic_prompt_option``）默认不下发、显式设置才下发。
全部为纯逻辑，不调用任何外部 API。
"""

from typing import Optional

import pytest

from ai_rpg.replicate.assets import TextToImageSpec, _text_to_image_input


def test_aspect_ratio_derived_landscape() -> None:
    spec = TextToImageSpec(model="flux-schnell", prompt="p", width=1024, height=768)
    assert _text_to_image_input(spec)["aspect_ratio"] == "4:3"


def test_aspect_ratio_derived_portrait() -> None:
    spec = TextToImageSpec(model="flux-schnell", prompt="p", width=768, height=1024)
    assert _text_to_image_input(spec)["aspect_ratio"] == "3:4"


def test_aspect_ratio_derived_square() -> None:
    spec = TextToImageSpec(model="flux-schnell", prompt="p", width=1024, height=1024)
    assert _text_to_image_input(spec)["aspect_ratio"] == "1:1"


def test_aspect_ratio_derived_wide() -> None:
    spec = TextToImageSpec(model="flux-schnell", prompt="p", width=1344, height=768)
    assert _text_to_image_input(spec)["aspect_ratio"] == "16:9"


def test_explicit_aspect_ratio_wins() -> None:
    spec = TextToImageSpec(
        model="ideogram-v3-turbo",
        prompt="p",
        width=1024,
        height=1024,
        aspect_ratio="16:9",
    )
    assert _text_to_image_input(spec)["aspect_ratio"] == "16:9"


def test_invalid_dimensions_fall_back_to_square() -> None:
    spec = TextToImageSpec(model="flux-schnell", prompt="p", width=0, height=0)
    assert _text_to_image_input(spec)["aspect_ratio"] == "1:1"


def test_model_specific_params_omitted_by_default() -> None:
    model_input = _text_to_image_input(TextToImageSpec(model="nano-banana", prompt="p"))
    assert "scheduler" not in model_input
    assert "magic_prompt_option" not in model_input


def test_model_specific_params_included_when_set() -> None:
    spec = TextToImageSpec(
        model="ideogram-v3-turbo",
        prompt="p",
        scheduler="K_EULER",
        magic_prompt_option="Auto",
    )
    model_input = _text_to_image_input(spec)
    assert model_input["scheduler"] == "K_EULER"
    assert model_input["magic_prompt_option"] == "Auto"


def test_seed_included_only_when_set() -> None:
    assert "seed" not in _text_to_image_input(TextToImageSpec(model="m", prompt="p"))
    assert (
        _text_to_image_input(TextToImageSpec(model="m", prompt="p", seed=7))["seed"]
        == 7
    )


@pytest.mark.parametrize("negative", [None, "", "blurry"])
def test_negative_prompt_always_present_as_string(negative: Optional[str]) -> None:
    spec = TextToImageSpec(model="m", prompt="p", negative_prompt=negative)
    assert isinstance(_text_to_image_input(spec)["negative_prompt"], str)


def test_num_outputs_is_fixed_one() -> None:
    assert (
        _text_to_image_input(TextToImageSpec(model="m", prompt="p"))["num_outputs"] == 1
    )
