from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable
import sys

def main():
    story_agent = RemoteRunnable("http://localhost:8008/story/")
    grandpa_agent = RemoteRunnable("http://localhost:8009/actor/npc/grandapa/")
    evaluate_agent = RemoteRunnable("http://localhost:8007/system/evaluate/")

    story_history = []
    chat_to_grandpa_history = []
    total_courage = 0
    background_story = ""

    print("进入main")
    print("-------------------")

    story_response = story_agent.invoke({"input": "故事开始.", "chat_history": story_history})
    story = AIMessage(content=story_response['output'])
    story_history.extend([HumanMessage(content="故事开始."), story])
    print("故事:" + story_response['output'])
    print("-------------------")

    while True:
        human = input("用户输入:")
        if "quit" in human:
            sys.exit()

        grandpa_response = grandpa_agent.invoke({"input": human
                                                 , "chat_history": chat_to_grandpa_history})
        grandpa = AIMessage(content=grandpa_response['output'])
        chat_to_grandpa_history.extend([HumanMessage(content=human), grandpa])   

        conversation = "冒险者说:" + human + ".\n祖父说:" + grandpa_response['output']
        inputs = f"""请将{conversation}里的内容进行整理并润色，然后输出"""      

        story_response = story_agent.invoke({"input": inputs, "chat_history": story_history})
        story = AIMessage(content=story_response['output'])
        story_history.extend([HumanMessage(content=conversation),story])

    
        courage_response = evaluate_agent.invoke({"input": story_response['output']})
        courage = courage_response['output']
        if (type(courage) == int):
            total_courage += courage 
        else:
            total_courage += 0

        print("故事:" + story_response['output'])
        print(f"放心程度:{total_courage}")
        print("----------")
        

        
        




if __name__ == "__main__":
    main()