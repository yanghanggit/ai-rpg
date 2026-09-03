#!/usr/bin/env python3
"""动态创建 Pydantic BaseModel 的示例脚本（用于学习）。

演示三种方式：
  1. create_model(字符串类名, **字段) —— 官方推荐
  2. 从一个字段定义"字符串"整体解析后，再用 create_model 创建
  3. 原生 type(name, (BaseModel,), {...}) —— class 语句的底层实现

直接运行：
    python scripts/dynamic_basemodel_sample.py
"""

from typing import Any, Dict, Tuple

from pydantic import BaseModel, ValidationError, create_model


# ---------------------------------------------------------------------------
# 方式一：create_model(类名字符串, **字段定义)
# ---------------------------------------------------------------------------
def sample_create_model() -> None:
    """用字符串类名 + 字段字典动态创建模型。

    字段定义格式：字段名=(类型, 默认值)
      - 默认值填 ... 表示"必填"，等价于 class 里的 `name: str`
      - 填具体值表示可选字段，等价于 `age: int = 0`
    """
    print("=== 方式一：create_model(字符串类名, **字段) ===")

    # 动态生成一个名为 "Character" 的模型
    Character = create_model(
        "Character",  # 字符串类名
        name=(str, ...),  # 必填
        age=(int, 0),  # 可选，默认 0
        hp=(int, 100),  # 可选，默认 100
        tags=(list[str], []),  # 可选，默认空列表
    )

    # 它就是一个普通的 BaseModel 子类
    print("类名:", Character.__name__)
    print("是否 BaseModel 子类:", issubclass(Character, BaseModel))

    hero = Character(name="Alice")
    print("实例:", hero)

    # 必填字段缺失会报错
    try:
        Character()
    except ValidationError as e:
        print("缺失必填字段时的报错:")
        print(e)

    # 还能拿到 JSON Schema（对接 FastAPI / LLM function calling 很有用）
    print("JSON Schema:")
    print(Character.model_json_schema())


# ---------------------------------------------------------------------------
# 方式二：从"字符串"整体解析出字段，再动态创建
# ---------------------------------------------------------------------------
def parse_field_string(src: str) -> Tuple[str, Dict[str, Any]]:
    """解析形如 "ClassName: name: str = 'x'; age: int" 的字符串。

    返回 (类名, 字段字典)，字段字典可直接传给 create_model。

    注意：这里为了示例简单用了 eval()，仅适用于你完全信任的字符串；
    如果字符串来自外部输入，请换成安全的解析方式（如 ast 模块）。
    """
    class_name, body = src.split(":", 1)
    fields: Dict[str, Any] = {}

    for part in body.split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            # 带默认值：name: str = 'x'
            name_type, default = part.split("=", 1)
            name, typ = (x.strip() for x in name_type.split(":", 1))
            fields[name] = (eval(typ), eval(default))
        else:
            # 无默认值（必填）：age: int
            name, typ = (x.strip() for x in part.split(":", 1))
            fields[name] = (eval(typ), ...)

    return class_name.strip(), fields


def sample_create_from_string() -> None:
    """从一段字符串定义创建模型。"""
    print("\n=== 方式二：从字符串整体解析创建 ===")

    src = "NPC: name: str = 'guard'; level: int; skills: list[str] = ['talk']"
    class_name, fields = parse_field_string(src)

    print("解析结果 -> 类名:", class_name, "| 字段:", fields)

    NPC = create_model(class_name, **fields)
    print("动态模型:", NPC)

    npc = NPC(level=3)
    print("实例:", npc)
    print("类名:", NPC.__name__)


# ---------------------------------------------------------------------------
# 方式三：原生 type() —— class 语句的底层
# ---------------------------------------------------------------------------
def sample_type() -> None:
    """用 type() 动态创建模型，等价于 class X(BaseModel) 的语法糖。

    相比 create_model 需要手动维护 __annotations__，容易出错，仅作原理演示。
    """
    print("\n=== 方式三：原生 type() ===")

    Item = type(
        "Item",  # 类名字符串
        (BaseModel,),  # 基类元组
        {
            "__annotations__": {"name": str, "price": float},
            "name": ...,  # 必填
            "price": 0.0,  # 默认值
        },
    )

    print("类名:", Item.__name__)
    print("是否 BaseModel 子类:", issubclass(Item, BaseModel))
    print("实例:", Item(name="sword", price=9.9))


def main() -> None:
    sample_create_model()
    sample_create_from_string()
    sample_type()


if __name__ == "__main__":
    main()
