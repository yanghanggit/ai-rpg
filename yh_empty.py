from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable
import sys
import re

#
def main():

    # str = f"""
    # [老猎人隐居的小木屋][stay]:...
    # [卡斯帕·艾伦德][stay][talk]:可能是时候再去外面看看世界了。
    # [小狗'短剑'][stay]:我想醒来，去看看卡斯帕。
    # """

    array = [
    "[闪电僵尸][fight][张三]:我要弄死你",
    "[老猎人隐居的小木屋][stay]:...",
    "[卡斯帕·艾伦德][stay][talk]:可能是时候再去外面看看世界了。",
    "[小狗'短剑'][stay]:我想醒来，去看看卡斯帕。"
    ]


    """
    - 如果你想攻击某个目标，那么你的输出格式为：“[fight][目标的名字]:...“，...代表着你本次攻击要说的话与心里活动。
    - 如果你想保持现状，那么你的输出格式为：“[stay][talk]：...“，...代表着你本次保持现状要说的话与心里活动。
    - 如果你想说话，那么你的输出格式为：“[stay][talk]:...“，...代表着你本次要说的话与心里活动。
    - 如果不在以上3种情况，就输出"[stay]:...", ...仅代表着你的心里活动。
    """

    for ss in array:
        print(ss)
        a, b = ss.split(':')
        # print(a)
        # print(b)


        extracted_elements = []
        pattern = r"\[(.*?)\]"
        matches = re.findall(pattern, a)
        for match in matches:
            extracted_elements.append(f"[{match}]")
            #print(match)

        print(extracted_elements)

        name = extracted_elements[0]
        actions = extracted_elements[1:]
        if actions[0] == "[fight]":
            #action = actions[0]
            target = actions[1]
            print(f"{name}=>{target}:{b}")

        elif actions[0] == "[stay]" or actions[0] == "[talk]":
            print(f"{name}:{b}")


        #
        # name = matches[0]
        # print(name)

        # #
        # actions = matches[1:]
        # actions = [f"[{action}]" for action in actions]
        # print(actions)
        


        print("==============================================")



    print("==============================================")

            
if __name__ == "__main__":
    print("==============================================")
    main()