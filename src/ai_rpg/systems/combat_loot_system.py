"""战斗掉落系统。"""

from typing import Final, List, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
from ..entitas import Entity, ExecuteProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    AppearanceComponent,
    CombatLootComponent,
    MonsterComponent,
    PartyMemberComponent,
)
from ..models.items import AnyItem, MaterialItem
from ..utils import extract_json_from_code_block


#######################################################################################################################################
class _LootEntry(BaseModel):
    """LLM 单件掉落条目。"""

    name: str = ""
    description: str = ""
    count: int = 1


#######################################################################################################################################
class _PartBreakEntry(BaseModel):
    """单个可破坏部位的判定结果。"""

    part_name: str = ""  # 部位名称（如"尾巴"、"左翼"）
    broken: bool = False  # 战斗中是否被破坏
    materials: List[_LootEntry] = []  # 部位破坏时的额外掉落


#######################################################################################################################################
class _MonsterLootResponse(BaseModel):
    """LLM 掉落推理完整响应。"""

    base_materials: List[_LootEntry] = []  # 基础掉落（必然产生）
    part_breaks: List[_PartBreakEntry] = []  # 部位破坏判定与额外掉落


#######################################################################################################################################
def _build_loot_prompt(
    monster_name: str, appearance: str, stage_name: str, total_rounds: int
) -> str:
    """构建怪物掉落推理 prompt。

    Args:
        monster_name: 怪物名称
        appearance: 怪物外观描述
        stage_name: 战斗场景名称
        total_rounds: 本场战斗总回合数
    """
    return f"""# 战斗结束，推断战利品掉落

你刚刚在 {stage_name} 经历了 {total_rounds} 回合战斗并被击败。

## 你的外观

{appearance}

---

## 任务一：基础掉落
根据你的生物特征，推断击败后**必然掉落**的材料（1-2件，无论战斗过程如何）。
- 通常是该生物最具代表性的身体材料，如皮、骨、鳞片、甲壳、体液等
- 即便战斗过程平淡，也应有基础产出

## 任务二：部位破坏额外掉落
根据你的外观，识别 1-3 个**可破坏的身体部位**（如尾巴、翅膀、角、眼睛等），然后：

**回顾上方的战斗历史**，对每个部位判断：
- 该部位在战斗中是否被集中攻击、切断或严重破坏？
- 判断依据：攻击描述、伤害叙事、状态效果，而非简单累加伤害数字
- 若**部位破坏成立**（`broken: true`），生成 1 件该部位对应的特殊材料
- 若破坏**未成立**（`broken: false`），`materials` 输出 `[]`

---

## 输出格式

```json
{{
  "base_materials": [
    {{
      "name": "材料.XXX",
      "description": "20-40字，描述外观与质感",
      "count": 1
    }}
  ],
  "part_breaks": [
    {{
      "part_name": "尾巴",
      "broken": true,
      "materials": [
        {{
          "name": "材料.XXX断尾",
          "description": "20-40字，体现战斗破坏痕迹",
          "count": 1
        }}
      ]
    }},
    {{
      "part_name": "左翼",
      "broken": false,
      "materials": []
    }}
  ]
}}
```

**命名规范**：所有 `name` 采用「材料.怪物简称+部位/特征」格式（如「材料.石缝蜥鳞片」「材料.石缝蜥断尾」）。
严格按 JSON 格式输出，不要添加其他内容。"""


