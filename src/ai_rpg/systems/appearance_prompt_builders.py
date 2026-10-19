"""外观合成的提示词与消息构造器（供补合成与穿装两条路径共用）。"""

from ..utils import prompt_builder


#######################################################################################################################################
@prompt_builder
def build_wear_costume_message(
    entity_name: str, costume_name: str, new_appearance: str
) -> str:
    """构建穿上时装后的外观更新消息。"""
    return f"# {entity_name} 的外观已更新\n{entity_name} 穿上了「{costume_name}」。\n当前外观：{new_appearance}"


#######################################################################################################################################
@prompt_builder
def build_self_appearance_message(costume_name: str, new_appearance: str) -> str:
    """构建「仅写给本人」的外观自我状态说明。

    用于管道起点的外观补齐：旧存档里的外观尚未与时装合成过，这不是世界上发生的
    “外观变化”事件（也没有人记过旧外观），因此只告知本人、不做全场景广播。
    """
    return (
        "# 你的外观\n" f"你当前穿着「{costume_name}」。\n" f"当前外观：{new_appearance}"
    )


#######################################################################################################################################
@prompt_builder
def build_appearance_synthesis_prompt(
    base_body: str,
    costume_name: str,
    costume_description: str,
) -> str:
    """构建外观合成的**任务提示词**：只给数据与输出格式。

    书写规范、覆盖维度、禁止项等规则不在这里，而由承担本任务的世界实体
    （`世界.外观合成`，见 demo/world.py 的 `create_appearance_synthesis`）
    以 system prompt 下发——任务提示词只负责「这批数据是什么」，规则只有一份。
    """
    return f"""# 任务

基础体型：{base_body}
时装「{costume_name}」：{costume_description}

把两者合成该角色当前的外观描述。只输出描述本身，不要前缀、解释或 Markdown。"""


#######################################################################################################################################
