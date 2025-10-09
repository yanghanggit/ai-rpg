#!/usr/bin/env python3
"""
Neo4j 连接测试脚本

此脚本用于测试 Neo4j 数据库的基本连接和操作功能。
包括连接测试、创建节点、查询节点、删除数据等基础操作。

使用方法:
python scripts/test_neo4j_connection.py
"""

import sys
from typing import Optional, Any
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class Neo4jTester:
    """Neo4j 测试类"""

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "password123",
    ) -> None:
        """初始化连接参数

        默认密码设为 password123，如果你设置了不同的密码，请修改此处
        或者在调用时传入正确的密码
        """
        self.uri = uri
        self.user = user
        self.password = password
        self.driver: Optional[Any] = None

    def connect(self) -> bool:
        """建立数据库连接"""
        try:
            # 先尝试新密码
            self.driver = GraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
            # 测试连接
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info(f"✅ 成功连接到 Neo4j: {self.uri}")
            return True
        except AuthError:
            logger.info("🔧 尝试使用默认密码连接...")
            try:
                # 使用默认密码连接
                temp_driver = GraphDatabase.driver(self.uri, auth=(self.user, "neo4j"))
                with temp_driver.session(database="system") as session:
                    session.run(
                        "ALTER CURRENT USER SET PASSWORD FROM 'neo4j' TO $new_password",
                        new_password=self.password,
                    )
                temp_driver.close()

                # 使用新密码重新连接
                self.driver = GraphDatabase.driver(
                    self.uri, auth=(self.user, self.password)
                )
                with self.driver.session() as session:
                    session.run("RETURN 1")
                logger.info(f"✅ 密码设置成功，连接到 Neo4j: {self.uri}")
                return True
            except Exception as e:
                logger.error(f"❌ 连接失败: {e}")
                return False
        except ServiceUnavailable as e:
            logger.error(f"❌ 无法连接到 Neo4j 服务: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 连接异常: {e}")
            return False

    def test_basic_operations(self) -> bool:
        """测试基本的 CRUD 操作"""
        if not self.driver:
            logger.error("❌ 数据库未连接")
            return False

        try:
            with self.driver.session() as session:
                # 1. 创建测试节点
                logger.info("📝 创建测试节点...")
                result = session.run(
                    """
                    CREATE (p:Player {name: $name, level: $level, created_at: datetime()})
                    RETURN p.name as name, p.level as level, p.created_at as created_at
                """,
                    name="测试玩家",
                    level=1,
                )

                record = result.single()
                if record:
                    logger.info(
                        f"✅ 创建节点成功: {record['name']}, 等级: {record['level']}"
                    )

                # 2. 查询节点
                logger.info("🔍 查询测试节点...")
                result = session.run(
                    """
                    MATCH (p:Player {name: $name})
                    RETURN p.name as name, p.level as level, elementId(p) as node_id
                """,
                    name="测试玩家",
                )

                records = list(result)
                logger.info(f"✅ 查询到 {len(records)} 个节点")
                for record in records:
                    logger.info(
                        f"   - 玩家: {record['name']}, 等级: {record['level']}, ID: {record['node_id']}"
                    )

                # 3. 更新节点
                logger.info("📝 更新测试节点...")
                result = session.run(
                    """
                    MATCH (p:Player {name: $name})
                    SET p.level = p.level + 1, p.updated_at = datetime()
                    RETURN p.name as name, p.level as level
                """,
                    name="测试玩家",
                )

                record = result.single()
                if record:
                    logger.info(
                        f"✅ 更新节点成功: {record['name']}, 新等级: {record['level']}"
                    )

                # 4. 创建关系
                logger.info("🔗 创建测试关系...")
                session.run(
                    """
                    MERGE (g:Game {name: "AI RPG", type: "Roguelike TCG"})
                    WITH g
                    MATCH (p:Player {name: $player_name})
                    MERGE (p)-[r:PLAYS]->(g)
                    SET r.started_at = datetime()
                """,
                    player_name="测试玩家",
                )

                # 5. 查询关系
                result = session.run(
                    """
                    MATCH (p:Player)-[r:PLAYS]->(g:Game)
                    RETURN p.name as player, type(r) as relationship, g.name as game
                """
                )

                relationships = list(result)
                logger.info(f"✅ 查询到 {len(relationships)} 个关系")
                for rel in relationships:
                    logger.info(
                        f"   - {rel['player']} {rel['relationship']} {rel['game']}"
                    )

                return True

        except Exception as e:
            logger.error(f"❌ 基本操作测试失败: {e}")
            return False

    def test_ai_rpg_schema(self) -> bool:
        """测试 AI RPG 相关的图结构"""
        if not self.driver:
            logger.error("❌ 数据库未连接")
            return False

        try:
            with self.driver.session() as session:
                logger.info("🎮 创建 AI RPG 测试数据...")

                # 创建角色和技能
                session.run(
                    """
                    MERGE (c:Character {name: "勇者", class: "Warrior", hp: 100})
                    MERGE (s1:Skill {name: "剑击", damage: 25, mana_cost: 10})
                    MERGE (s2:Skill {name: "防御", defense_boost: 15, mana_cost: 5})
                    MERGE (c)-[:KNOWS]->(s1)
                    MERGE (c)-[:KNOWS]->(s2)
                """
                )

                # 创建装备
                session.run(
                    """
                    MERGE (w:Weapon {name: "铁剑", attack: 20, durability: 100})
                    MERGE (a:Armor {name: "皮甲", defense: 10, durability: 80})
                    WITH w, a
                    MATCH (c:Character {name: "勇者"})
                    MERGE (c)-[:EQUIPS]->(w)
                    MERGE (c)-[:WEARS]->(a)
                """
                )

                # 查询角色信息
                result = session.run(
                    """
                    MATCH (c:Character {name: "勇者"})
                    OPTIONAL MATCH (c)-[:KNOWS]->(s:Skill)
                    OPTIONAL MATCH (c)-[:EQUIPS]->(w:Weapon)
                    OPTIONAL MATCH (c)-[:WEARS]->(a:Armor)
                    RETURN c.name as character, 
                           c.class as class, 
                           c.hp as hp,
                           collect(DISTINCT s.name) as skills,
                           w.name as weapon,
                           a.name as armor
                """
                )

                record = result.single()
                if record:
                    logger.info("✅ AI RPG 角色创建成功:")
                    logger.info(f"   - 角色: {record['character']} ({record['class']})")
                    logger.info(f"   - 生命值: {record['hp']}")
                    logger.info(f"   - 技能: {', '.join(record['skills'])}")
                    logger.info(f"   - 武器: {record['weapon']}")
                    logger.info(f"   - 防具: {record['armor']}")

                return True

        except Exception as e:
            logger.error(f"❌ AI RPG 数据测试失败: {e}")
            return False

    def cleanup_test_data(self) -> None:
        """清理测试数据"""
        if not self.driver:
            return

        try:
            with self.driver.session() as session:
                logger.info("🧹 清理测试数据...")

                # 删除测试节点和关系
                session.run(
                    """
                    MATCH (p:Player {name: "测试玩家"})
                    DETACH DELETE p
                """
                )

                session.run(
                    """
                    MATCH (c:Character {name: "勇者"})
                    DETACH DELETE c
                """
                )

                session.run(
                    """
                    MATCH (n) WHERE n:Game OR n:Skill OR n:Weapon OR n:Armor
                    DETACH DELETE n
                """
                )

                logger.info("✅ 测试数据清理完成")

        except Exception as e:
            logger.warning(f"⚠️  清理数据时出现问题: {e}")

    def close(self) -> None:
        """关闭连接"""
        if self.driver:
            self.driver.close()
            logger.info("✅ 数据库连接已关闭")


