"""战斗掉落系统：怪物各自推断掉落，结果汇总进玩家的战利品。"""

from typing import Final, List, final

from loguru import logger
from overrides import override
from pydantic import BaseModel

from ..deepseek import DeepSeekClient
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.dbg_game import DBGGame
from ..llm import ChatClientProtocol, batch_chat
from ..models import (
    AnyItem,
    AppearanceComponent,
    HumanMessage,
    LootComponent,
    MaterialItem,
    MonsterComponent,
    PartyMemberComponent,
)
from ..utils import extract_json, prompt_builder


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
@prompt_builder
def _build_loot_prompt(
    monster_name: str, appearance: str, stage_name: str, total_rounds: int
) -> str:
    """构建怪物掉落推理 prompt。"""
    return f"""# 战斗结束，推断战利品掉落

你刚刚在 {stage_name} 经历了 {total_rounds} 回合战斗并被击败。

## 你的外观

{appearance}

---

## 任务一：基础掉落
根据你的外观，推断击败后**必然掉落**的材料（1-2件）。
- 从外观中识别最具代表性的构成要素——可能是生物组织、构造材料、残留物或蕴含物
- 材料的感官描述应呼应外观中的具体细节

## 任务二：构成破坏额外掉落
根据你的外观，识别 1-3 个**可破坏的构成部分**（可能是身体部位、组成构件、附着物或结构弱点）。

**回顾上方的战斗历史**，对每个构成部分判断：
- 该部分在战斗中是否被集中攻击、切断或严重破坏？
- 判断依据：攻击描述、伤害叙事、状态效果，而非简单累加伤害数字
- 若**破坏成立**（`broken: true`），生成 1 件该部分对应的特殊材料
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
      "part_name": "XXX",
      "broken": true,
      "materials": [
        {{
          "name": "材料.XXX",
          "description": "20-40字，体现破坏痕迹",
          "count": 1
        }}
      ]
    }}
  ]
}}
```

**命名规范**：所有 `name` 采用「材料.XXX」格式，XXX 为 2-4 字材料简称，体现来源与特征。
严格按 JSON 格式输出，不要添加其他内容。"""


#######################################################################################################################################
@prompt_builder
def _build_loot_message(loot_items: List[AnyItem]) -> str:
    """生成「你获得了什么」的自我状态说明（只写给本人，不广播）。"""
    lines = ["# 你的战利品", "战斗结束后，你收集到了："]
    lines.extend(
        f"- {item.name} ×{item.count}：{item.description}" for item in loot_items
    )
    return "\n".join(lines)


