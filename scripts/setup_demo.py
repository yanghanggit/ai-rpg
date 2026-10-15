#!/usr/bin/env python3
"""
开发环境初始化脚本
"""

import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Final, List, Optional, final

from loguru import logger
from pydantic import BaseModel

from ai_rpg.embedding_model.sentence_transformer import embedding_model
from ai_rpg.models import (
    Blueprint,
    Dungeon,
)
from ai_rpg.models.entities import Stage, World
from ai_rpg.paths import BLUEPRINTS_DIR, DUNGEONS_DIR
from ai_rpg.pgsql import (
    pgsql_create_database,
    pgsql_drop_database,
    pgsql_ensure_database_tables,
    postgresql_config,
    procrastinate_app,
    save_card_prototype,
    save_deck_build,
)
from ai_rpg.pgsql.user_operations import has_user, save_user
from ai_rpg.rag import add_documents
from demo import (
    CARD_PROTOTYPES,
    DEFAULT_DECK_BUILD,
    create_beast_lair_dungeon,
    create_demo_blueprint,
)


#######################################################################################################
@final
class UserAccount(BaseModel):
    username: str
    hashed_password: str
    display_name: str


########################################################################################################
########################################################################################################
########################################################################################################
TEST_USER = UserAccount(
    username="yanghangethan@gmail.com",
    hashed_password="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # 明文是 secret
    display_name="yh",
)

###########################################################################################################################################
# 默认游戏名称
GAME_1: Final[str] = (
    "Game1"  # unity 客户端目前是一定会链接到这个游戏的，所以这个名字暂时不能改。
)

###########################################################################################################################################
# 系统提示词快照输出目录（项目根目录下）
DEBUG_CACHE_DIR: Final[Path] = Path(".debug_cache")
DEBUG_CACHE_DIR.mkdir(parents=True, exist_ok=True)
assert DEBUG_CACHE_DIR.exists(), f"找不到目录: {DEBUG_CACHE_DIR}"


########################################################################################################
########################################################################################################
########################################################################################################
def _setup_dungeons() -> List[Dungeon]:
    """将演示副本序列化为 JSON 文件，存入 DUNGEONS_DIR"""
    logger.info("🚀 保存演示副本...")

    dungeons = [
        create_beast_lair_dungeon(),  # 荒狼巢副本
    ]

    for dungeon in dungeons:
        path = DUNGEONS_DIR / f"{dungeon.name}.json"
        path.write_text(dungeon.model_dump_json(indent=4), encoding="utf-8")
        logger.success(f"✅ {dungeon.name}.json 已保存至 {path.absolute()}")

    return dungeons


########################################################################################################
########################################################################################################
########################################################################################################
def _setup_blueprints() -> Blueprint:
    """将演示游戏世界蓝图序列化为 JSON 文件，存入 BLUEPRINTS_DIR"""
    logger.info("🚀 保存演示游戏蓝图...")

    blueprint_game1 = create_demo_blueprint(GAME_1)
    path_game1 = BLUEPRINTS_DIR / f"{GAME_1}.json"
    path_game1.write_text(blueprint_game1.model_dump_json(indent=4), encoding="utf-8")
    logger.success(f"✅ {GAME_1}.json 已保存至 {path_game1.absolute()}")

    return blueprint_game1


########################################################################################################
########################################################################################################
########################################################################################################
def _collect_entity_records(
    stages: List[Stage], worlds: List[World]
) -> List[tuple[str, str, str]]:
    """收集若干 Stage / Actor / World 的 (类型, 名称, system_message)。

    Actor 内嵌于 Stage，故一并提取。
    """
    records: List[tuple[str, str, str]] = []

    def _add(kind: str, name: str, system_message: str) -> None:
        records.append((kind, name, system_message or ""))

    for stage in stages:
        _add("Stage", stage.name, stage.system_message)
        for actor in stage.actors:
            _add("Actor", actor.name, actor.system_message)

    for world in worlds:
        _add("World", world.name, world.system_message)

    return records


########################################################################################################
def _render_system_message_markdown(
    kind: str, name: str, scope: str, system_message: str
) -> str:
    """将 system_message 渲染为无 markdownlint 告警的 md 文本。

    system_message 是任意 AI 提示词，其内部可能包含尾随空格、强调式小节标题、列表等
    会被 markdownlint 判为告警的写法。为了原样保留提示词、又让文件本身“干净”，这里把正文
    包进带 ``text`` 语言的围栏代码块：代码块内部不再参与行内规则的校验。
    围栏反引号数量动态取自正文中最长的反引号串，避免正文提前闭合代码块。
    """
    message = system_message or ""
    longest_backtick_run = max(
        (len(run) for run in re.findall(r"`+", message)), default=0
    )
    fence = "`" * max(3, longest_backtick_run + 1)

    # 首行用一级标题，满足 markdownlint 默认的 MD041；前后各留一个空行（MD031）；
    # 文件以单个换行结尾（MD047）。
    return (
        f"# {kind}: {name}\n\n"
        f"<!-- scope: {scope} -->\n\n"
        f"{fence}text\n"
        f"{message}\n"
        f"{fence}\n"
    )


