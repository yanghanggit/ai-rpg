import pandas as pd
from auxiliary.extract_md_content import extract_md_content
import os
from loguru import logger
from typing import Any
from pandas import DataFrame


def read_md(file_path: str) -> str:
    try:
        file_path = os.getcwd() + file_path
        with open(file_path, 'r', encoding='utf-8') as file:
            md_content = file.read()
            if isinstance(md_content, str):
                return md_content
            else:
                logger.error(f"Failed to read the file:{md_content}")
                return ""
    except FileNotFoundError:
        return f"File not found: {file_path}"
    except Exception as e:
        return f"An error occurred: {e}"


class TblNpc:

    def __init__(self, name: str, codename: str, description: str, history: str) -> None:
        self.name = name
        self.codename = codename
        self.description = description
        self.history = history

    def __str__(self) -> str:
        return f"TblNpc({self.name}, {self.codename}, {self.description}, {self.history})"
        
      




def main() -> None:
    print("Hello, World!")

    try:
        # 读取xlsx文件
        df = pd.read_excel('budding_world/budding_world.xlsx', engine='openpyxl')
        print(df)
        # 将DataFrame转换为JSON，禁用ASCII强制转换
        json_data: DataFrame = df.to_json(orient='records', force_ascii=False)
        for index, row in df.iterrows():
            #print(row["name"], row["codename"], row["description"], row["history"])

            tblnpc = TblNpc(row["name"], row["codename"], row["description"], row["history"])
            print(tblnpc)
        print("________________________________________________________________________")


        print(json_data)
        print("________________________________________________________________________")

        npc_temp = read_md("/budding_world/gen_npc_template.md")

        print(npc_temp)



    except Exception as e:
        print("读取Excel文件时出现问题：", e)
        #logger.exception(e)
        return

if __name__ == "__main__":
    main()
