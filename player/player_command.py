from dataclasses import dataclass


@dataclass
class PlayerCommand:
    user: str = ""
    command: str = "/command"


if __name__ == "__main__":
    pass
