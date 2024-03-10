###
### 测试与LLM无关的代码，和一些尝试
###


import sys
import json
import os

def main():


    file_path = "./items/test.json"
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            json_data = json.load(file)
            print(json_data)
    else:
        print("File does not exist.")

    #
    # while True:
    #     usr_input = input("[user input]: ")
    #     if "/quit" in usr_input:
    #         sys.exit()

            
    #     print("==============================================")

        

if __name__ == "__main__":
    main()