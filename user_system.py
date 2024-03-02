from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable
import sys

def talk(input_val, npc_agent, chat_history):
    response = npc_agent.invoke({"input": input_val, "chat_history": chat_history})
    chat_history.extend([HumanMessage(content=input_val), AIMessage(content=response['output'])])
    return response['output']


def run_user_system():

    npc_agent = RemoteRunnable("http://localhost:8001/actor/npc/elder/")
    chat_history = []

    print(
         talk("故事开始", npc_agent, chat_history)
    )

    while True:
        usr_input = input("[you]: ")
        if "quit" in usr_input:
            sys.exit()

        print(
            '[npc]:', talk(usr_input, npc_agent, chat_history)
        )



if __name__ == "__main__":
    run_user_system()