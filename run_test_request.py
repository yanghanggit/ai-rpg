import datetime
from typing import List
from agent.chat_request_handler import ChatRequestHandler
from extended_systems.lang_serve_system import LangServeSystem
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from loguru import logger


async def run():
    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logger.add(f"testlog/{log_start_time}.log")

    server_url = "http://localhost:8100/v1/llm_serve/chat/"
    lang_serve_system = LangServeSystem(f"test-langserve_system")
    lang_serve_system.add_remote_runnable(url=server_url)

    history: List[SystemMessage | HumanMessage | AIMessage] = []
    system_msg = """你好！我正在设计一个卡牌游戏，需要你作为卡牌设计师的助手辅助设计一些卡牌的原型。\n
# 玩法梗概
1. 在这个游戏中，玩家需要操作三个角色在地下城中冒险。每个角色都带有一个牌池，玩家使用他们对应的牌来驱动他们。
2. 玩家每回合会从卡组中抽出五张牌，给这五张牌进行排序并最后打出。牌的顺序代表了最终执行顺序。
3. LLM将判断这五张牌的合理性和有效性，并给出玩家行动的最终描述。
4. 牌的不同排列将形成不同的combo，玩家需要根据情况选择合适当前战况的combo。
5. combo示例：法师先生成了火球，又生成了冰雨，让场地中弥漫遮挡视线的水汽。战士使用投掷将猎人投掷到敌人背后，猎人随后使用连击对敌人的弱点造成了更多伤害。
# 卡牌细节
1. 卡牌的名字：可以是动词，代表行动的名词，代表道具的名词。
2. 卡牌描述：对于卡牌名内容的描述。
3. 卡牌效果：在何种条件下能给自身，友方或目标添加或移除什么TAG。卡牌的效果是由对角色TAG的增改表示的。
4. 卡牌TAG，这张牌包含什么TAG。
# TAG细节
1. TAG是LLM用于判断卡牌合理性，有效性的依据。
2. TAG的格式为 <TAG名>: Tag描述， 以字典形式存储。
3. 对于每张牌，需要尽可能多的TAG来全面且详细地描述这张牌。例如<物理>：这是物理攻击，<火焰>：这是火属性攻击，<范围>：此攻击范围很大，更易命中，但也可能误伤友方。TAG描述要客观。
# 牌的输出格式
- 请以json格式返回牌。
- 格式示例：{“牌名”: {"discription": "卡牌描述", "effect": "卡牌效果", "tags": {TAG字典}},...}
# 其他要求
- 请尽量发挥想象力，让卡牌尽可能夸张，无厘头，有趣。
- 尽量使每张牌都能与其他牌形成combo。

\n我希望先完成“鲁莽的战士”，“怕鬼的法师”，“纯真的猎人”三个角色的卡牌。
\n你需要了解的信息如上，接下来卡牌设计师将给你具体的指示。"""
    logger.error(system_msg)
    history.append(SystemMessage(content=system_msg))

    run_flag = True
    while run_flag:
        usr_input = input(f"输入对话内容，/q退出：")
        logger.warning(usr_input)
        if usr_input is "/q":
            print("退出！")
            run_flag = False
            continue
        elif usr_input is "":
            print("空输入！")
            continue

        request = ChatRequestHandler(
            name="user", prompt=usr_input, chat_history=history
        )
        request_list = [request]

        await lang_serve_system.gather(request_list)
        for handler in request_list:
            response = handler.response_content
            logger.debug(response)

            history.append(HumanMessage(content=usr_input))
            history.append(AIMessage(content=response))


if __name__ == "__main__":
    import asyncio

    asyncio.run(run())
