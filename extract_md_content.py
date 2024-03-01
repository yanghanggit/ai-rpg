import os

def extract_md_content(file_path) -> str:
    try:
        file_path = os.getcwd() + "/prompts/" + file_path
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