#######################################################################################################################################
@final
class CombatLootSystem(ExecuteProcessor):
    """战斗掉落系统（仿怪物猎人机制）。"""

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    #######################################################################################################################################
    @override
    async def execute(self) -> None:
        """每帧检查战斗是否胜利结束；未胜利则直接返回，胜利则推理掉落并写入 LootComponent。"""
        if not self._game.current_dungeon_combat_room.combat.is_combat_completed:
            return

        if not self._game.current_dungeon_combat_room.combat.is_won:
            return

        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "无法获取玩家实体，掉落流程异常！"
        assert player_entity.has(
            PartyMemberComponent
        ), "玩家实体缺少 PartyMemberComponent"

        # 获取当前战斗场景中的所有怪物实体
        monsters = list(
            self._game.get_actors_in_stage(
                player_entity, Matcher(all_of=[MonsterComponent])
            )
        )

        # 为每头怪物创建 LLM 客户端并推理掉落，解析结果后写入玩家 LootComponent
        clients = [self._create_loot_client(m) for m in monsters]

        # 并行调用 LLM 推理所有怪物掉落
        await batch_chat(clients=clients)

        # 逐头记账：先留痕（与 MonsterPrePlaySystem 一致，写入 prompt 与 AI 原文），再解析掉落
        loot_items: List[AnyItem] = []
        for monster, client in zip(monsters, clients):
            self._record_loot_memory(monster, client)
            loot_items.extend(self._parse_loot_item(client))

        # 将掉落物写入玩家 LootComponent
        player_entity.replace(LootComponent, player_entity.name, loot_items)
        logger.info(
            f"[CombatLootSystem] 掉落完成，共 {len(loot_items)} 件战利品写入 LootComponent"
        )

        # 让玩家知道自己拿到什么：只写给本人（战利品尚未领取，不对外广播）
        if loot_items:
            stage_entity = self._game.resolve_stage_entity(player_entity)
            assert (
                stage_entity is not None
            ), "CombatLootSystem: 无法找到玩家所在场景实体"
            self._game.add_human_message(
                entity=player_entity,
                human_message=HumanMessage(
                    content=_build_loot_message(loot_items),
                    combat_loot_items=stage_entity.name,
                ),
            )

    #######################################################################################################################################
    def _record_loot_memory(self, monster: Entity, client: ChatClientProtocol) -> None:
        """把掉落推理写回怪物记忆（human = 请求原文，ai = 回包原文）。

        怪物在战斗中所有以自己为主体的 LLM 推理（出牌决策 / 掉落）均留痕，
        记忆管理策略因此统一；失败（无回包）时只留请求侧，不伪造 AI 回复。
        """
        self._game.add_human_message(
            entity=monster,
            human_message=HumanMessage(
                content=client.input_message,
                combat_loot_reasoning=monster.name,
            ),
        )
        if client.response_ai_message is None:
            logger.warning(f"[CombatLootSystem] {monster.name} 无 AI 回包，仅记录请求")
            return
        self._game.add_ai_message(monster, client.response_ai_message)

    #######################################################################################################################################
    def _create_loot_client(self, monster: Entity) -> DeepSeekClient:
        """为单头怪物创建配置好的 DeepSeekClient，传入其消息历史。"""
        total_rounds = len(self._game.current_dungeon_combat_room.combat.rounds or [])

        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        stage_entity = self._game.resolve_stage_entity(player_entity)
        assert stage_entity is not None, "CombatLootSystem: 无法找到玩家所在场景实体"
        stage_name = stage_entity.name

        appearance_comp = monster.get(AppearanceComponent)
        assert (
            appearance_comp is not None
        ), f"CombatLootSystem: 怪物 {monster.name} 缺少 AppearanceComponent"
        return DeepSeekClient(
            label=monster.name,
            input_message=_build_loot_prompt(
                monster.name, appearance_comp.appearance, stage_name, total_rounds
            ),
            messages=self._game.get_agent_memory(monster).messages,
        )

    #######################################################################################################################################
    def _parse_loot_item(self, client: ChatClientProtocol) -> List[AnyItem]:
        """解析单头怪物的 LLM 响应，返回基础掉落与部位破坏额外掉落。

        入参按协议标注：只需 label / response_content。
        """
        items: List[AnyItem] = []

        if not client.response_content:
            logger.error(f"[CombatLootSystem] {client.label} LLM 响应为空，跳过掉落")
            return items

        try:
            json_str = extract_json(client.response_content)
            response = _MonsterLootResponse.model_validate_json(json_str)
        except Exception as e:
            logger.error(
                f"[CombatLootSystem] 解析 {client.label} 掉落响应失败: {e}\n原始内容:\n{client.response_content}"
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
                f"[CombatLootSystem] {client.label} 基础掉落: {entry.name} x{entry.count}"
            )

        # 部位破坏额外掉落
        for part in response.part_breaks:
            if not part.broken:
                logger.debug(
                    f"[CombatLootSystem] {client.label} 部位 [{part.part_name}] 未破坏，无额外掉落"
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
                    f"[CombatLootSystem] {client.label} 部位破坏 [{part.part_name}] 额外掉落: {entry.name} x{entry.count}"
                )

        return items
