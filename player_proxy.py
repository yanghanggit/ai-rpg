
### 目前啥也不干，但留着有用的时候再用
class PlayerProxy:

    def __init__(self, name: str) -> None:
        self.name = name

    def __str__(self) -> str:
        return f'PlayerProxy({self.name})'
    


