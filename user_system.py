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

    npc_agent = RemoteRunnable("http://localhost:8001/actor/npc/elder/")
    chat_history = []

    print(
         talk_to_agent("故事开始", npc_agent, chat_history)
    )
    print("---------------------------------------------------")


    while True:
        usr_input = input("[user input]: ")
        print("---------------------------------------------------")
        if "quit" in usr_input:
            sys.exit()
        

        if "/talk" in usr_input:
            real_input = parse_talk(usr_input)
            print("[you say]:", real_input)
            print(
                '[npc say]:', talk_to_agent(real_input, npc_agent, chat_history)
            )
        else:
            print("error command!")


        print("---------------------------------------------------")

if __name__ == "__main__":
    run_user_system()