from typing import final, Dict
from overrides import override
from pydantic import BaseModel
from ..entitas import Matcher, Entity, GroupEvent, ReactiveProcessor
from loguru import logger
from ..models import (
    HunterComponent,
    HunterShotUsedComponent,
    DeathComponent,
    WerewolfComponent,
    SeerComponent,
    WitchComponent,
    VillagerComponent,
    HunterShootAction,
    AppearanceComponent,
    MindEvent,
    NightKillTargetComponent,
    DayVoteOutComponent,
)
from ..chat_services.client import ChatClient
from ..utils import json_format
from ..utils.md_format import format_dict_as_markdown_list
from ..game.sdg_game import SDGGame


###############################################################################################################################################
def _generate_shoot_decision_prompt(target_options_mapping: Dict[str, str]) -> str:
    """创建猎人开枪决策提示"""
    response_sample = HunterShootDecisionResponse(
        target_name="目标玩家的名字，或者空字符串表示不开枪",
        reasoning="你选择这个目标（或选择不开枪）的详细推理过程，包括对该玩家身份的分析、威胁评估等。",
    )

    return f"""# 指令！你已经死亡，作为猎人，你现在可以选择开枪带走一名玩家。

## 当前可选的射击目标:

{format_dict_as_markdown_list(target_options_mapping)}

## 决策建议

作为猎人，你可以选择开枪或不开枪：

### 开枪策略：
1. **身份判断**: 优先射击你认为是狼人的玩家
2. **威胁评估**: 射击对好人阵营威胁最大的玩家
3. **信息利用**: 基于之前游戏过程中收集的信息做出判断
4. **阵营贡献**: 确保你的最后一枪能为好人阵营带来最大价值

### 不开枪策略：
1. **不确定性**: 如果你完全不确定谁是狼人，可以选择不开枪
2. **避免误伤**: 如果你担心会误杀好人，可以选择不开枪
3. **局势判断**: 如果场上人数很少且你不确定，不开枪可能更安全

## 注意事项

- 这是你唯一的机会，使用后你将彻底退出游戏
- 你可以选择不开枪，将 target_name 设置为空字符串即可
- 严格遵循推理机制

## 输出格式

### 标准示例

```json
{response_sample.model_dump_json()}
```

## 输出要求

请严格按照上述的 JSON 标准示例 格式输出！如果你决定开枪，必须从上述可选目标中选择一个作为target_name。如果决定不开枪，请将target_name设置为空字符串。"""


###############################################################################################################################################
@final
class HunterShootDecisionResponse(BaseModel):
    target_name: str
    reasoning: str


