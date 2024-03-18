import os

def extract_md_content(file_path: str) -> str:
    """提取md内容。文件路径示例: /xxx/xxx.md"""
    try:
        file_path = os.getcwd() + "/prompts" + file_path
        with open(file_path, 'r', encoding='utf-8') as file:
            md_content = file.read()
            if isinstance(md_content, str):
                return md_content
            else:
                print("Failed to read the file:", md_content)
                return ""
    except FileNotFoundError:
        return f"File not found: {file_path}"
    except Exception as e:
        return f"An error occurred: {e}"
    

def wirte_content_into_md(content:str, file_path:str) -> None:
    """将md内容写入.md文件。文件路径示例:/xxx/xxx.md"""
    try:
        file_path = os.getcwd() + "/prompts" + file_path
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)
    except Exception as e:
        print(f"An error occurred: {e}")
