class GUIDGenerator:

    def __init__(self, name: str) -> None:
        self._name: str = name
        self._index: int = 0

    def generate(self) -> int:
        self._index += 1
        return self._index