def main() -> bool:
    """主函数"""
    logger.info("🚀 开始 Neo4j 连接测试...")

    # 创建测试实例
    tester = Neo4jTester()

    try:
        # 测试连接
        if not tester.connect():
            logger.error("❌ 连接测试失败，退出程序")
            return False

        # 验证服务器信息
        if tester.driver:
            with tester.driver.session() as session:
                result = session.run(
                    "CALL dbms.components() YIELD name, versions, edition"
                )
                for record in result:
                    logger.info(
                        f"📊 Neo4j 信息: {record['name']} {record['versions'][0]} ({record['edition']})"
                    )

        # 运行基本操作测试
        if not tester.test_basic_operations():
            logger.error("❌ 基本操作测试失败")
            return False

        # 运行 AI RPG 相关测试
        if not tester.test_ai_rpg_schema():
            logger.error("❌ AI RPG 数据测试失败")
            return False

        logger.info("🎉 所有测试通过！Neo4j 集成准备就绪")

        # 自动清理测试数据
        tester.cleanup_test_data()

        return True

    except KeyboardInterrupt:
        logger.info("\n⏹️  用户中断测试")
        return False
    except Exception as e:
        logger.error(f"❌ 测试过程中出现异常: {e}")
        return False
    finally:
        tester.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