########################################################################################################
def _write_records(
    records: List[tuple[str, str, str]], out_dir: Path, scope: str
) -> List[str]:
    """将记录逐个写为 md 文件，返回用于索引的文本行。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    index_lines: List[str] = []

    for idx, (kind, name, system_message) in enumerate(records, start=1):
        safe_name = name.replace("/", "_").replace("\\", "_")
        file_name = f"{idx:02d}_{kind}_{safe_name}.md"
        (out_dir / file_name).write_text(
            _render_system_message_markdown(kind, name, scope, system_message),
            encoding="utf-8",
        )
        index_lines.append(f"- [{kind}] {name} → `{file_name}`")

    return index_lines


########################################################################################################
def _dump_system_messages(blueprint: Blueprint, dungeons: List[Dungeon]) -> None:
    """将每个 Actor / Stage / World / Artifact 的 system_message 写入 .debug_cache。

    容器文件夹命名规则：``<Blueprint.name>_<时间戳>``。其中：
    - ``blueprint/``：蓝图自带的 Stage / Actor / World / Artifact
    - ``dungeons/<副本名>/``：各副本房间内的 Stage / Actor / Artifact

    每个实体的提示词单独存为一个 md 文件，方便开发者在 setup 之后人工通读最终系统提示词。
    """
    logger.info("🚀 导出系统提示词快照...")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dump_dir = DEBUG_CACHE_DIR / f"{blueprint.name}_{timestamp}"
    dump_dir.mkdir(parents=True, exist_ok=True)

    index_lines = [
        f"# {blueprint.name} 系统提示词快照",
        "",
        f"- 生成时间：{timestamp}",
        "",
    ]

    # 蓝图实体
    blueprint_records = _collect_entity_records(
        blueprint.stages, blueprint.world_entities
    )
    index_lines.append(f"## Blueprint（{len(blueprint_records)} 个实体）")
    index_lines.append("")
    index_lines += _write_records(
        blueprint_records, dump_dir / "blueprint", blueprint.name
    )
    index_lines.append("")

    # 副本实体
    total = len(blueprint_records)
    for dungeon in dungeons:
        records = _collect_entity_records([room.stage for room in dungeon.rooms], [])
        total += len(records)
        index_lines.append(f"## Dungeon: {dungeon.name}（{len(records)} 个实体）")
        index_lines.append("")
        index_lines += _write_records(
            records, dump_dir / "dungeons" / dungeon.name, dungeon.name
        )
        index_lines.append("")

    index_lines.insert(3, f"- 实体总数：{total}")
    (dump_dir / "_index.md").write_text(
        "\n".join(index_lines).rstrip("\n") + "\n", encoding="utf-8"
    )
    logger.success(f"✅ 已导出 {total} 个系统提示词至 {dump_dir.absolute()}")


########################################################################################################
########################################################################################################
########################################################################################################
async def _apply_procrastinate_schema() -> None:
    """创建 Procrastinate 任务队列所需的表结构"""
    async with procrastinate_app.open_async():
        await procrastinate_app.schema_manager.apply_schema_async()


########################################################################################################
########################################################################################################
########################################################################################################
def _setup_user() -> None:
    """检查并创建测试用户账号"""
    logger.info("🚀 检查并保存测试用户...")
    if not has_user(TEST_USER.username):
        save_user(
            username=TEST_USER.username,
            hashed_password=TEST_USER.hashed_password,
            display_name=TEST_USER.display_name,
        )
        logger.info(f"测试用户 {TEST_USER.username} 已创建")
    else:
        logger.info(f"测试用户 {TEST_USER.username} 已存在，跳过创建")


########################################################################################################
########################################################################################################
########################################################################################################
def _setup_rag() -> None:
    """
    初始化 RAG 系统

    注意：vector_documents 表已在 PostgreSQL 初始化阶段随数据库一并重建，此处无需再清空。
    """
    logger.info("🚀 初始化RAG系统...")

    # 读取 BLUEPRINTS_DIR 下所有蓝图文件为 Blueprint 实例
    blueprints = [
        Blueprint.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(BLUEPRINTS_DIR.glob("*.json"))
    ]
    logger.info(f"📂 发现蓝图文件: {[blueprint.name for blueprint in blueprints]}")

    if not blueprints:
        logger.warning("⚠️ BLUEPRINTS_DIR 下没有蓝图文件，跳过RAG加载")
        logger.success("✅ RAG系统初始化完成!")
        return

    # 为每个蓝图分别加载其自带的知识库
    for blueprint in blueprints:
        if not blueprint.knowledge_base:
            logger.warning(f"⚠️ 蓝图 {blueprint.name} 的知识库为空，跳过加载")
            continue

        # 准备文档数据：将 Dict[str, List[str]] 展开为 flat lists
        documents_list: List[str] = []
        metadatas_list: List[Dict[str, str]] = []

        for category, docs in blueprint.knowledge_base.items():
            for doc in docs:
                documents_list.append(doc)
                metadatas_list.append({"category": category})

        logger.info(f"📚 为 {blueprint.name} 加载知识库...")
        success = add_documents(
            collection=blueprint.name,
            embedding_model=embedding_model,
            documents=documents_list,
            metadatas=metadatas_list,
        )
        if not success:
            logger.error(f"❌ {blueprint.name} 知识库加载失败!")
            raise Exception(f"{blueprint.name} 知识库加载失败")
        logger.success(f"✅ {blueprint.name} 知识库加载成功!")

    logger.success("✅ RAG系统初始化完成!")


def _setup_card_prototypes() -> None:
    """将卡牌原型刷入 PostgreSQL，供后续 Agent 检索「选择核心 + 润色」。"""
    logger.info("🚀 初始化卡牌原型...")

    for proto in CARD_PROTOTYPES:
        save_card_prototype(
            prototype_id=proto.meta.prototype_id,
            card_type=proto.meta.card_type,
            archetype=proto.meta.archetype,
            archetype_subtype=proto.meta.archetype_subtype,
            name=proto.meta.name,
            summary=proto.meta.summary,
            guide=proto.meta.guide,
            card_json=proto.skeleton.model_dump_json(),
            keywords=list(proto.meta.keywords),
        )
        logger.info(
            f"📥 卡牌原型已入库: {proto.meta.prototype_id}"
            f"（{proto.meta.card_type}/{proto.meta.archetype}/{proto.meta.archetype_subtype}）"
        )

    logger.success(f"✅ 卡牌原型初始化完成（{len(CARD_PROTOTYPES)} 个）")


########################################################################################################
def _setup_deck_build() -> None:
    """将默认牌单刷入 PostgreSQL，作为牌库组建失败时的兜底牌库。"""
    logger.info("🚀 初始化默认牌单...")

    known_ids = {proto.meta.prototype_id for proto in CARD_PROTOTYPES}
    for prototype_id in DEFAULT_DECK_BUILD.card_prototype_ids:
        assert (
            prototype_id in known_ids
        ), f"默认牌单引用了不存在的原型 id: {prototype_id}"

    save_deck_build(list(DEFAULT_DECK_BUILD.card_prototype_ids))
    logger.success(
        f"✅ 默认牌单初始化完成（{len(DEFAULT_DECK_BUILD.card_prototype_ids)} 张）"
    )


########################################################################################################
########################################################################################################
def main() -> None:
    """主函数：执行完整的开发环境初始化流程"""

    logger.info("🚀 开始初始化开发环境...")

    blueprint_game1: Optional[Blueprint] = None
    dungeons: List[Dungeon] = []

    try:
        # 保存演示游戏蓝图
        blueprint_game1 = _setup_blueprints()

        # 保存演示副本
        dungeons = _setup_dungeons()

    except Exception as e:
        logger.error(f"❌ 保存演示游戏蓝图或副本失败: {e}")

    try:
        # 导出所有实体的 system_message 快照，供开发期人工审阅
        if blueprint_game1 is not None:
            _dump_system_messages(blueprint_game1, dungeons)
    except Exception as e:
        logger.error(f"❌ 导出系统提示词快照失败: {e}")

    try:
        # PostgreSQL 相关操作
        logger.info("🗑️ 删除旧数据库（如果存在）...")
        pgsql_drop_database(postgresql_config.database)

        logger.info("📦 创建新数据库...")
        pgsql_create_database(postgresql_config.database)

        logger.info("📋 创建数据库表结构...")
        pgsql_ensure_database_tables()

        logger.info("🧱 创建 Procrastinate 任务队列表结构...")
        asyncio.run(_apply_procrastinate_schema())

        logger.info("👤 设置PostgreSQL测试用户...")
        _setup_user()

        logger.info("🎴 初始化卡牌原型...")
        _setup_card_prototypes()

        logger.info("🃏 初始化默认牌单...")
        _setup_deck_build()

        logger.info("🚀 初始化RAG系统...")
        _setup_rag()

        logger.success("✅ PostgreSQL 初始化完成")

    except Exception as e:
        logger.error(f"❌ PostgreSQL 初始化失败: {e}")

    logger.info("🎉 开发环境初始化完成")


#######################################################################################################
# Main execution
if __name__ == "__main__":
    main()
