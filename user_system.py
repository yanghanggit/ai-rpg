from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable
import sys


def talk_to_agent(input_val, npc_agent, chat_history):
    response = npc_agent.invoke({"input": input_val, "chat_history": chat_history})
    chat_history.extend([HumanMessage(content=input_val), AIMessage(content=response['output'])])
    return response['output']

def parse_talk(input_val):
    if "/talk" in input_val:
        return input_val.split("/talk")[1].strip()
    return input_val

def run_user_system():

    #
    npc_agent = RemoteRunnable("http://localhost:8001/actor/npc/elder/")
    npc_achat_history = []

    #
    scene_agent = RemoteRunnable("http://localhost:8002/actor/npc/house/")
    scene_achat_history = []

    #
    scene_state = talk_to_agent(
            f"""
#状态
-晚上
#事件
-村长坐在屋子里（篝火旁），回忆年轻时的事情
#需求
-请根据#状态与#事件，输出一段描写文字，表现此时的场景状态
            """, 
            scene_agent, scene_achat_history)
    #
    print("[scene]:", scene_state)

    #
    event = f"""我进入了屋子，面色凝重"""
    print("[event]:", event)

    #
    print("[npc]:", talk_to_agent(
            f"""
# 场景
-{scene_state}
# 事件
-{event}
# 需求
-根据场景与事件输出对话。标志着村长与我的对话开始
            """, 
            npc_agent, npc_achat_history))




    while True:
        usr_input = input("[user input]: ")

        if "/quit" in usr_input:
            sys.exit()

        elif "/talk" in usr_input:
            real_input = parse_talk(usr_input)
            print("[you]:", real_input)
            print(
                '[npc]:', talk_to_agent(real_input, npc_agent, npc_achat_history)
            )

        else:
            real_input = parse_talk(usr_input)
            print("[default]:", real_input)
            print(
                '[npc]:', talk_to_agent(real_input, npc_agent, npc_achat_history)
            )


if __name__ == "__main__":
    print("==============================================")
    run_user_system()