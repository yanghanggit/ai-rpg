"""TUI Screen 基类：提供对 GameClient 实例的类型安全访问。"""

from typing import cast

from textual.screen import Screen

from .app import GameClient


class BaseGameScreen(Screen[None]):
    """所有游戏 Screen 的基类。

    Textual 的 Screen.app 属性静态类型为 App[object]，无法自动窄化为子类。
    此处将唯一一次不安全的 cast 集中在基类属性中，子类通过 self.game_client 访问。
    """

    @property
    def game_client(self) -> GameClient:
        # Textual 的 Screen.app 类型为 App[object]，在运行时它确实是 GameClient，
        # 故此 cast 安全——这是项目中唯一需要此绕过的集中点。
        return cast(GameClient, self.app)