#######################################################################################################################################
@final
class CombatLootSystem(ExecuteProcessor):
    """战斗掉落系统（仿怪物猎人机制）。"""

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    #######################################################################################################################################
    @override
    async def execute(self) -> None:
        """每帧检查战斗是否胜利结束；未胜利则直接返回，胜利则推理掉落并写入 CombatLootComponent。"""
        if not self._game.current_combat_room.combat.is_combat_completed:
            return

        if not self._game.current_combat_room.combat.is_won:
            return

        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "无法获取玩家实体，掉落流程异常！"
        # if player_entity is None:
        #     logger.error("[CombatLootSystem] 无法获取玩家实体，跳过掉落流程")
        #     return

        assert player_entity.has(
            PartyMemberComponent
        ), "玩家实体缺少 PartyMemberComponent"

        # 获取当前战斗场景中的所有怪物实体
        actors = self._game.get_actors_in_stage(player_entity)
        monsters = [e for e in actors if e.has(MonsterComponent)]

        # 为每头怪物创建 LLM 客户端并推理掉落，解析结果后写入玩家 CombatLootComponent
        clients = [self._create_loot_client(m) for m in monsters]

        # 并行调用 LLM 推理所有怪物掉落
        await DeepSeekClient.batch_chat(clients=clients)

        # 解析所有怪物的掉落结果，合并基础掉落与部位破坏额外掉落
        loot_items = [
            item for client in clients for item in self._parse_loot_item(client)
        ]

        # 将掉落物写入玩家 CombatLootComponent
        player_entity.replace(CombatLootComponent, player_entity.name, loot_items)
        logger.info(
            f"[CombatLootSystem] 掉落完成，共 {len(loot_items)} 件战利品写入 CombatLootComponent"
        )

    #######################################################################################################################################
    def _create_loot_client(self, monster: Entity) -> DeepSeekClient:
        """为单头怪物创建配置好的 DeepSeekClient，传入其战斗上下文。

        Args:
            monster: 怪物实体

        Returns:
            配置好的 DeepSeekClient
        """
        total_rounds = len(self._game.current_combat_room.combat.rounds or [])

        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        stage_entity = self._game.resolve_stage_entity(player_entity)
        stage_name = stage_entity.name if stage_entity is not None else "未知场景"

        appearance = (
            monster.get(AppearanceComponent).appearance
            if monster.has(AppearanceComponent)
            else monster.name
        )
        return DeepSeekClient(
            name=monster.name,
            prompt=_build_loot_prompt(
                monster.name, appearance, stage_name, total_rounds
            ),
            context=self._game.get_agent_context(monster).context,
        )

    #######################################################################################################################################
    def _parse_loot_item(self, client: DeepSeekClient) -> List[AnyItem]:
        """解析单头怪物的 LLM 响应，返回基础掉落与部位破坏额外掉落。

        解析失败时记录 error 日志并返回空列表。

        Args:
            client: 已完成 LLM 调用的客户端

        Returns:
            该怪物的全部掉落物列表
        """
        items: List[AnyItem] = []

        if not client.response_content:
            logger.error(f"[CombatLootSystem] {client.name} LLM 响应为空，跳过掉落")
            return items

        try:
            json_str = extract_json_from_code_block(client.response_content)
            response = _MonsterLootResponse.model_validate_json(json_str)
        except Exception as e:
            logger.error(
                f"[CombatLootSystem] 解析 {client.name} 掉落响应失败: {e}\n"
                f"原始内容:\n{client.response_content}"
            )
            return items

        # 基础掉落（必然产生）
        for entry in response.base_materials:
            if not entry.name:
                continue
            items.append(
                MaterialItem(
                    name=entry.name,
                    description=entry.description,
                    count=max(1, entry.count),
                )
            )
            logger.info(
                f"[CombatLootSystem] {client.name} 基础掉落: {entry.name} x{entry.count}"
            )

        # 部位破坏额外掉落
        for part in response.part_breaks:
            if not part.broken:
                logger.debug(
                    f"[CombatLootSystem] {client.name} 部位 [{part.part_name}] 未破坏，无额外掉落"
                )
                continue
            for entry in part.materials:
                if not entry.name:
                    continue
                items.append(
                    MaterialItem(
                        name=entry.name,
                        description=entry.description,
                        count=max(1, entry.count),
                    )
                )
                logger.info(
                    f"[CombatLootSystem] {client.name} 部位破坏 [{part.part_name}] 额外掉落: {entry.name} x{entry.count}"
                )

        return items
