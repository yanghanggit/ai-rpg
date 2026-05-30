from typing import Final, List, final
from loguru import logger
from overrides import override
from ..deepseek import DeepSeekClient
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from ..models import ActorComponent, AppearanceComponent, CostumeComponent
from ..models.items import CostumeItem
from .update_appearance_action_system import _build_appearance_synthesis_prompt


#######################################################################################################################################
@final
class ActorAppearanceInitSystem(ExecuteProcessor):
    """角色外观初始化系统（Init 语义）。

    每次管道启动时，检查所有穿戴时装但 appearance == base_body 的角色实体，
    重新触发 LLM 合成外观描述，确保存档恢复后外观与穿戴状态保持一致。
    """

    def __init__(self, game: TCGGame) -> None:
        self._game: Final[TCGGame] = game

    #######################################################################################################################################
    @override
    async def execute(self) -> None:
        await self._synthesize_costume_appearances()

    #######################################################################################################################################
    async def _synthesize_costume_appearances(self) -> None:
        """找出 appearance == base_body 且穿戴时装的角色，批量重新合成外观描述。"""

        entities = self._game.get_group(
            Matcher(all_of=[ActorComponent, AppearanceComponent, CostumeComponent])
        ).entities

        # 筛选出外观未初始化（appearance == base_body）的实体
        targets: List[Entity] = [
            entity
            for entity in entities
            if entity.get(AppearanceComponent).appearance
            == entity.get(AppearanceComponent).base_body
        ]

        if not targets:
            logger.debug("ActorAppearanceInitSystem: 无需初始化外观，跳过")
            return

        # 为每个目标实体构建提示词并创建 DeepSeekClient 实例
        clients: List[DeepSeekClient] = []
        for entity in targets:
            appearance_comp = entity.get(AppearanceComponent)
            costume: CostumeItem = entity.get(CostumeComponent).item
            prompt = _build_appearance_synthesis_prompt(
                base_body=appearance_comp.base_body,
                costume_name=costume.name,
                costume_description=costume.description,
            )
            clients.append(
                DeepSeekClient(
                    name=entity.name,
                    prompt=prompt,
                    context=self._game.get_agent_context(entity).context,
                )
            )

        # 批量请求 LLM 合成外观描述
        await DeepSeekClient.batch_chat(clients)

        # 将合成结果更新回角色外观组件
        for entity, client in zip(targets, clients):
            appearance_comp = entity.get(AppearanceComponent)
            costume = entity.get(CostumeComponent).item
            new_appearance = client.response_content.strip()
            if not new_appearance:
                logger.warning(
                    f"ActorAppearanceInitSystem: LLM 返回空，角色 {entity.name} 退回简单拼接"
                )
                new_appearance = f"{appearance_comp.base_body}，{costume.description}"
            entity.replace(
                AppearanceComponent,
                appearance_comp.name,
                appearance_comp.base_body,
                new_appearance,
            )
            logger.debug(
                f"ActorAppearanceInitSystem: 角色 {entity.name} 外观已恢复合成，时装 {costume.name!r}"
            )

    #######################################################################################################################################
