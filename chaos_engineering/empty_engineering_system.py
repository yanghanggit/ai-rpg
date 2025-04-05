from chaos_engineering.chaos_engineering_system import IChaosEngineering
from typing import Any, final, override


@final
class EmptyChaosEngineeringSystem(IChaosEngineering):

    def __init__(self) -> None:
        super().__init__()

    @override
    def on_pre_new_game(self) -> None:
        pass

    @override
    def on_post_new_game(self) -> None:
        pass

    @override
    def initialize(self, execution_context: Any) -> None:
        pass