###############################################################################################################################################
@final
class HunterDeathActionSystem(ReactiveProcessor):
    """猎人死亡时的开枪推理系统（仅负责推理和决策）"""

    def __init__(self, game_context: SDGGame) -> None:
        super().__init__(game_context)
        self._game: SDGGame = game_context

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {
            Matcher(
                any_of=[NightKillTargetComponent, DayVoteOutComponent]
            ): GroupEvent.ADDED
        }

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        """只处理有猎人组件且刚死亡、且尚未开枪的实体"""
        return (
            (entity.has(DayVoteOutComponent) or entity.has(NightKillTargetComponent))
            and entity.has(HunterComponent)
            and not entity.has(HunterShotUsedComponent)
        )

    ###############################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        """猎人死亡开枪推理的主要执行逻辑"""

        for hunter_entity in entities:
            # 获取所有存活的玩家（猎人可以射击任何存活的玩家）
            alive_player_entities = self._game.get_group(
                Matcher(
                    any_of=[
                        WerewolfComponent,
                        SeerComponent,
                        WitchComponent,
                        VillagerComponent,
                    ],
                    none_of=[
                        DeathComponent,
                        NightKillTargetComponent,
                        DayVoteOutComponent,
                    ],
                )
            ).entities.copy()

            if len(alive_player_entities) == 0:
                logger.warning(
                    f"猎人 {hunter_entity.name} 死亡时没有存活的玩家，无法开枪"
                )
                continue

            # 执行猎人开枪决策推理
            await self._execute_hunter_shoot_decision(
                hunter_entity, alive_player_entities
            )

            # 标记猎人已经使用过技能（防止重复触发）
            hunter_entity.replace(HunterShotUsedComponent, hunter_entity.name)

    ###############################################################################################################################################
    async def _execute_hunter_shoot_decision(
        self, hunter_entity: Entity, alive_player_entities: set[Entity]
    ) -> None:
        """执行猎人开枪决策推理"""

        # 创建可选目标的外貌映射
        target_options_mapping = self._create_target_options_mapping(
            alive_player_entities
        )

        # 让猎人进行开枪决策推理
        target_name = await self._get_shoot_decision(
            hunter_entity, target_options_mapping, alive_player_entities
        )

        if target_name:
            # 添加射击动作组件到目标实体
            self._add_shoot_action(hunter_entity, target_name)
        else:
            logger.info(f"猎人 {hunter_entity.name} 选择不开枪")
            # 通知猎人选择不开枪
            self._game.notify_entities(
                set({hunter_entity}),
                MindEvent(
                    actor=hunter_entity.name,
                    message=f"# 猎人 {hunter_entity.name} 选择不开枪，平静地离开了游戏。",
                    content=f"# 猎人 {hunter_entity.name} 选择不开枪，平静地离开了游戏。",
                ),
            )

    ###############################################################################################################################################
    def _create_target_options_mapping(
        self, alive_player_entities: set[Entity]
    ) -> Dict[str, str]:
        """创建可选目标的外貌映射"""
        target_mapping = {}
        for entity in alive_player_entities:
            appearance_comp = entity.get(AppearanceComponent)
            if appearance_comp:
                target_mapping[entity.name] = appearance_comp.appearance
            else:
                target_mapping[entity.name] = "外貌未知"
        return target_mapping

    ###############################################################################################################################################
    async def _get_shoot_decision(
        self,
        hunter_entity: Entity,
        target_options_mapping: Dict[str, str],
        alive_player_entities: set[Entity],
    ) -> str:
        """让猎人进行开枪决策推理，返回目标名称（或空字符串表示不开枪）"""

        # 创建决策请求
        prompt = _generate_shoot_decision_prompt(target_options_mapping)
        agent_context = self._game.get_agent_context(hunter_entity)
        request_handler = ChatClient(
            name=hunter_entity.name,
            prompt=prompt,
            context=agent_context.context,
        )

        # 执行请求
        await ChatClient.gather_request_post(clients=[request_handler])

        # 处理响应
        target_name = self._process_shoot_decision_response(
            request_handler, alive_player_entities
        )

        if target_name:
            logger.info(f"猎人 {hunter_entity.name} 决定开枪射击: {target_name}")
        else:
            logger.info(f"猎人 {hunter_entity.name} 决定不开枪")

        return target_name

    ###############################################################################################################################################
    def _process_shoot_decision_response(
        self, request_handler: ChatClient, alive_player_entities: set[Entity]
    ) -> str:
        """处理猎人开枪决策响应，返回目标名称（或空字符串）"""
        try:
            response = HunterShootDecisionResponse.model_validate_json(
                json_format.strip_json_code_block(request_handler.response_content)
            )

            # 如果选择不开枪（空字符串）
            if not response.target_name or response.target_name.strip() == "":
                hunter_entity = self._game.get_entity_by_name(request_handler.name)
                if hunter_entity:
                    self._game.notify_entities(
                        set({hunter_entity}),
                        MindEvent(
                            message=f"经过你的思考，你决定不开枪。理由是：{response.reasoning}",
                            actor=hunter_entity.name,
                            content=f"经过你的思考，你决定不开枪。理由是：{response.reasoning}",
                        ),
                    )
                return ""

            # 验证目标是否有效
            if response.target_name not in [e.name for e in alive_player_entities]:
                logger.error(f"猎人选择的目标 {response.target_name} 不在可选列表中")
                return ""

            # 记录猎人的决策过程
            hunter_entity = self._game.get_entity_by_name(request_handler.name)
            if hunter_entity:
                self._game.notify_entities(
                    set({hunter_entity}),
                    MindEvent(
                        message=f"经过你的思考，你决定开枪射击 {response.target_name}。理由是：{response.reasoning}",
                        actor=hunter_entity.name,
                        content=f"经过你的思考，你决定开枪射击 {response.target_name}。理由是：{response.reasoning}",
                    ),
                )

            return response.target_name

        except Exception as e:
            logger.error(
                f"处理猎人 {request_handler.name} 的开枪决策响应时出现异常: {e}"
            )
            logger.error(f"原始响应内容: {request_handler.response_content}")
            return ""

    ###############################################################################################################################################
    def _add_shoot_action(self, hunter_entity: Entity, target_name: str) -> None:
        """添加射击动作到目标实体"""
        target_entity = self._game.get_entity_by_name(target_name)

        if target_entity is not None:
            # 添加射击动作组件
            target_entity.replace(
                HunterShootAction,
                target_entity.name,
                hunter_entity.name,
            )
            logger.info(f"猎人 {hunter_entity.name} 添加射击动作到 {target_name}")

    ###############################################################################################################################################
