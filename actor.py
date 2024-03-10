from langchain_core.messages import HumanMessage, AIMessage
from langserve import RemoteRunnable

#
class Actor:
    def __init__(self, name: str):
        self.name = name   
        self.url = ""
        self.agent = None
        self.chat_history = None

    def connect(self, url: str)-> None:
        self.agent = RemoteRunnable(url)
        self.chat_history = []

    def call_agent(self, prompt: str) -> str:
        if self.agent == None:
            print(f"call_agent: {self.name} have no agent.")
            return ""
        if self.chat_history == None:
            print(f"call_agent: {self.name} have no chat history.")
            return ""
        response = self.agent.invoke({"input": prompt, "chat_history": self.chat_history})
        #print(f"{self.name} call_agent => ", response)
        self.chat_history.extend([HumanMessage(content=prompt), AIMessage(content=response['output'])])
        return response['output']
    
    def add_memory(self, content: str) -> bool:
        if self.chat_history == None:
            print(f"add_memory: {self.name} have no chat history.")
            return False
        self.chat_history.append(HumanMessage(content=content))
        return True






